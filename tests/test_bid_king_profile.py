from __future__ import annotations

import logging
import unittest
from pathlib import Path

import yaml

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.authoring import check_profile_pack
from game_script_dev.dashboard.readiness import evaluate_readiness
from game_script_dev.engine import Engine
from game_script_dev.profile_loader import load_profile
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import Anchor, ProfileValidationError, validate_profile

PACK_DIR = Path("profiles/neverness_the_everness/bid_king")
PROFILE_PATH = PACK_DIR / "profile.yaml"


class _WindowAdapter:
    def find_target(self, profile):  # noqa: ANN001
        return None

    def prepare_window(self, window, resolution):  # noqa: ANN001
        return None

    def verify_window(self, window, profile):  # noqa: ANN001
        return window


class _ScenarioScreenAdapter:
    def capture(
        self,
        window: TargetWindow,
        context: str | None = None,
    ) -> Screenshot:
        return Screenshot(source=context or "bid-king-scenario-capture")


class _ScenarioVisionAdapter:
    def __init__(self, scenario: str, current_state: dict[str, str | None]) -> None:
        self.scenario = scenario
        self.current_state = current_state

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        state = self.current_state["name"] or ""
        if screenshot.source.startswith("wait-for-"):
            state = screenshot.source.removeprefix("wait-for-")
        if anchor.name == "placeholder_start_visible":
            return self.scenario != "detection_failure" and state == "start"
        if anchor.name == "placeholder_confirmation_visible":
            return state == "confirmation"
        if anchor.name == "placeholder_ready_visible":
            return state == "ready"
        if anchor.name == "placeholder_skip_available":
            if self.scenario == "skip_immediately":
                return state in {"skip_check_01", "skip_01"}
            if self.scenario == "bid_then_skip":
                return state in {"skip_check_02", "skip_02"}
            return False
        if anchor.name == "placeholder_bid_available":
            if self.scenario == "bid_then_skip":
                return state in {"bid_check_01", "bid_01"}
            if self.scenario == "bid_limit":
                return state in {
                    "bid_check_01",
                    "bid_01",
                    "bid_check_02",
                    "bid_02",
                }
            return False
        if anchor.name == "placeholder_select_one_visible":
            return self.scenario in {"bid_then_skip", "bid_limit"} and state.startswith(
                "select_one_"
            )
        if anchor.name == "placeholder_bid_confirm_visible":
            return self.scenario in {"bid_then_skip", "bid_limit"} and state.startswith(
                "bid_confirm_"
            )
        if anchor.name == "placeholder_exit_visible":
            return (
                self.scenario in {"skip_immediately", "bid_then_skip"}
                and state == "exit"
            )
        return False

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return None


class _RecordingInputAdapter:
    def __init__(self) -> None:
        self.clicks: list[tuple[str, str | None]] = []
        self.waits: list[float] = []
        self.cleanup_calls = 0

    def click_region(self, region: str, input_mode: str | None = None) -> None:
        self.clicks.append((region, input_mode))

    def wait(self, seconds: float) -> None:
        self.waits.append(seconds)

    def stop_all_continuous_inputs(self) -> None:
        self.cleanup_calls += 1


class BidKingProfileTests(unittest.TestCase):
    def test_pack_check_and_profile_validation_passes_with_warning(
        self,
    ) -> None:
        result = check_profile_pack(PACK_DIR)
        self.assertTrue(result.ok, result.errors)
        warning_text = " ".join(result.warnings)
        self.assertIn("profile_pack compatibility incomplete", warning_text)

        profile = load_profile(PROFILE_PATH)
        validate_profile(profile, PACK_DIR)

        self.assertIsNotNone(profile.profile_pack)
        self.assertFalse(profile.profile_pack.compatibility_complete)
        self.assertEqual(profile.initial_state, "entry")

    def test_scenario_matrix_documents_the_expected_finite_outcomes(self) -> None:
        matrix_path = (
            PACK_DIR / "validation_examples" / "valid" / "scenario_matrix.yaml"
        )
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))

        self.assertEqual(matrix["safety_bounds"]["rounds"], 1)
        self.assertEqual(matrix["safety_bounds"]["bid_cycles"], 2)
        self.assertEqual(matrix["safety_bounds"]["branch_priority"], ["skip", "bid"])
        self.assertEqual(
            {
                name: details["expected_result"]
                for name, details in matrix["scenarios"].items()
            },
            {
                "skip_immediately": "completed",
                "bid_then_skip": "completed",
                "bid_limit": "failed_bid_limit_reached",
                "detection_failure": "failed_detection_or_action",
            },
        )

    def test_state_graph_shape_and_terminal_reachability(self) -> None:
        profile = load_profile(PROFILE_PATH)
        expected_states = {
            "entry",
            "round_01",
            "start",
            "confirmation",
            "ready",
            "bid_or_skip_01",
            "skip_check_01",
            "skip_01",
            "bid_check_01",
            "bid_01",
            "select_one_01",
            "bid_confirm_01",
            "bid_or_skip_02",
            "skip_check_02",
            "skip_02",
            "bid_check_02",
            "bid_02",
            "select_one_02",
            "bid_confirm_02",
            "exit",
            "round_complete",
            "bid_limit_reached",
            "failure",
        }
        self.assertEqual(set(profile.states), expected_states)

        reachable = self._reachable_states(profile)
        self.assertEqual(reachable, expected_states)
        self.assertEqual(profile.states["round_complete"].result, "completed")
        self.assertEqual(
            profile.states["bid_limit_reached"].result,
            "failed_bid_limit_reached",
        )
        self.assertEqual(
            profile.states["failure"].result,
            "failed_detection_or_action",
        )
        self.assertEqual(profile.states["skip_check_01"].on_failure, "bid_check_01")
        self.assertEqual(profile.states["skip_check_02"].on_failure, "bid_check_02")
        self.assertEqual(
            profile.states["bid_confirm_01"].on_success,
            "bid_or_skip_02",
        )
        self.assertEqual(
            profile.states["bid_confirm_02"].on_success,
            "bid_limit_reached",
        )
        self.assertEqual(profile.states["exit"].on_success, "round_complete")

    def test_round_bid_retry_wait_and_timeout_bounds_are_explicit(self) -> None:
        profile = load_profile(PROFILE_PATH)

        self.assertFalse(profile.allow_infinite_run)
        self.assertEqual(profile.max_retries, 1)
        self.assertEqual(profile.default_timeout_seconds, 1)
        authored_rounds = [
            name
            for name in profile.states
            if name.startswith("round_") and name != "round_complete"
        ]
        self.assertEqual(authored_rounds, ["round_01"])
        self.assertEqual(
            [name for name in profile.states if name.startswith("bid_or_skip_")],
            ["bid_or_skip_01", "bid_or_skip_02"],
        )
        self.assertEqual(
            [name for name in profile.states if name.startswith("bid_check_")],
            ["bid_check_01", "bid_check_02"],
        )
        self.assertEqual(
            [name for name in profile.states if name.startswith("bid_")],
            [
                "bid_or_skip_01",
                "bid_check_01",
                "bid_01",
                "bid_confirm_01",
                "bid_or_skip_02",
                "bid_check_02",
                "bid_02",
                "bid_confirm_02",
                "bid_limit_reached",
            ],
        )
        self.assertEqual(profile.interruptions, [])

        wait_seconds: list[float] = []
        timeout_seconds: list[float] = []
        poll_seconds: list[float] = []
        for state in profile.states.values():
            for action in state.actions:
                if action.type == "wait":
                    wait_seconds.append(float(action.data["seconds"]))
                if action.type == "wait_for_state":
                    timeout_seconds.append(float(action.data["timeout_seconds"]))
                    poll_seconds.append(float(action.data["poll_interval_seconds"]))

        self.assertTrue(wait_seconds)
        self.assertTrue(timeout_seconds)
        self.assertTrue(poll_seconds)
        self.assertTrue(all(0 < seconds <= 0.1 for seconds in wait_seconds))
        self.assertTrue(all(0 < seconds <= 1 for seconds in timeout_seconds))
        self.assertTrue(all(0 < seconds <= 0.1 for seconds in poll_seconds))

    def test_pack_local_invalid_examples_fail_for_the_intended_reason(self) -> None:
        expected_fragments = {
            "missing_asset.yaml": (
                "template anchor asset missing: assets/not_present.ppm"
            ),
            "unknown_transition.yaml": (
                "state 'home' on_success references unknown state 'missing_state'"
            ),
            "unsupported_action.yaml": "uses unknown action type",
            "unbounded_control.yaml": "has no path to a terminal state",
        }
        invalid_dir = PACK_DIR / "validation_examples" / "invalid"

        for filename, fragment in expected_fragments.items():
            profile_path = invalid_dir / filename
            with self.subTest(profile_path=profile_path):
                profile = load_profile(profile_path)
                with self.assertRaises(ProfileValidationError) as captured:
                    validate_profile(profile, profile_path.parent)
                self.assertIn(fragment, str(captured.exception))

    def test_dashboard_readiness_is_blocked_by_incomplete_compatibility(self) -> None:
        report = evaluate_readiness(
            "neverness_the_everness__bid_king",
            PROFILE_PATH,
            last_dry_run_success=True,
            check_target=False,
        )

        self.assertTrue(report.valid)
        self.assertFalse(report.live_available)
        self.assertEqual(report.compatibility_status, "incomplete")
        self.assertEqual(len(report.blockers), 1)
        blocker = report.blockers[0]
        for missing_check in (
            "interruption_recovery",
            "required_assets",
            "successful_validation_or_dry_run",
            "supported_resolution",
            "target_identity",
        ):
            self.assertIn(missing_check, blocker)

    def test_skip_is_selected_before_bid_when_both_paths_are_possible(self) -> None:
        result, states, inputs = self._run_scenario("skip_immediately")

        self.assertEqual(result, "completed")
        self.assertIn("skip_check_01", states)
        self.assertIn("skip_01", states)
        self.assertNotIn("bid_check_01", states)
        self.assertNotIn("bid_01", states)
        self.assertEqual(
            [region for region, _mode in inputs.clicks],
            [
                "placeholder_start_click",
                "placeholder_confirmation_click",
                "placeholder_skip_click",
                "placeholder_exit_click",
            ],
        )
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_one_bid_returns_to_branch_then_skip_completes_the_round(self) -> None:
        result, states, inputs = self._run_scenario("bid_then_skip")

        self.assertEqual(result, "completed")
        expected_order = [
            "skip_check_01",
            "bid_check_01",
            "bid_01",
            "select_one_01",
            "bid_confirm_01",
            "bid_or_skip_02",
            "skip_check_02",
            "skip_02",
            "exit",
            "round_complete",
        ]
        positions = [states.index(state_name) for state_name in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(
            [region for region, _mode in inputs.clicks],
            [
                "placeholder_start_click",
                "placeholder_confirmation_click",
                "placeholder_bid_click",
                "placeholder_select_one_click",
                "placeholder_bid_confirm_click",
                "placeholder_skip_click",
                "placeholder_exit_click",
            ],
        )
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_two_bid_cycles_end_at_the_explicit_safety_cap(self) -> None:
        result, states, inputs = self._run_scenario("bid_limit")

        self.assertEqual(result, "failed_bid_limit_reached")
        self.assertEqual(states[-1], "bid_limit_reached")
        self.assertEqual(states.count("bid_01"), 1)
        self.assertEqual(states.count("bid_02"), 1)
        self.assertNotIn("exit", states)
        self.assertEqual(
            [region for region, _mode in inputs.clicks],
            [
                "placeholder_start_click",
                "placeholder_confirmation_click",
                "placeholder_bid_click",
                "placeholder_select_one_click",
                "placeholder_bid_confirm_click",
                "placeholder_bid_click",
                "placeholder_select_one_click",
                "placeholder_bid_confirm_click",
            ],
        )
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_missing_start_anchor_reaches_failure_after_one_attempt(self) -> None:
        result, states, inputs = self._run_scenario("detection_failure")

        self.assertEqual(result, "failed_detection_or_action")
        self.assertEqual(states.count("start"), 1)
        self.assertEqual(states[-1], "failure")
        self.assertEqual(inputs.clicks, [])
        self.assertEqual(inputs.cleanup_calls, 1)

    @staticmethod
    def _reachable_states(profile) -> set[str]:  # noqa: ANN001
        reachable = {profile.initial_state}
        pending = [profile.initial_state]
        while pending:
            state = profile.states[pending.pop()]
            successors = [state.on_success, state.on_failure]
            for successor in successors:
                if successor in profile.states and successor not in reachable:
                    reachable.add(successor)
                    pending.append(successor)
        return reachable

    def _run_scenario(
        self,
        scenario: str,
    ) -> tuple[str, list[str], _RecordingInputAdapter]:
        profile = load_profile(PROFILE_PATH)
        current_state: dict[str, str | None] = {"name": None}
        events: list[dict[str, object]] = []
        inputs = _RecordingInputAdapter()
        window = TargetWindow(
            title="Safe Bid King Scenario",
            process_name=None,
            left=0,
            top=0,
            width=64,
            height=64,
        )
        runtime = RuntimeContext(
            mode="test",
            window=window,
            window_adapter=_WindowAdapter(),
            screen_adapter=_ScenarioScreenAdapter(),
            vision_adapter=_ScenarioVisionAdapter(scenario, current_state),
            input_adapter=inputs,
        )

        def runtime_factory(  # noqa: ANN001
            profile, mode, logger, artifact_dir, profile_dir
        ):
            return runtime

        def on_event(event: dict[str, object]) -> None:
            events.append(event)
            if event["event"] == "state_started":
                current_state["name"] = str(event["state"])

        result = Engine(
            profile=profile,
            mode="test",
            logger=logging.getLogger(f"bid-king-{scenario}"),
            runtime_factory=runtime_factory,
            sleeper=lambda _seconds: None,
            event_handler=on_event,
        ).run()
        states = [
            str(event["state"]) for event in events if event["event"] == "state_started"
        ]
        return result, states, inputs


if __name__ == "__main__":
    unittest.main()
