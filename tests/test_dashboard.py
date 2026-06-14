from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.dashboard.profile_catalog import ProfileCatalog
from game_script_dev.dashboard.readiness import evaluate_readiness
from game_script_dev.dashboard.run_registry import RunRegistry
from game_script_dev.dashboard.server import create_server, main as dashboard_main
from game_script_dev.dashboard.target_preview import TargetPreview


PROFILE_YAML = """
version: 1
name: Dashboard Demo
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: done
states:
  done:
    required_anchors:
      - name: done_title
        type: text
        text: Done
    terminal: true
    result: success
"""

PROFILE_PACK_YAML = """
version: 1
name: Dashboard Pack Demo
profile_pack:
  game: Demo Game
  game_mode: Daily Task
  detection_strategy: template_matching
  known_limitations:
    - Demo only; not verified against a live game window.
  compatibility:
    target_identity: true
    supported_resolution: true
    required_assets: true
    full_state_graph: true
    terminal_states: true
    failure_transitions: true
    interruption_recovery: true
    known_limitations: true
    successful_validation_or_dry_run: false
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: done
states:
  done:
    required_anchors:
      - name: done_title
        type: text
        text: Done
    terminal: true
    result: success
"""

LONG_WAIT_PROFILE_YAML = """
version: 1
name: Dashboard Long Wait
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: home
states:
  home:
    actions:
      - type: wait
        seconds: 2
    on_success: done
  done:
    terminal: true
    result: success
"""

MANUAL_STOP_PROFILE_YAML = """
version: 1
name: Dashboard Manual Stop
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
  manual_stop_is_dry_run_success: true
initial_state: start_repeat
states:
  start_repeat:
    actions:
      - type: start_continuous_input
        name: repeat_f_key
        action: press_key
        key: f
        repeat_every_seconds: 0.2
        seconds: 0.1
    on_success: keep_alive
    on_failure: failed
  keep_alive:
    actions:
      - type: wait
        seconds: 30
    on_success: keep_alive
    on_failure: failed
  failed:
    terminal: true
    result: failed_manual_stop
"""


class DashboardTests(unittest.TestCase):
    def test_profile_catalog_discovers_and_validates_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = _write_profile(Path(temp_dir))

            entries = ProfileCatalog(Path(temp_dir) / "profiles").list_profiles()

            self.assertEqual([entry.id for entry in entries], ["demo"])
            self.assertEqual(entries[0].path, profile_path)
            self.assertTrue(entries[0].valid)

    def test_profile_catalog_get_profile_path_uses_cached_id_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            catalog = ProfileCatalog(root / "profiles")

            resolved = catalog.get_profile_path("demo")
            catalog._cached_entries = []  # type: ignore[assignment]

            self.assertEqual(resolved, profile_path)
            self.assertEqual(catalog.get_profile_path("demo"), profile_path)

    def test_profile_catalog_validate_profile_updates_cached_entry_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            catalog = ProfileCatalog(root / "profiles")

            initial_entries = catalog.list_profiles()
            self.assertTrue(initial_entries[0].valid)

            profile_path.write_text("version: [\n", encoding="utf-8")
            updated = catalog.validate_profile("demo")

            self.assertFalse(updated.valid)
            self.assertIsNotNone(catalog._cached_entries)
            self.assertFalse(catalog._cached_entries[0].valid)  # type: ignore[index]

    def test_readiness_blocks_live_until_dashboard_dry_run_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = _write_profile(Path(temp_dir))

            report = evaluate_readiness(
                "demo",
                profile_path,
                last_dry_run_success=False,
                check_target=False,
            )

            self.assertFalse(report.live_available)
            self.assertIn("successful dry-run", " ".join(report.blockers))

    def test_readiness_mentions_operator_stop_for_manual_stop_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = _write_profile(Path(temp_dir), MANUAL_STOP_PROFILE_YAML)

            report = evaluate_readiness(
                "demo",
                profile_path,
                last_dry_run_success=False,
                check_target=False,
            )

            self.assertFalse(report.live_available)
            self.assertIn("stopped by the operator", " ".join(report.blockers))

    def test_readiness_uses_client_resolution_when_window_has_decorations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = _write_profile(Path(temp_dir))

            report = evaluate_readiness(
                "demo",
                profile_path,
                last_dry_run_success=True,
                window_adapter=DecoratedWindowAdapter(),
            )

            self.assertFalse(report.live_available)
            self.assertIn(
                "OCR adapter is optional and not configured by default",
                report.blockers,
            )
            self.assertEqual(report.target_status, "matched")
            self.assertEqual(report.resolution_status, "passed")

    def test_readiness_blocks_live_for_incomplete_profile_pack_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = _write_profile(Path(temp_dir), PROFILE_PACK_YAML)

            report = evaluate_readiness(
                "demo",
                profile_path,
                last_dry_run_success=True,
                check_target=False,
            )

            self.assertFalse(report.live_available)
            self.assertEqual(report.compatibility_status, "incomplete")
            self.assertIn("compatibility checklist", " ".join(report.blockers))
            self.assertIn("successful_validation_or_dry_run", " ".join(report.blockers))

    def test_profile_catalog_exposes_pack_metadata_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_profile(Path(temp_dir), PROFILE_PACK_YAML)

            entry = ProfileCatalog(Path(temp_dir) / "profiles").list_profiles()[0]
            payload = entry.to_dict()

            self.assertEqual(payload["pack_status"], "incomplete")
            self.assertEqual(payload["profile_pack"]["game"], "Demo Game")
            self.assertIn("successful_validation_or_dry_run", payload["profile_pack"]["missing_compatibility_checks"])
            self.assertIn("Dashboard notes", payload["notes"])

    def test_run_registry_records_dry_run_result_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            self.assertEqual(record.status, "completed")
            self.assertEqual(record.final_result, "success")
            self.assertTrue(registry.last_dry_run_success("demo"))
            self.assertIn("Profile finished", registry.read_log(record.id))

            review = registry.review(record.id)
            self.assertEqual(review["run"]["id"], record.id)
            self.assertNotIn("timeline", review["run"])
            self.assertTrue(review["timeline"])
            self.assertEqual(review["timeline"][0]["event"], "run_started")
            self.assertEqual(review["timeline"][-1]["event"], "run_completed")

    def test_run_registry_list_runs_can_limit_recent_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            first = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, first.id)
            time.sleep(1.1)
            second = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, second.id)

            runs = registry.list_runs(limit=1)

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].id, second.id)
            self.assertEqual(registry.run_count(), 2)

    def test_run_registry_preserves_newest_first_run_order_without_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            first = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, first.id)
            second = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, second.id)
            third = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, third.id)

            runs = registry.list_runs()

            self.assertEqual([run.id for run in runs[:3]], [third.id, second.id, first.id])

    def test_run_registry_lists_newest_artifact_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            assert record.run_paths is not None
            older = record.run_paths.artifact_dir / "older.txt"
            newer = record.run_paths.artifact_dir / "newer.txt"
            older.write_text("older", encoding="utf-8")
            time.sleep(1.1)
            newer.write_text("newer", encoding="utf-8")

            artifacts = registry.list_artifacts(record.id)

            self.assertEqual([artifact["name"] for artifact in artifacts[:2]], ["newer.txt", "older.txt"])
            self.assertIn("modified_at", artifacts[0])

    def test_run_registry_log_tail_returns_incremental_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            assert record.run_paths is not None
            record.run_paths.run_log.write_text("line1\nline2\n", encoding="utf-8")

            first = registry.read_log_tail(record.id, offset=0)
            line2_offset = str(first["text"]).index("line2")
            second = registry.read_log_tail(record.id, offset=line2_offset)

            self.assertEqual(str(first["text"]).splitlines(), ["line1", "line2"])
            self.assertEqual(str(second["text"]).splitlines(), ["line2"])
            self.assertEqual(second["offset"], line2_offset)
            self.assertEqual(second["next_offset"], len(str(first["text"]).encode("utf-8")))

    def test_run_registry_summary_and_review_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            summary = registry.run_summary(record.id)
            review = registry.review(record.id, after_index=1, limit=1)

            self.assertEqual(summary["id"], record.id)
            self.assertIn("log_size", summary)
            self.assertIn("timeline_count", summary)
            self.assertIn("artifact_stamp", summary)
            self.assertEqual(len(review["timeline"]), 1)
            self.assertEqual(review["next_index"], 2)
            self.assertEqual(review["total_count"], len(record.timeline))

    def test_run_registry_review_can_skip_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)

            review = registry.review(record.id, include_artifacts=False)

            self.assertIn("timeline", review)
            self.assertNotIn("artifacts", review)

    def test_run_registry_artifact_limit_returns_recent_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            assert record.run_paths is not None
            (record.run_paths.artifact_dir / "one.txt").write_text("1", encoding="utf-8")
            time.sleep(1.1)
            (record.run_paths.artifact_dir / "two.txt").write_text("2", encoding="utf-8")

            artifacts = registry.list_artifacts(record.id, limit=1)

            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0]["name"], "two.txt")

    def test_run_registry_artifact_snapshot_returns_count_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            assert record.run_paths is not None
            (record.run_paths.artifact_dir / "one.txt").write_text("1", encoding="utf-8")
            time.sleep(1.1)
            (record.run_paths.artifact_dir / "two.txt").write_text("2", encoding="utf-8")

            snapshot = registry.artifact_snapshot(record.id, limit=1)

            self.assertEqual(snapshot["total_count"], 2)
            self.assertEqual(len(snapshot["artifacts"]), 1)
            self.assertEqual(snapshot["latest_artifact"]["name"], "two.txt")

    def test_run_registry_can_stop_running_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root, LONG_WAIT_PROFILE_YAML)
            registry = RunRegistry(root / "logs")
            with patch("game_script_dev.dashboard.run_registry.Engine", FakeStoppableEngine):
                record = registry.start_run("demo", profile_path, "dry-run")
                _wait_for_status(registry, record.id, "running")
                registry.stop_run(record.id)
                _wait_for_run(registry, record.id)
                record = registry.get_run(record.id)

                self.assertEqual(record.status, "completed")
                self.assertEqual(record.final_result, "operator_stopped")
                self.assertTrue(record.stop_requested)
                self.assertFalse(registry.last_dry_run_success("demo"))

    def test_run_registry_accepts_operator_stopped_manual_stop_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root, MANUAL_STOP_PROFILE_YAML)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_status(registry, record.id, "running")
            stopped = registry.stop_run(record.id)
            _wait_for_run(registry, record.id)
            record = registry.get_run(record.id)

            self.assertTrue(stopped.stop_requested)
            self.assertEqual(record.status, "completed")
            self.assertEqual(record.final_result, "operator_stopped")
            self.assertTrue(registry.last_dry_run_success("demo"))

    def test_run_registry_stop_is_noop_after_run_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")

            record = registry.start_run("demo", profile_path, "dry-run")
            _wait_for_run(registry, record.id)

            stopped = registry.stop_run(record.id)

            self.assertEqual(stopped.status, "completed")
            self.assertEqual(stopped.final_result, "success")
            self.assertFalse(stopped.stop_requested)

    def test_server_exposes_profiles_and_starts_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                profiles = _get_json(f"{base_url}/api/profiles")
                self.assertEqual(profiles["profiles"][0]["id"], "demo")

                request = Request(
                    f"{base_url}/api/runs",
                    data=json.dumps({"profile_id": "demo", "mode": "dry-run"}).encode(
                        "utf-8"
                    ),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                response = json.loads(urlopen(request, timeout=5).read())
                self.assertEqual(response["profile_id"], "demo")

                runs = _get_json(f"{base_url}/api/runs")
                self.assertNotIn("timeline", runs["runs"][0])
                self.assertIn("total_count", runs)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_limits_run_list_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                first = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, first["id"])
                time.sleep(1.1)
                second = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, second["id"])

                runs = _get_json(f"{base_url}/api/runs?limit=1")

                self.assertEqual(len(runs["runs"]), 1)
                self.assertEqual(runs["runs"][0]["id"], second["id"])
                self.assertEqual(runs["total_count"], 2)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_json_responses_are_compact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                raw = urlopen(f"{base_url}/api/profiles", timeout=5).read().decode("utf-8")

                self.assertNotIn("\n", raw)
                self.assertTrue(raw.startswith("{"))
                self.assertIn('"profiles":[', raw)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_exposes_run_specific_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )

                readiness = _get_json(
                    f"{base_url}/api/runs/{response['id']}/readiness"
                )

                self.assertEqual(readiness["run_id"], response["id"])
                self.assertEqual(readiness["profile_id"], "demo")
                self.assertIn("blockers", readiness)
                self.assertIn("live_available", readiness)
                self.assertIn("target_status", readiness)
                self.assertIn("resolution_status", readiness)
                self.assertIn("compatibility_status", readiness)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_exposes_run_summary_log_tail_and_review_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, response["id"])

                summary = _get_json(f"{base_url}/api/runs/{response['id']}/summary")
                log_tail_response = urlopen(
                    f"{base_url}/api/runs/{response['id']}/log-tail?offset=0",
                    timeout=5,
                )
                log_tail_text = log_tail_response.read().decode("utf-8")
                review = _get_json(f"{base_url}/api/runs/{response['id']}/review?after=1&limit=1")

                self.assertEqual(summary["id"], response["id"])
                self.assertIn("log_size", summary)
                self.assertIn("timeline_count", summary)
                self.assertIn("artifact_stamp", summary)
                self.assertIsInstance(log_tail_text, str)
                self.assertIsNotNone(log_tail_response.headers.get("X-Log-Next-Offset"))
                self.assertIn(log_tail_response.headers.get("X-Log-Reset"), {"0", "1"})
                self.assertEqual(len(review["timeline"]), 1)
                self.assertIn("next_index", review)
                self.assertIn("total_count", review)
                self.assertIn("artifacts", review)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_review_can_skip_artifacts_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, response["id"])

                review = _get_json(
                    f"{base_url}/api/runs/{response['id']}/review?include_artifacts=0"
                )

                self.assertIn("timeline", review)
                self.assertNotIn("artifacts", review)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_caches_profile_readiness_briefly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                fake_report = type(
                    "Readiness",
                    (),
                    {"to_dict": lambda self: {"live_available": True}},
                )()
                with patch(
                    "game_script_dev.dashboard.server.evaluate_readiness",
                    return_value=fake_report,
                ) as mocked:
                    _get_json(f"{base_url}/api/profiles/demo/readiness")
                    _get_json(f"{base_url}/api/profiles/demo/readiness")

                self.assertEqual(mocked.call_count, 1)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_starts_live_run_without_run_confirmation_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                registry = server.dashboard_state.runs  # type: ignore[attr-defined]
                registry._last_dry_run_success["demo"] = True  # type: ignore[attr-defined]
                with patch(
                    "game_script_dev.dashboard.server.DashboardRequestHandler._readiness"
                ) as readiness:
                    readiness.return_value = type(
                        "Readiness",
                        (),
                        {"live_available": True, "to_dict": lambda self: {"live_available": True}},
                    )()
                    response = _post_json(
                        f"{base_url}/api/runs",
                        {"profile_id": "demo", "mode": "live"},
                    )

                self.assertEqual(response["mode"], "live")
            finally:
                server.shutdown()
                server.server_close()

    def test_server_exposes_startup_checks_and_run_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                startup = _get_json(f"{base_url}/api/startup-checks")
                self.assertIn("runtime_dependencies", startup["checks"])
                self.assertIn("writable_logs", startup["checks"])

                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, response["id"])

                review = _get_json(f"{base_url}/api/runs/{response['id']}/review")

                self.assertEqual(review["run"]["id"], response["id"])
                self.assertNotIn("timeline", review["run"])
                self.assertTrue(review["timeline"])
                self.assertIn("artifacts", review)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_exposes_runtime_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with patch(
                    "game_script_dev.dashboard.server.is_running_as_admin",
                    return_value=False,
                ):
                    runtime = _get_json(f"{base_url}/api/runtime")

                self.assertFalse(runtime["is_admin"])
                self.assertEqual(runtime["host"], "127.0.0.1")
            finally:
                server.shutdown()
                server.server_close()

    def test_server_can_start_admin_relaunch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            original_shutdown = server.shutdown
            shutdown_called = threading.Event()

            def recording_shutdown() -> None:
                shutdown_called.set()
                original_shutdown()

            server.shutdown = recording_shutdown  # type: ignore[assignment]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with patch(
                    "game_script_dev.dashboard.server.is_running_as_admin",
                    return_value=False,
                ):
                    with patch(
                        "game_script_dev.dashboard.server.relaunch_module_as_admin"
                    ) as relaunch:
                        payload = _post_json(
                            f"{base_url}/api/runtime/relaunch-admin",
                            {},
                        )

                self.assertEqual(payload["status"], "relaunching")
                relaunch.assert_called_once()
                self.assertTrue(shutdown_called.wait(2))
            finally:
                server.server_close()

    def test_server_can_stop_selected_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root, LONG_WAIT_PROFILE_YAML)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with patch("game_script_dev.dashboard.run_registry.Engine", FakeStoppableEngine):
                    response = _post_json(
                        f"{base_url}/api/runs",
                        {"profile_id": "demo", "mode": "dry-run"},
                    )
                    _wait_for_server_status(base_url, response["id"], "running")

                    stopped = _post_json(
                        f"{base_url}/api/runs/{response['id']}/stop",
                        {},
                    )
                    self.assertTrue(stopped["stop_requested"])

                    _wait_for_server_run(base_url, response["id"])
                    run = _get_json(f"{base_url}/api/runs/{response['id']}")
                    self.assertEqual(run["final_result"], "operator_stopped")
            finally:
                server.shutdown()
                server.server_close()

    def test_server_stop_is_noop_for_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                _wait_for_server_run(base_url, response["id"])

                stopped = _post_json(
                    f"{base_url}/api/runs/{response['id']}/stop",
                    {},
                )

                self.assertEqual(stopped["status"], "completed")
                self.assertEqual(stopped["final_result"], "success")
                self.assertFalse(stopped["stop_requested"])
            finally:
                server.shutdown()
                server.server_close()

    def test_server_exposes_target_preview_for_selected_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server(
                "127.0.0.1",
                0,
                root,
                root / "logs",
                target_preview=FakeTargetPreviewService(),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                preview = _get_json(f"{base_url}/api/profiles/demo/target-preview")

                self.assertEqual(preview["title"], "Demo Window")
                self.assertEqual(preview["process_name"], "python.exe")
                self.assertEqual(preview["width"], 320)
                self.assertEqual(preview["height"], 180)
                self.assertTrue(
                    str(preview["data_url"]).startswith("data:image/png;base64,")
                )
            finally:
                server.shutdown()
                server.server_close()

    def test_run_specific_readiness_uses_run_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            _write_profile(root, profile_id="other", name="Other Demo")
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "other", "mode": "dry-run"},
                )

                readiness = _get_json(
                    f"{base_url}/api/runs/{response['id']}/readiness"
                )

                self.assertEqual(readiness["profile_id"], "other")
            finally:
                server.shutdown()
                server.server_close()

    def test_run_specific_readiness_returns_404_for_missing_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(HTTPError) as captured:
                    urlopen(f"{base_url}/api/runs/missing/readiness", timeout=5)

                self.assertEqual(captured.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()

    def test_dashboard_static_ui_contains_live_verification_containers(self) -> None:
        html = Path("src/game_script_dev/dashboard/static/index.html").read_text(
            encoding="utf-8"
        )
        styles = Path("src/game_script_dev/dashboard/static/styles.css").read_text(
            encoding="utf-8"
        )
        app_js = Path("src/game_script_dev/dashboard/static/app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="live-verification-checklist"', html)
        self.assertIn('id="selected-run-readiness"', html)
        self.assertIn('id="latest-screenshot-link"', html)
        self.assertIn('id="profile-pack-detail"', html)
        self.assertIn('id="run-review-timeline"', html)
        self.assertIn('id="target-preview-image"', html)
        self.assertIn('id="target-preview-meta"', html)
        self.assertIn('id="runtime-admin-button"', html)
        self.assertIn('id="runtime-status"', html)
        self.assertIn('id="stop-run-button"', html)
        self.assertNotIn('id="live-dialog"', html)
        self.assertIn("aspect-ratio: var(--target-preview-ratio, 16 / 9);", styles)
        self.assertIn("min-height: 220px;", styles)
        self.assertIn(
            'frame.style.setProperty("--target-preview-ratio", String(Math.max(previewRatio, 16 / 9)));',
            app_js,
        )
        self.assertIn('function displayResultLabel(result)', app_js)
        self.assertIn('return "interrupt";', app_js)
        self.assertIn("function getActiveStoppableRun()", app_js)
        self.assertIn('button.textContent = run ? `Stop ${run.mode}` : "Stop";', app_js)
        self.assertIn("state.selectedRunId = runs.length ? runs[0].id : null;", app_js)
        self.assertIn("const latestArtifact = artifacts[0] || null;", app_js)
        self.assertIn("link.textContent = `Latest artifact: ${latestArtifact.name}`;", app_js)
        self.assertIn("async function refreshSelectedRunData({ force = false } = {})", app_js)
        self.assertIn("async function fetchLogTail(runId, offset)", app_js)
        self.assertIn('response.headers.get("X-Log-Next-Offset")', app_js)
        self.assertIn("artifacts?limit=", app_js)
        self.assertIn("const MAX_VISIBLE_RUNS = 100;", app_js)
        self.assertIn('api(`/api/runs?limit=${MAX_VISIBLE_RUNS}`)', app_js)
        self.assertIn("function scheduleNextPoll()", app_js)
        self.assertIn("window.setTimeout(async () => {", app_js)
        self.assertIn("const PREVIEW_REFRESH_INTERVAL_MS = 1000;", app_js)
        self.assertIn("const ACTIVE_POLL_INTERVAL_MS = 1000;", app_js)
        self.assertIn("const IDLE_POLL_INTERVAL_MS = 1000;", app_js)
        self.assertIn("hasActiveRun: false,", app_js)
        self.assertIn("state.hasActiveRun = runs.some((run) => isRunActive(run));", app_js)
        self.assertIn("const interval = state.hasActiveRun ? ACTIVE_POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS;", app_js)
        self.assertIn("await refreshReadiness({ includePreview: true });", app_js)
        self.assertIn("include_artifacts=0", app_js)
        self.assertIn("function renderRunsList()", app_js)
        self.assertIn("function renderRunCount()", app_js)
        self.assertIn("function upsertRunEntry(runEntry)", app_js)
        self.assertIn("function normalizeRunListEntry(runEntry)", app_js)
        self.assertIn("renderRunsList();", app_js)
        self.assertIn('button.dataset.profileId = profile.id;', app_js)
        self.assertIn('button.dataset.runId = run.id;', app_js)
        self.assertIn('$("profiles").addEventListener("click", async (event) => {', app_js)
        self.assertIn('$("runs").addEventListener("click", async (event) => {', app_js)
        self.assertIn("const shouldRefreshSelectedRunDetail = (", app_js)
        self.assertIn("|| state.hasActiveRun", app_js)
        self.assertIn("|| previousHasActiveRun !== state.hasActiveRun", app_js)
        self.assertIn("function syncSelectedRunListState()", app_js)
        self.assertIn("async function selectProfile(profileId, { autoDryRun = false, skipInitialReadiness = false } = {})", app_js)
        self.assertIn("function upsertProfileEntry(profileEntry)", app_js)
        self.assertIn("skipInitialReadiness: true", app_js)
        self.assertIn("const validatedProfile = await validateSelectedProfile();", app_js)
        self.assertIn("previous.artifact_stamp !== summary.artifact_stamp", app_js)
        self.assertIn('runLogLineCounts: {}', app_js)
        self.assertIn("state.runLogLineCounts[summary.id] = countLines(target.textContent);", app_js)
        self.assertIn("state.runLogLineCounts[runId] = countLines(text);", app_js)
        self.assertIn("scrollLogToLatest(target);", app_js)
        self.assertIn("function scrollLogToLatest(target)", app_js)
        self.assertIn("target.scrollTop = target.scrollHeight;", app_js)
        self.assertIn("function countLines(text)", app_js)
        self.assertIn('lastProfilesSignature: ""', app_js)
        self.assertIn('lastProfileSelectSignature: ""', app_js)
        self.assertIn('lastPackDetailSignature: ""', app_js)
        self.assertIn('lastRuntimeSignature: ""', app_js)
        self.assertIn('lastReadinessSignature: ""', app_js)
        self.assertIn('lastRunReadinessSignature: ""', app_js)
        self.assertIn("if (signature === state.lastProfilesSignature) {", app_js)
        self.assertIn("if (signature === state.lastProfileSelectSignature) {", app_js)
        self.assertIn("if (signature === state.lastPackDetailSignature) {", app_js)
        self.assertIn("if (signature === state.lastRuntimeSignature) {", app_js)
        self.assertIn("if (signature !== state.lastReadinessSignature) {", app_js)
        self.assertIn("if (signature === state.lastRunReadinessSignature) {", app_js)
        self.assertIn("state.lastMessageSignatures[id] === signature", app_js)

    def test_dashboard_can_relaunch_as_admin(self) -> None:
        with patch(
            "game_script_dev.dashboard.server.is_running_as_admin",
            return_value=False,
        ):
            with patch(
                "game_script_dev.dashboard.server.relaunch_module_as_admin"
            ) as relaunch:
                result = dashboard_main(
                    [
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8765",
                        "--run-as-admin",
                    ]
                )

        self.assertEqual(result, 0)
        relaunch.assert_called_once()
        module, args = relaunch.call_args.args[:2]
        self.assertEqual(module, "game_script_dev.dashboard")
        self.assertNotIn("--run-as-admin", args)


def _write_profile(
    root: Path,
    contents: str = PROFILE_YAML,
    *,
    profile_id: str = "demo",
    name: str | None = None,
) -> Path:
    if name is not None:
        contents = contents.replace("name: Dashboard Demo", f"name: {name}", 1)
    profile_dir = root / "profiles" / profile_id
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "profile.yaml"
    profile_path.write_text(contents, encoding="utf-8")
    (profile_dir / "notes.md").write_text("Dashboard notes", encoding="utf-8")
    return profile_path


def _wait_for_run(registry: RunRegistry, run_id: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = registry.get_run(run_id)
        if record.status in {"completed", "failed"}:
            return
        time.sleep(0.01)
    raise AssertionError("run did not finish")


def _wait_for_status(registry: RunRegistry, run_id: str, status: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = registry.get_run(run_id)
        if record.status == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"run did not reach status {status}")


def _get_json(url: str) -> dict[str, object]:
    return json.loads(urlopen(url, timeout=5).read())


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urlopen(request, timeout=5).read())


class FakeTargetPreviewService:
    def capture(self, profile_path: Path) -> TargetPreview:
        return TargetPreview(
            title="Demo Window",
            process_name="python.exe",
            width=320,
            height=180,
            data_url="data:image/png;base64,ZmFrZQ==",
        )


class DecoratedWindowAdapter:
    def find_target(self, profile: object) -> TargetWindow:
        return TargetWindow(
            title="Decorated Demo",
            process_name="demo.exe",
            left=100,
            top=200,
            width=1296,
            height=759,
            handle=100,
            process_id=200,
            client_left=108,
            client_top=231,
            client_width=1280,
            client_height=720,
        )


class FakeStoppableEngine:
    def __init__(
        self,
        *,
        stop_requested,
        sleeper,
        event_handler=None,
        **_kwargs,
    ) -> None:
        self.stop_requested = stop_requested
        self.sleeper = sleeper
        self.event_handler = event_handler

    def run(self) -> str:
        if self.event_handler is not None:
            self.event_handler({"event": "state_started", "state": "home"})
        while not self.stop_requested():
            self.sleeper(0.05)
        if self.event_handler is not None:
            self.event_handler(
                {
                    "event": "finished",
                    "state": "home",
                    "result": "operator_stopped",
                    "failure_reason": "stop requested by operator",
                }
            )
        return "operator_stopped"


def _wait_for_server_run(base_url: str, run_id: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = _get_json(f"{base_url}/api/runs/{run_id}")
        if run["status"] in {"completed", "failed"}:
            return
        time.sleep(0.01)
    raise AssertionError("server run did not finish")


def _wait_for_server_status(base_url: str, run_id: str, status: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = _get_json(f"{base_url}/api/runs/{run_id}")
        if run["status"] == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"server run did not reach status {status}")


if __name__ == "__main__":
    unittest.main()
