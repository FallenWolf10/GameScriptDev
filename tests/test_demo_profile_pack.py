from __future__ import annotations

import unittest
import time
from pathlib import Path

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.dashboard.profile_catalog import ProfileCatalog
from game_script_dev.dashboard.readiness import evaluate_readiness
from game_script_dev.dashboard.run_registry import RunRegistry
from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile

PACK_PROFILE = Path("profiles/demo/local_target/profile.yaml")


class DemoProfilePackTests(unittest.TestCase):
    def test_dashboard_discovers_flat_demo_and_local_target_pack(self) -> None:
        entries = ProfileCatalog(Path("profiles")).list_profiles()
        by_id = {entry.id: entry for entry in entries}

        self.assertIn("demo", by_id)
        self.assertIn("demo__local_target", by_id)
        self.assertEqual(by_id["demo"].path, Path("profiles/demo/profile.yaml"))
        self.assertEqual(by_id["demo__local_target"].path, PACK_PROFILE)
        self.assertTrue(by_id["demo"].valid)
        self.assertTrue(by_id["demo__local_target"].valid)

    def test_local_target_pack_profile_validates(self) -> None:
        profile = load_profile(PACK_PROFILE)

        validate_profile(profile, PACK_PROFILE.parent)

        self.assertIsNotNone(profile.profile_pack)
        self.assertTrue(profile.profile_pack.compatibility_complete)

    def test_local_target_pack_readiness_requires_dashboard_dry_run(self) -> None:
        report = evaluate_readiness(
            "demo__local_target",
            PACK_PROFILE,
            last_dry_run_success=False,
            window_adapter=PresentDemoWindowAdapter(),
        )

        self.assertFalse(report.live_available)
        self.assertEqual(report.compatibility_status, "passed")
        self.assertIn("successful dry-run", " ".join(report.blockers))

    def test_local_target_pack_readiness_passes_after_dry_run_and_target(self) -> None:
        report = evaluate_readiness(
            "demo__local_target",
            PACK_PROFILE,
            last_dry_run_success=True,
            window_adapter=PresentDemoWindowAdapter(),
        )

        self.assertTrue(report.live_available)
        self.assertEqual(report.compatibility_status, "passed")
        self.assertEqual(report.target_status, "matched")
        self.assertEqual(report.resolution_status, "ignored")

    def test_local_target_pack_readiness_can_be_checked_without_os_target(self) -> None:
        report = evaluate_readiness(
            "demo__local_target",
            PACK_PROFILE,
            last_dry_run_success=True,
            check_target=False,
        )

        self.assertTrue(report.live_available)
        self.assertEqual(report.compatibility_status, "passed")
        self.assertEqual(report.blockers, [])

    def test_local_target_pack_dry_run_evidence_is_profile_id_specific(self) -> None:
        registry = RunRegistry(Path("logs/test-demo-profile-pack"))

        record = registry.start_run("demo__local_target", PACK_PROFILE, "dry-run")
        self._wait_for_run(registry, record.id)

        self.assertTrue(registry.last_dry_run_success("demo__local_target"))
        self.assertFalse(registry.last_dry_run_success("demo"))

    def test_local_target_pack_complete_checklist_example_validates(self) -> None:
        profile_path = Path(
            "profiles/demo/local_target/validation_examples/valid/"
            "complete_checklist.yaml"
        )
        profile = load_profile(profile_path)

        validate_profile(profile, profile_path.parent)

    def test_local_target_pack_incomplete_but_valid_checklist_blocks_live(self) -> None:
        profile_path = Path(
            "profiles/demo/local_target/validation_examples/valid/"
            "incomplete_checklist.yaml"
        )
        profile = load_profile(profile_path)

        validate_profile(profile, profile_path.parent)
        report = evaluate_readiness(
            "demo__local_target",
            profile_path,
            last_dry_run_success=True,
            check_target=False,
        )

        self.assertFalse(report.live_available)
        self.assertEqual(report.compatibility_status, "incomplete")
        self.assertIn("successful_validation_or_dry_run", " ".join(report.blockers))

    def test_local_target_pack_incomplete_checklist_example_fails(self) -> None:
        profile_path = Path(
            "profiles/demo/local_target/validation_examples/invalid/"
            "incomplete_checklist.yaml"
        )
        profile = load_profile(profile_path)

        with self.assertRaises(ProfileValidationError) as captured:
            validate_profile(profile, profile_path.parent)

        self.assertIn(
            "profile_pack.compatibility.successful_validation_or_dry_run is required",
            str(captured.exception),
        )

    def _wait_for_run(self, registry: RunRegistry, run_id: str) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            record = registry.get_run(run_id)
            if record.status in {"completed", "failed"}:
                self.assertEqual(record.status, "completed", record.failure_reason)
                return
            time.sleep(0.01)
        raise AssertionError("run did not finish")


class PresentDemoWindowAdapter:
    def find_target(self, profile: object) -> TargetWindow:
        return TargetWindow(
            title="Demo Automation Window",
            process_name="python.exe",
            left=0,
            top=0,
            width=1296,
            height=759,
            handle=100,
            process_id=200,
        )


if __name__ == "__main__":
    unittest.main()
