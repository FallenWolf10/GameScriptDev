from __future__ import annotations

import logging
import unittest
from pathlib import Path

import yaml

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.authoring import check_profile_pack
from game_script_dev.engine import Engine
from game_script_dev.profile_loader import load_profile
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import Anchor, ProfileValidationError, validate_profile

PACK_DIR = Path("profiles/neverness_to_everness/fishing_core")
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
        return Screenshot(source=context or "scenario-capture")


class _ScenarioVisionAdapter:
    def __init__(self, scenario: str, current_state: dict[str, str | None]) -> None:
        self.scenario = scenario
        self.current_state = current_state

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        state = self.current_state["name"] or ""
        if anchor.name == "fishing_option_confirmed":
            return state == "fishing_option_confirmed"
        if anchor.name == "preparation_screen_confirmed":
            return state == "preparation_screen_confirmed"
        if anchor.name == "fishing_minigame_visible":
            return state == "fishing_minigame_confirmed" or state.startswith("control_")
        if anchor.name == "target_zone_visible":
            return state.startswith("control_")
        if anchor.name == "cursor_left_of_dead_zone":
            return state == "control_01"
        if anchor.name == "cursor_right_of_dead_zone":
            return state == "control_02"
        if anchor.name == "caught_outcome":
            return self.scenario == "caught" and state == "caught_01"
        if anchor.name == "escaped_outcome":
            return self.scenario == "escaped" and state == "escaped_01"
        if anchor.name == "lost_state_outcome":
            return self.scenario == "lost_state" and state == "lost_01"
        return False

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return None


class _RecordingInputAdapter:
    def __init__(self) -> None:
        self.key_presses: list[tuple[str, float | None]] = []
        self.waits: list[float] = []
        self.cleanup_calls = 0

    def press_key(self, key: str, seconds: float | None = None) -> None:
        self.key_presses.append((key, seconds))

    def wait(self, seconds: float) -> None:
        self.waits.append(seconds)

    def stop_all_continuous_inputs(self) -> None:
        self.cleanup_calls += 1


class FishingCoreProfileTests(unittest.TestCase):
    def test_pack_shape_profile_validation_and_finite_graph(self) -> None:
        result = check_profile_pack(PACK_DIR)
        self.assertTrue(result.ok, result.errors)

        profile = load_profile(PROFILE_PATH)
        validate_profile(profile, PACK_DIR)

        self.assertFalse(profile.allow_infinite_run)
        self.assertEqual(profile.initial_state, "fishing_option_confirmed")
        self.assertEqual(
            [name for name in profile.states if name.startswith("control_")],
            ["control_01", "control_02", "control_03", "control_exhausted"],
        )
        self.assertEqual(profile.states["caught_01"].result, "caught")
        self.assertEqual(profile.states["escaped_01"].result, "escaped")
        self.assertEqual(profile.states["lost_01"].result, "lost_state")

    def test_invalid_example_rejects_unbounded_loop(self) -> None:
        invalid_path = (
            PACK_DIR / "validation_examples" / "invalid" / "unbounded_control.yaml"
        )
        profile = load_profile(invalid_path)

        with self.assertRaises(ProfileValidationError):
            validate_profile(profile, invalid_path.parent)

    def test_scenario_matrix_matches_expected_outcomes(self) -> None:
        matrix_path = (
            PACK_DIR / "validation_examples" / "valid" / "scenario_matrix.yaml"
        )
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))

        self.assertEqual(
            {
                name: details["expected_result"]
                for name, details in matrix["scenarios"].items()
            },
            {
                "caught": "caught",
                "escaped": "escaped",
                "lost_state": "lost_state",
                "retry_failure": "failed_control_timeout",
                "operator_stop": "operator_stopped",
            },
        )

    def test_caught_path_corrects_right_then_terminates(self) -> None:
        result, states, inputs, events = self._run_scenario("caught")

        self.assertEqual(result, "caught")
        self.assertEqual(
            states[:5],
            [
                "fishing_option_confirmed",
                "preparation_screen_confirmed",
                "fishing_minigame_confirmed",
                "control_01",
                "caught_01",
            ],
        )
        self.assertEqual(inputs.key_presses, [("right", 0.08)])
        self.assertEqual(inputs.cleanup_calls, 1)
        self.assertTrue(any(event["event"] == "finished" for event in events))

    def test_escaped_path_uses_failure_transition(self) -> None:
        result, states, inputs, _events = self._run_scenario("escaped")

        self.assertEqual(result, "escaped")
        self.assertIn("caught_01", states)
        self.assertIn("escaped_01", states)
        self.assertEqual(inputs.key_presses, [("right", 0.08)])
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_lost_state_path_is_terminal(self) -> None:
        result, states, inputs, _events = self._run_scenario("lost_state")

        self.assertEqual(result, "lost_state")
        self.assertIn("caught_01", states)
        self.assertIn("escaped_01", states)
        self.assertIn("lost_01", states)
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_retry_failure_is_bounded_and_cleans_up(self) -> None:
        result, states, inputs, events = self._run_scenario("retry_failure")

        self.assertEqual(result, "failed_control_timeout")
        self.assertIn("control_03", states)
        self.assertEqual(states[-1], "control_exhausted")
        caught_failures = [
            event
            for event in events
            if event["event"] == "state_failed" and event["state"] == "caught_01"
        ]
        self.assertEqual(
            [event["failure_count"] for event in caught_failures],
            [1, 2],
        )
        self.assertEqual(inputs.key_presses, [("right", 0.08), ("left", 0.08)])
        self.assertEqual(inputs.cleanup_calls, 1)

    def test_operator_stop_during_control_cleans_up(self) -> None:
        stop = {"requested": False}

        def on_event(event: dict[str, object]) -> None:
            if event["event"] == "state_started" and event["state"] == "control_01":
                stop["requested"] = True

        result, states, inputs, _events = self._run_scenario(
            "caught",
            additional_event_handler=on_event,
            stop_requested=lambda: stop["requested"],
        )

        self.assertEqual(result, "operator_stopped")
        self.assertEqual(states[-1], "control_01")
        self.assertEqual(inputs.key_presses, [])
        self.assertEqual(inputs.cleanup_calls, 1)

    def _run_scenario(
        self,
        scenario: str,
        *,
        additional_event_handler=None,  # noqa: ANN001
        stop_requested=None,  # noqa: ANN001
    ) -> tuple[
        str,
        list[str],
        _RecordingInputAdapter,
        list[dict[str, object]],
    ]:
        profile = load_profile(PROFILE_PATH)
        current_state: dict[str, str | None] = {"name": None}
        events: list[dict[str, object]] = []
        inputs = _RecordingInputAdapter()
        window = TargetWindow(
            title="Safe Fishing Core Scenario",
            process_name=None,
            left=0,
            top=0,
            width=1280,
            height=720,
        )
        runtime = RuntimeContext(
            mode="test",
            window=window,
            window_adapter=_WindowAdapter(),
            screen_adapter=_ScenarioScreenAdapter(),
            vision_adapter=_ScenarioVisionAdapter(scenario, current_state),
            input_adapter=inputs,
        )

        def runtime_factory(profile, mode, logger, artifact_dir, profile_dir):  # noqa: ANN001
            return runtime

        def on_event(event: dict[str, object]) -> None:
            events.append(event)
            if event["event"] == "state_started":
                current_state["name"] = str(event["state"])
            if additional_event_handler is not None:
                additional_event_handler(event)

        result = Engine(
            profile=profile,
            mode="test",
            logger=logging.getLogger(f"fishing-core-{scenario}"),
            runtime_factory=runtime_factory,
            sleeper=lambda _seconds: None,
            event_handler=on_event,
            stop_requested=stop_requested,
        ).run()
        states = [
            str(event["state"])
            for event in events
            if event["event"] == "state_started"
        ]
        return result, states, inputs, events


if __name__ == "__main__":
    unittest.main()
