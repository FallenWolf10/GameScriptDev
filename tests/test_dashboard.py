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
from game_script_dev.dashboard.run_registry import (
    ActiveRunConflictError,
    RunRegistry,
)
from game_script_dev.dashboard.server import (
    LIVE_CONFIRMATION_VALUE,
    create_server,
    main as dashboard_main,
)
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

    def test_readiness_allows_profile_scoped_dry_run_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_yaml = PROFILE_YAML.replace(
                "execution:\n",
                "execution:\n  skip_dry_run_requirement: true\n",
            )
            profile_path = _write_profile(Path(temp_dir), profile_yaml)

            report = evaluate_readiness(
                "demo",
                profile_path,
                last_dry_run_success=False,
                check_target=False,
            )

            self.assertNotIn("dry-run", " ".join(report.blockers))

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
            self.assertEqual(report.background_capture_status, "visible_required")
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
            self.assertEqual(payload["target"]["process_name"], "demo.exe")
            self.assertEqual(payload["target"]["input_mode"], "background_window_messages")
            self.assertEqual(payload["resolution"]["width"], 1280)
            self.assertEqual(payload["state_count"], 1)

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

    def test_run_registry_atomically_rejects_a_second_active_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")
            worker_started = threading.Event()
            release_worker = threading.Event()

            def hold_worker(record, _stop_event) -> None:
                worker_started.set()
                release_worker.wait(5)
                registry._update(  # type: ignore[attr-defined]
                    record.id,
                    status="completed",
                    finished_at="finished",
                )

            with patch.object(registry, "_run_profile", side_effect=hold_worker):
                first = registry.start_run("demo", profile_path, "dry-run")
                self.assertTrue(worker_started.wait(1))

                with self.assertRaises(ActiveRunConflictError) as raised:
                    registry.start_run("demo", profile_path, "dry-run")

                self.assertEqual(raised.exception.active_run.id, first.id)
                self.assertEqual(registry.run_count(), 1)
                self.assertEqual(registry.active_run().id, first.id)
                release_worker.set()
                _wait_for_run(registry, first.id)

            self.assertIsNone(registry.active_run())

    def test_run_registry_admits_exactly_one_of_two_concurrent_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            registry = RunRegistry(root / "logs")
            request_barrier = threading.Barrier(3)
            release_worker = threading.Event()
            accepted = []
            conflicts = []

            def hold_worker(record, _stop_event) -> None:
                release_worker.wait(5)
                registry._update(  # type: ignore[attr-defined]
                    record.id,
                    status="completed",
                    finished_at="finished",
                )

            def request_run() -> None:
                request_barrier.wait()
                try:
                    accepted.append(
                        registry.start_run("demo", profile_path, "dry-run")
                    )
                except ActiveRunConflictError as error:
                    conflicts.append(error)

            with patch.object(registry, "_run_profile", side_effect=hold_worker):
                requests = [
                    threading.Thread(target=request_run, daemon=True)
                    for _ in range(2)
                ]
                for request in requests:
                    request.start()
                request_barrier.wait()
                for request in requests:
                    request.join(2)

                self.assertEqual(len(accepted), 1)
                self.assertEqual(len(conflicts), 1)
                self.assertEqual(registry.run_count(), 1)
                self.assertEqual(
                    conflicts[0].active_run.id,
                    accepted[0].id,
                )
                release_worker.set()
                _wait_for_run(registry, accepted[0].id)

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

                source = _get_json(f"{base_url}/api/profiles/demo/source")
                structured = _get_json(
                    f"{base_url}/api/profiles/demo/structured"
                )
                self.assertFalse(source["read_only"])
                self.assertEqual(len(source["fingerprint"]), 64)
                self.assertEqual(structured["fingerprint"], source["fingerprint"])
                self.assertEqual(structured["document"]["name"], "Dashboard Demo")
                self.assertFalse(structured["read_only"])

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

    def test_server_creates_a_new_profile_pack_in_the_user_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                created = _post_json(
                    f"{base_url}/api/profiles",
                    {
                        "profile_id": "daily_route",
                        "name": "Daily Route",
                        "game": "Example Game",
                        "mode": "Daily Task",
                        "initial_state": "start",
                    },
                )

                self.assertEqual(created["profile"]["id"], "daily_route")
                self.assertEqual(created["profile"]["name"], "Daily Route")
                pack_dir = root / "profiles" / "daily_route"
                self.assertTrue((pack_dir / "profile.yaml").is_file())
                self.assertTrue((pack_dir / "notes.md").is_file())
                self.assertTrue((pack_dir / "assets" / ".gitkeep").is_file())
                self.assertTrue(
                    (pack_dir / "validation_examples" / "valid" / ".gitkeep").is_file()
                )
                self.assertIn("initial_state: start", created["source"]["source"])
                self.assertIn("  start:", created["source"]["source"])
                self.assertFalse(created["source"]["read_only"])
                self.assertEqual(
                    _get_json(f"{base_url}/api/profiles")["profiles"][0]["id"],
                    "daily_route",
                )

                with self.assertRaises(HTTPError) as duplicate:
                    _post_json(
                        f"{base_url}/api/profiles",
                        {
                            "profile_id": "daily_route",
                            "name": "Duplicate",
                            "game": "Example Game",
                            "mode": "Daily Task",
                            "initial_state": "start",
                        },
                    )
                self.assertEqual(duplicate.exception.code, 409)

                with self.assertRaises(HTTPError) as traversal:
                    _post_json(
                        f"{base_url}/api/profiles",
                        {
                            "profile_id": "../outside",
                            "name": "Outside",
                            "game": "Example Game",
                            "mode": "Daily Task",
                            "initial_state": "start",
                        },
                    )
                self.assertEqual(traversal.exception.code, 400)
                self.assertFalse((root / "outside").exists())
            finally:
                server.shutdown()
                server.server_close()

    def test_server_persists_drafts_and_only_replaces_yaml_on_valid_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                source = _get_json(f"{base_url}/api/profiles/demo/source")
                invalid_source = "version: [\n"

                invalid_draft = _post_json(
                    f"{base_url}/api/profiles/demo/draft",
                    {
                        "source": invalid_source,
                        "base_fingerprint": source["fingerprint"],
                    },
                )

                self.assertFalse(invalid_draft["valid"])
                self.assertTrue(invalid_draft["dirty"])
                self.assertEqual(profile_path.read_text(encoding="utf-8"), PROFILE_YAML)
                recovered = _get_json(f"{base_url}/api/profiles/demo/draft")
                self.assertEqual(recovered["source"], invalid_source)
                self.assertTrue(recovered["exists"])

                with self.assertRaises(HTTPError) as invalid_save:
                    _post_json(f"{base_url}/api/profiles/demo/save", {})
                self.assertEqual(invalid_save.exception.code, 422)
                self.assertEqual(profile_path.read_text(encoding="utf-8"), PROFILE_YAML)

                valid_source = PROFILE_YAML.replace(
                    "name: Dashboard Demo",
                    "name: Edited In Application",
                    1,
                )
                valid_draft = _post_json(
                    f"{base_url}/api/profiles/demo/draft",
                    {
                        "source": valid_source,
                        "base_fingerprint": source["fingerprint"],
                    },
                )
                self.assertTrue(valid_draft["valid"], valid_draft["errors"])

                saved = _post_json(f"{base_url}/api/profiles/demo/save", {})

                self.assertEqual(saved["profile"]["name"], "Edited In Application")
                self.assertEqual(profile_path.read_text(encoding="utf-8"), valid_source)
                self.assertFalse(
                    _get_json(f"{base_url}/api/profiles/demo/draft")["exists"]
                )
                revisions = list((root / "drafts" / "revisions").rglob("*.yaml"))
                self.assertEqual(len(revisions), 1)
                self.assertEqual(revisions[0].read_text(encoding="utf-8"), PROFILE_YAML)
            finally:
                server.shutdown()
                server.server_close()

    def test_server_refuses_to_overwrite_an_external_yaml_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                source = _get_json(f"{base_url}/api/profiles/demo/source")
                draft_source = PROFILE_YAML.replace(
                    "name: Dashboard Demo",
                    "name: Draft Name",
                    1,
                )
                _post_json(
                    f"{base_url}/api/profiles/demo/draft",
                    {
                        "source": draft_source,
                        "base_fingerprint": source["fingerprint"],
                    },
                )
                external_source = PROFILE_YAML.replace(
                    "name: Dashboard Demo",
                    "name: External Name",
                    1,
                )
                profile_path.write_text(external_source, encoding="utf-8")

                with self.assertRaises(HTTPError) as conflict:
                    _post_json(f"{base_url}/api/profiles/demo/save", {})

                self.assertEqual(conflict.exception.code, 409)
                payload = json.loads(conflict.exception.read())
                self.assertIn("changed outside", payload["error"])
                self.assertEqual(profile_path.read_text(encoding="utf-8"), external_source)
                recovered = _get_json(f"{base_url}/api/profiles/demo/draft")
                self.assertEqual(recovered["source"], draft_source)
                self.assertTrue(recovered["conflict"])
            finally:
                server.shutdown()
                server.server_close()

    def test_server_rejects_invalid_profile_without_creating_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root, "version: [\n")
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                with self.assertRaises(HTTPError) as invalid:
                    _post_json(
                        f"{base_url}/api/runs",
                        {"profile_id": "demo", "mode": "dry-run"},
                    )

                self.assertEqual(invalid.exception.code, 400)
                payload = json.loads(invalid.exception.read())
                self.assertEqual(payload["error"], "profile is invalid")
                self.assertFalse(payload["profile"]["valid"])
                self.assertEqual(
                    _get_json(f"{base_url}/api/runs")["total_count"],
                    0,
                )
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

    def test_server_requires_and_accepts_per_attempt_live_confirmation(self) -> None:
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
                    with self.assertRaises(HTTPError) as missing_confirmation:
                        _post_json(
                            f"{base_url}/api/runs",
                            {"profile_id": "demo", "mode": "live"},
                        )
                    self.assertEqual(missing_confirmation.exception.code, 400)

                    response = _post_json(
                        f"{base_url}/api/runs",
                        {
                            "profile_id": "demo",
                            "mode": "live",
                            "confirmation": LIVE_CONFIRMATION_VALUE,
                        },
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
                self.assertEqual(runtime["port"], server.server_port)
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

    def test_server_rejects_competing_run_with_active_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root, LONG_WAIT_PROFILE_YAML)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with patch(
                    "game_script_dev.dashboard.run_registry.Engine",
                    FakeStoppableEngine,
                ):
                    first = _post_json(
                        f"{base_url}/api/runs",
                        {"profile_id": "demo", "mode": "dry-run"},
                    )
                    _wait_for_server_status(base_url, first["id"], "running")

                    with self.assertRaises(HTTPError) as conflict:
                        _post_json(
                            f"{base_url}/api/runs",
                            {"profile_id": "demo", "mode": "dry-run"},
                        )

                    self.assertEqual(conflict.exception.code, 409)
                    payload = json.loads(conflict.exception.read())
                    self.assertEqual(payload["active_run"]["id"], first["id"])
                    runs = _get_json(f"{base_url}/api/runs")
                    self.assertEqual(runs["total_count"], 1)
                    self.assertEqual(runs["active_run"]["id"], first["id"])

                    _post_json(
                        f"{base_url}/api/runs/{first['id']}/stop",
                        {},
                    )
                    _wait_for_server_run(base_url, first["id"])
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

    def test_dashboard_static_ui_exposes_operator_application_contract(self) -> None:
        html = Path("src/game_script_dev/dashboard/static/index.html").read_text(
            encoding="utf-8"
        )
        styles = Path("src/game_script_dev/dashboard/static/styles.css").read_text(
            encoding="utf-8"
        )
        app_js = Path("src/game_script_dev/dashboard/static/app.js").read_text(
            encoding="utf-8"
        )

        required_ids = {
            "workspace-navigation",
            "workspace-run",
            "workspace-build",
            "workspace-settings",
            "stop-run-button",
            "target-preview-image",
            "background-capture-status",
            "live-verification-checklist",
            "run-review-timeline",
            "log-output",
            "artifacts",
            "profile-pack-detail",
            "builder-state-list",
            "builder-action-list",
            "builder-action-palette",
            "builder-action-inspector-form",
            "builder-diff-dialog",
            "builder-diff-preview",
            "confirm-builder-diff",
            "move-builder-action-state",
            "move-builder-action-state-button",
            "builder-problems-drawer",
            "undo-builder-action",
            "redo-builder-action",
            "builder-state-view-tab",
            "builder-graph-view-tab",
            "builder-flow-canvas",
            "builder-flow-edges",
            "builder-flow-nodes",
            "builder-flow-inspector-form",
            "tidy-builder-flow",
            "undo-builder-layout",
            "redo-builder-layout",
            "create-profile-button",
            "create-profile-dialog",
            "create-profile-form",
            "builder-yaml-editor",
            "validate-builder-draft",
            "save-builder-profile",
            "reload-builder-source",
            "builder-draft-messages",
            "startup-checks-list",
            "live-dialog",
            "cancel-live-button",
            "confirm-live-button",
        }
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('id="cancel-live-button" value="cancel"', html)
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.googleapis.com", styles)

        self.assertIn("aspect-ratio: var(--target-preview-ratio, 16 / 9);", styles)
        self.assertIn(".run-layout", styles)
        self.assertIn(".builder-state-node", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)
        self.assertIn(":focus-visible", styles)

        self.assertIn(
            'frame.style.setProperty("--target-preview-ratio", String(Math.max(previewRatio, 16 / 9)));',
            app_js,
        )
        self.assertIn("payload.active_run", app_js)
        self.assertIn("dialog.showModal();", app_js)
        self.assertIn('startRun("live", "start-live-run")', app_js)
        self.assertIn("async function refreshBuilderProfile()", app_js)
        self.assertIn("/structured`)", app_js)
        self.assertIn("async function persistBuilderDraft", app_js)
        self.assertIn("async function saveBuilderProfile", app_js)
        self.assertIn("async function mutateBuilderAction", app_js)
        self.assertIn("async function restoreBuilderActionHistory", app_js)
        self.assertIn('operation: "move_to_state"', app_js)
        self.assertIn("builder-drag-handle", app_js)
        self.assertIn("function renderBuilderInspectorField", app_js)
        self.assertIn("data-builder-action-field", app_js)
        self.assertIn("mutation.unset_fields", app_js)
        self.assertIn("function confirmBuilderDiff", app_js)
        self.assertIn("/actions/preview", app_js)
        self.assertIn("function stateProblems", app_js)
        self.assertIn("function showBuilderDropIndicator", app_js)
        self.assertIn("function autoScrollBuilderActionList", app_js)
        self.assertIn("function renderBuilderFlowGraph", app_js)
        self.assertIn("async function mutateBuilderFlow", app_js)
        self.assertIn("async function tidyBuilderFlowLayout", app_js)
        self.assertIn("/flow-layout", app_js)
        self.assertIn('operation: "update_state"', app_js)
        self.assertIn('"dragstart"', app_js)
        self.assertIn('"dragover"', app_js)
        self.assertIn('"drop"', app_js)
        self.assertIn('event.key !== "Escape"', app_js)
        self.assertIn("builder-drop-indicator", styles)
        self.assertIn("builder-state-node.drag-target", styles)
        self.assertIn(".builder-flow-node", styles)
        self.assertIn(".builder-flow-edge.success", styles)
        self.assertIn("async function createProfile", app_js)
        self.assertIn("function activateWorkspace(workspace", app_js)
        self.assertIn("function scheduleNextPoll()", app_js)
        self.assertNotIn("autoDryRun", app_js)

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

    def test_server_exposes_action_schema_and_versioned_mutations(self) -> None:
        source_with_comments = LONG_WAIT_PROFILE_YAML.replace(
            "    actions:\n",
            "    # Keep State guidance.\n    actions:\n",
        ).replace(
            "        seconds: 2",
            "        seconds: 2 # tune carefully",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root, source_with_comments)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                schema = _get_json(f"{base_url}/api/profile-schema")
                wait_definition = next(
                    action
                    for action in schema["actions"]
                    if action["type"] == "wait"
                )
                self.assertEqual(schema["version"], 2)
                self.assertTrue(wait_definition["structured"])
                self.assertEqual(wait_definition["fields"][0]["default"], 1)
                self.assertEqual(
                    {
                        action["type"]
                        for action in schema["actions"]
                        if action["structured"]
                    },
                    {
                        "wait",
                        "log",
                        "press_key",
                        "hold_key",
                        "click_point",
                        "wait_for_state",
                        "stop",
                    },
                )

                initial = _get_json(f"{base_url}/api/profiles/demo/draft")
                self.assertEqual(initial["version"], 0)
                with self.assertRaises(HTTPError) as unversioned:
                    _post_json(
                        f"{base_url}/api/profiles/demo/actions",
                        {
                            "mutation": {
                                "operation": "delete",
                                "state": "home",
                                "index": 0,
                            },
                        },
                    )
                self.assertEqual(unversioned.exception.code, 400)
                updated = _post_json(
                    f"{base_url}/api/profiles/demo/actions",
                    {
                        "expected_version": initial["version"],
                        "expected_fingerprint": initial["draft_fingerprint"],
                        "mutation": {
                            "operation": "update",
                            "state": "home",
                            "index": 0,
                            "fields": {"seconds": -1},
                        },
                    },
                )
                self.assertEqual(updated["version"], 1)
                self.assertFalse(updated["valid"])
                self.assertTrue(updated["history"]["can_undo"])
                self.assertIn("# Keep State guidance.", updated["source"])
                self.assertIn("seconds: -1 # tune carefully", updated["source"])
                self.assertEqual(
                    updated["problems"][0]["location"],
                    "states.home.actions[0].seconds",
                )
                validated = _post_json(
                    f"{base_url}/api/profiles/demo/draft",
                    {
                        "source": updated["source"],
                        "base_fingerprint": updated["base_fingerprint"],
                        "expected_version": updated["version"],
                    },
                )
                self.assertEqual(validated["version"], updated["version"])
                self.assertTrue(validated["history"]["can_undo"])

                undone = _post_json(
                    f"{base_url}/api/profiles/demo/undo",
                    {"expected_version": updated["version"]},
                )
                self.assertTrue(undone["valid"], undone["errors"])
                self.assertIn("seconds: 2 # tune carefully", undone["source"])
                self.assertTrue(undone["history"]["can_redo"])

                redone = _post_json(
                    f"{base_url}/api/profiles/demo/redo",
                    {"expected_version": undone["version"]},
                )
                self.assertFalse(redone["valid"])

                with self.assertRaises(HTTPError) as stale:
                    _post_json(
                        f"{base_url}/api/profiles/demo/actions",
                        {
                            "expected_version": updated["version"],
                            "mutation": {
                                "operation": "delete",
                                "state": "home",
                                "index": 0,
                            },
                        },
                    )
                self.assertEqual(stale.exception.code, 409)
                current = _get_json(f"{base_url}/api/profiles/demo/draft")
                self.assertEqual(current["source"], redone["source"])
            finally:
                server.shutdown()
                server.server_close()

    def test_saved_structured_wait_edit_is_used_by_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root, LONG_WAIT_PROFILE_YAML)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                draft = _get_json(f"{base_url}/api/profiles/demo/draft")
                edited = _post_json(
                    f"{base_url}/api/profiles/demo/actions",
                    {
                        "expected_version": draft["version"],
                        "mutation": {
                            "operation": "update",
                            "state": "home",
                            "index": 0,
                            "fields": {"seconds": 0.01},
                        },
                    },
                )
                self.assertTrue(edited["valid"], edited["errors"])
                _post_json(f"{base_url}/api/profiles/demo/save", {})
                self.assertIn(
                    "seconds: 0.01",
                    profile_path.read_text(encoding="utf-8"),
                )

                run = _post_json(
                    f"{base_url}/api/runs",
                    {"profile_id": "demo", "mode": "dry-run"},
                )
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    current = _get_json(f"{base_url}/api/runs/{run['id']}")
                    if current["status"] in {"completed", "failed", "interrupted"}:
                        break
                    time.sleep(0.02)
                self.assertEqual(current["status"], "completed")
                review = _get_json(f"{base_url}/api/runs/{run['id']}/review")
                wait_event = next(
                    event
                    for event in review["timeline"]
                    if event["event"] == "action_completed"
                )
                self.assertEqual(wait_event["action_type"], "wait")
                self.assertIn("0.01", wait_event["action_summary"])
            finally:
                server.shutdown()
                server.server_close()

    def test_structured_mutation_preview_requires_matching_confirmation(self) -> None:
        source = LONG_WAIT_PROFILE_YAML.replace(
            "      - type: wait",
            "      # Keep timing context.\n      - type: wait",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root, source)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                draft = _get_json(f"{base_url}/api/profiles/demo/draft")
                request = {
                    "expected_version": draft["version"],
                    "expected_fingerprint": draft["draft_fingerprint"],
                    "mutation": {
                        "operation": "delete",
                        "state": "home",
                        "index": 0,
                    },
                }
                preview = _post_json(
                    f"{base_url}/api/profiles/demo/actions/preview",
                    request,
                )
                self.assertTrue(preview["requires_confirmation"])
                self.assertTrue(preview["comment_changes"])
                self.assertIn("-      # Keep timing context.", preview["diff"])

                with self.assertRaises(HTTPError) as unconfirmed:
                    _post_json(
                        f"{base_url}/api/profiles/demo/actions",
                        request,
                    )
                self.assertEqual(unconfirmed.exception.code, 428)
                unchanged = _get_json(f"{base_url}/api/profiles/demo/draft")
                self.assertEqual(unchanged["version"], draft["version"])

                confirmed = _post_json(
                    f"{base_url}/api/profiles/demo/actions",
                    {
                        **request,
                        "confirmed_preview_fingerprint": preview[
                            "updated_fingerprint"
                        ],
                    },
                )
                self.assertEqual(confirmed["document"]["states"]["home"]["actions"], [])
                self.assertNotIn("# Keep timing context.", confirmed["source"])
                self.assertEqual(profile_path.read_text(encoding="utf-8"), source)
            finally:
                server.shutdown()
                server.server_close()

    def test_state_validation_problem_has_a_navigable_location(self) -> None:
        source = PROFILE_YAML.replace("    result: success", '    result: ""')
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_profile(root, PROFILE_YAML)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                draft = _get_json(f"{base_url}/api/profiles/demo/draft")
                invalid = _post_json(
                    f"{base_url}/api/profiles/demo/draft",
                    {
                        "source": source,
                        "base_fingerprint": draft["base_fingerprint"],
                        "expected_version": draft["version"],
                    },
                )

                self.assertFalse(invalid["valid"])
                self.assertEqual(
                    invalid["problems"][0]["location"],
                    "states.done.result",
                )
            finally:
                server.shutdown()
                server.server_close()

    def test_flow_mutations_and_builder_only_layout_are_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = _write_profile(root, LONG_WAIT_PROFILE_YAML)
            server = create_server("127.0.0.1", 0, root, root / "logs")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                draft = _get_json(f"{base_url}/api/profiles/demo/draft")
                mutation = {
                    "operation": "update_state",
                    "state": "home",
                    "make_initial": False,
                    "terminal": False,
                    "on_success": "done",
                    "on_failure": "graceful_termination",
                }
                preview = _post_json(
                    f"{base_url}/api/profiles/demo/flow/preview",
                    {
                        "expected_version": draft["version"],
                        "expected_fingerprint": draft["draft_fingerprint"],
                        "mutation": mutation,
                    },
                )
                self.assertFalse(preview["requires_confirmation"])
                updated = _post_json(
                    f"{base_url}/api/profiles/demo/flow",
                    {
                        "expected_version": draft["version"],
                        "expected_fingerprint": draft["draft_fingerprint"],
                        "mutation": mutation,
                    },
                )
                self.assertEqual(
                    updated["document"]["states"]["home"]["on_failure"],
                    "graceful_termination",
                )
                self.assertEqual(
                    profile_path.read_text(encoding="utf-8"),
                    LONG_WAIT_PROFILE_YAML,
                )

                terminal_mutation = {
                    "operation": "update_state",
                    "state": "home",
                    "make_initial": False,
                    "terminal": True,
                    "result": "success",
                }
                terminal_request = {
                    "expected_version": updated["version"],
                    "expected_fingerprint": updated["draft_fingerprint"],
                    "mutation": terminal_mutation,
                }
                terminal_preview = _post_json(
                    f"{base_url}/api/profiles/demo/flow/preview",
                    terminal_request,
                )
                self.assertTrue(terminal_preview["requires_confirmation"])
                with self.assertRaises(HTTPError) as unconfirmed:
                    _post_json(
                        f"{base_url}/api/profiles/demo/flow",
                        terminal_request,
                    )
                self.assertEqual(unconfirmed.exception.code, 428)
                terminal = _post_json(
                    f"{base_url}/api/profiles/demo/flow",
                    {
                        **terminal_request,
                        "confirmed_preview_fingerprint": terminal_preview[
                            "updated_fingerprint"
                        ],
                    },
                )
                self.assertTrue(terminal["document"]["states"]["home"]["terminal"])
                updated = _post_json(
                    f"{base_url}/api/profiles/demo/undo",
                    {
                        "expected_version": terminal["version"],
                        "expected_fingerprint": terminal["draft_fingerprint"],
                    },
                )
                self.assertFalse(
                    updated["document"]["states"]["home"].get("terminal", False)
                )

                layout = _get_json(
                    f"{base_url}/api/profiles/demo/flow-layout"
                )
                self.assertEqual(layout["version"], 0)
                moved_positions = dict(layout["positions"])
                moved_positions["home"] = {
                    "x": moved_positions["home"]["x"] + 25,
                    "y": moved_positions["home"]["y"] + 30,
                }
                moved = _post_json(
                    f"{base_url}/api/profiles/demo/flow-layout",
                    {
                        "expected_version": layout["version"],
                        "positions": moved_positions,
                    },
                )
                self.assertEqual(moved["version"], 1)
                self.assertTrue(moved["history"]["can_undo"])
                reloaded_catalog = ProfileCatalog(
                    root / "profiles",
                    draft_root=root / "drafts",
                )
                self.assertEqual(
                    reloaded_catalog.get_flow_layout("demo")["positions"],
                    moved["positions"],
                )

                tidy = _post_json(
                    f"{base_url}/api/profiles/demo/flow-layout/tidy",
                    {"expected_version": moved["version"]},
                )
                self.assertEqual(tidy["version"], 2)
                self.assertNotEqual(tidy["positions"], moved["positions"])
                restored = _post_json(
                    f"{base_url}/api/profiles/demo/flow-layout/undo",
                    {"expected_version": tidy["version"]},
                )
                self.assertEqual(restored["positions"], moved["positions"])
                self.assertEqual(
                    profile_path.read_text(encoding="utf-8"),
                    LONG_WAIT_PROFILE_YAML,
                )
            finally:
                server.shutdown()
                server.server_close()


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
