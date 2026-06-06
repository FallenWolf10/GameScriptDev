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
            self.assertTrue(review["timeline"])
            self.assertEqual(review["timeline"][0]["event"], "run_started")
            self.assertEqual(review["timeline"][-1]["event"], "run_completed")

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
