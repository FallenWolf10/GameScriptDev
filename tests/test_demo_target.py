from __future__ import annotations

import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.demo_target import (
    COMPLETION_SIGNAL,
    DAILY_SIGNAL,
    HOME_SIGNAL,
    INTERRUPTION_SIGNAL,
    KNOWN_FAILURE_SIGNAL,
    STATE_COMPLETION,
    STATE_DAILY_MENU,
    STATE_HOME,
    STATE_INTERRUPTION,
    STATE_KNOWN_FAILURE,
    DemoTargetModel,
)
from game_script_dev.dashboard.readiness import evaluate_readiness


class DemoTargetModelTests(unittest.TestCase):
    def test_starts_on_home_signal(self) -> None:
        model = DemoTargetModel()

        self.assertEqual(model.state, STATE_HOME)
        self.assertEqual(model.signal, HOME_SIGNAL)

    def test_clicking_daily_region_opens_daily_menu(self) -> None:
        model = DemoTargetModel()

        model.click(640, 420)

        self.assertEqual(model.state, STATE_DAILY_MENU)
        self.assertEqual(model.signal, DAILY_SIGNAL)

    def test_keyboard_flow_reaches_completion(self) -> None:
        model = DemoTargetModel(state=STATE_DAILY_MENU)

        model.key("F")
        model.key("W")

        self.assertEqual(model.state, STATE_COMPLETION)
        self.assertEqual(model.signal, COMPLETION_SIGNAL)

    def test_known_failure_and_interruption_screens_are_controlled(self) -> None:
        model = DemoTargetModel()

        model.key("K")
        self.assertEqual(model.state, STATE_KNOWN_FAILURE)
        self.assertEqual(model.signal, KNOWN_FAILURE_SIGNAL)

        model.key("R")
        model.key("I")
        self.assertEqual(model.state, STATE_INTERRUPTION)
        self.assertEqual(model.signal, INTERRUPTION_SIGNAL)

    def test_module_entrypoint_uses_main_exit_code(self) -> None:
        with patch("game_script_dev.demo_target.main", return_value=7):
            with self.assertRaises(SystemExit) as captured:
                runpy.run_module("game_script_dev.demo_target", run_name="__main__")

        self.assertEqual(captured.exception.code, 7)

    def test_demo_profile_is_live_ready_when_title_target_is_present(self) -> None:
        profile_path = Path("profiles/demo/profile.yaml")

        report = evaluate_readiness(
            "demo",
            profile_path,
            last_dry_run_success=True,
            window_adapter=StaticWindowAdapter(present=True),
        )

        self.assertTrue(report.live_available)
        self.assertEqual(report.target_status, "matched")
        self.assertEqual(report.resolution_status, "ignored")

    def test_demo_profile_is_blocked_when_title_target_is_absent(self) -> None:
        profile_path = Path("profiles/demo/profile.yaml")

        report = evaluate_readiness(
            "demo",
            profile_path,
            last_dry_run_success=True,
            window_adapter=StaticWindowAdapter(present=False),
        )

        self.assertFalse(report.live_available)
        self.assertEqual(report.target_status, "missing")
        self.assertIn("target window is not running", report.blockers)


class StaticWindowAdapter:
    def __init__(self, present: bool) -> None:
        self.present = present

    def find_target(self, profile: object) -> TargetWindow | None:
        if not self.present:
            return None
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
