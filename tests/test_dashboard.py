from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from game_script_dev.dashboard.profile_catalog import ProfileCatalog
from game_script_dev.dashboard.readiness import evaluate_readiness
from game_script_dev.dashboard.run_registry import RunRegistry
from game_script_dev.dashboard.server import create_server


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


def _write_profile(root: Path, contents: str = PROFILE_YAML) -> Path:
    profile_dir = root / "profiles" / "demo"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "profile.yaml"
    profile_path.write_text(contents, encoding="utf-8")
    return profile_path


def _wait_for_run(registry: RunRegistry, run_id: str) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = registry.get_run(run_id)
        if record.status in {"completed", "failed"}:
            return
        time.sleep(0.01)
    raise AssertionError("run did not finish")


def _get_json(url: str) -> dict[str, object]:
    return json.loads(urlopen(url, timeout=5).read())


if __name__ == "__main__":
    unittest.main()
