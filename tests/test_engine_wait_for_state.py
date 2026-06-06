from __future__ import annotations

import io
import logging
import unittest
from unittest.mock import patch

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.engine import Engine
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import (
    Action,
    Anchor,
    Profile,
    Resolution,
    State,
    Target,
)


class StaticWindowAdapter:
    def find_target(self, profile: Profile) -> TargetWindow:
        return TargetWindow("test", "test.exe", 0, 0, 1280, 720)

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        return None


class SequencedScreenAdapter:
    def __init__(self) -> None:
        self.capture_count = 0

    def capture(self, window: TargetWindow) -> Screenshot:
        self.capture_count += 1
        return Screenshot(source=f"capture-{self.capture_count}")


class RecordingScreenAdapter:
    def __init__(self) -> None:
        self.contexts: list[str | None] = []

    def capture(
        self,
        window: TargetWindow,
        context: str | None = None,
    ) -> Screenshot:
        self.contexts.append(context)
        return Screenshot(source=f"capture-{len(self.contexts)}")


class ExplodingScreenAdapter:
    def capture(
        self,
        window: TargetWindow,
        context: str | None = None,
    ) -> Screenshot:
        raise AssertionError(f"unexpected capture: {context}")


class SequencedVisionAdapter:
    def __init__(self, ready_after_capture: int | None) -> None:
        self.ready_after_capture = ready_after_capture

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        capture_number = int(screenshot.source.split("-")[1])
        if anchor.name == "home_title":
            return True
        if self.ready_after_capture is None:
            return False
        return capture_number >= self.ready_after_capture

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return None


class NoInputAdapter:
    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        return None

    def click_region(self, region_name: str, input_mode: str | None = None) -> None:
        return None

    def hold_click(
        self,
        region_name: str,
        seconds: float,
        input_mode: str | None = None,
    ) -> None:
        return None

    def press_key(self, key: str, seconds: float | None = None) -> None:
        return None

    def press_keys(self, keys: list[str], seconds: float | None = None) -> None:
        return None

    def hold_key(self, key: str, seconds: float) -> None:
        return None

    def hold_keys(self, keys: list[str], seconds: float) -> None:
        return None

    def repeat_key(
        self,
        key: str,
        repeat_for_seconds: float,
        repeat_every_seconds: float,
        tap_duration_seconds: float | None = None,
    ) -> None:
        return None

    def hold_key_while_repeating_key(
        self,
        hold_key: str,
        hold_seconds: float,
        tap_key: str,
        tap_every_seconds: float,
        tap_duration_seconds: float | None = None,
    ) -> None:
        return None

    def move_mouse(
        self,
        dx: float,
        dy: float,
        seconds: float | None = None,
        input_mode: str | None = None,
    ) -> None:
        return None

    def hold_mouse_button_and_move(
        self,
        button: str,
        dx: float,
        dy: float,
        seconds: float | None = None,
        input_mode: str | None = None,
    ) -> None:
        return None

    def scroll_mouse(
        self,
        direction: str,
        steps: int = 1,
        input_mode: str | None = None,
    ) -> None:
        return None

    def start_continuous_input(
        self,
        name: str,
        action_type: str,
        data: dict[str, object],
    ) -> None:
        return None

    def stop_continuous_input(self, name: str) -> None:
        return None

    def stop_all_continuous_inputs(self) -> None:
        return None

    def wait(self, seconds: float) -> None:
        return None


class RecordingInputAdapter(NoInputAdapter):
    def __init__(self) -> None:
        self.actions: list[tuple[object, ...]] = []

    def click_region(self, region_name: str, input_mode: str | None = None) -> None:
        self.actions.append(("click_region", region_name, input_mode))

    def hold_click(
        self,
        region_name: str,
        seconds: float,
        input_mode: str | None = None,
    ) -> None:
        self.actions.append(("hold_click", region_name, seconds, input_mode))

    def press_key(self, key: str, seconds: float | None = None) -> None:
        if seconds is None:
            self.actions.append(("press_key", key))
            return
        self.actions.append(("press_key", key, seconds))

    def press_keys(self, keys: list[str], seconds: float | None = None) -> None:
        if seconds is None:
            self.actions.append(("press_keys", tuple(keys)))
            return
        self.actions.append(("press_keys", tuple(keys), seconds))

    def hold_keys(self, keys: list[str], seconds: float) -> None:
        self.actions.append(("hold_keys", tuple(keys), seconds))

    def repeat_key(
        self,
        key: str,
        repeat_for_seconds: float,
        repeat_every_seconds: float,
        tap_duration_seconds: float | None = None,
    ) -> None:
        if tap_duration_seconds is None:
            self.actions.append(
                ("repeat_key", key, repeat_for_seconds, repeat_every_seconds)
            )
            return
        self.actions.append(
            (
                "repeat_key",
                key,
                repeat_for_seconds,
                repeat_every_seconds,
                tap_duration_seconds,
            )
        )

    def hold_key_while_repeating_key(
        self,
        hold_key: str,
        hold_seconds: float,
        tap_key: str,
        tap_every_seconds: float,
        tap_duration_seconds: float | None = None,
    ) -> None:
        if tap_duration_seconds is None:
            self.actions.append(
                (
                    "hold_key_while_repeating_key",
                    hold_key,
                    hold_seconds,
                    tap_key,
                    tap_every_seconds,
                )
            )
            return
        self.actions.append(
            (
                "hold_key_while_repeating_key",
                hold_key,
                hold_seconds,
                tap_key,
                tap_every_seconds,
                tap_duration_seconds,
            )
        )

    def move_mouse(
        self,
        dx: float,
        dy: float,
        seconds: float | None = None,
        input_mode: str | None = None,
    ) -> None:
        if seconds is None:
            self.actions.append(("move_mouse", dx, dy, input_mode))
            return
        self.actions.append(("move_mouse", dx, dy, seconds, input_mode))

    def hold_mouse_button_and_move(
        self,
        button: str,
        dx: float,
        dy: float,
        seconds: float | None = None,
        input_mode: str | None = None,
    ) -> None:
        if seconds is None:
            self.actions.append(
                ("hold_mouse_button_and_move", button, dx, dy, input_mode)
            )
            return
        self.actions.append(
            ("hold_mouse_button_and_move", button, dx, dy, seconds, input_mode)
        )

    def scroll_mouse(
        self,
        direction: str,
        steps: int = 1,
        input_mode: str | None = None,
    ) -> None:
        self.actions.append(("scroll_mouse", direction, steps, input_mode))

    def start_continuous_input(
        self,
        name: str,
        action_type: str,
        data: dict[str, object],
    ) -> None:
        self.actions.append(
            (
                "start_continuous_input",
                name,
                action_type,
                tuple(sorted(data.items())),
            )
        )

    def stop_continuous_input(self, name: str) -> None:
        self.actions.append(("stop_continuous_input", name))

    def stop_all_continuous_inputs(self) -> None:
        self.actions.append(("stop_all_continuous_inputs",))


def runtime_factory(ready_after_capture: int | None):
    def factory(
        _profile: Profile,
        _mode: str,
        _logger: logging.Logger,
        _artifact_dir: object,
        _profile_dir: object,
    ) -> RuntimeContext:
        window = TargetWindow("test", "test.exe", 0, 0, 1280, 720)
        return RuntimeContext(
            mode="live",
            window=window,
            window_adapter=StaticWindowAdapter(),
            screen_adapter=SequencedScreenAdapter(),
            vision_adapter=SequencedVisionAdapter(ready_after_capture),
            input_adapter=NoInputAdapter(),
        )

    return factory


def runtime_factory_for_action_only(input_adapter: RecordingInputAdapter):
    def factory(
        _profile: Profile,
        _mode: str,
        _logger: logging.Logger,
        _artifact_dir: object,
        _profile_dir: object,
    ) -> RuntimeContext:
        window = TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=100)
        return RuntimeContext(
            mode="live",
            window=window,
            window_adapter=StaticWindowAdapter(),
            screen_adapter=ExplodingScreenAdapter(),
            vision_adapter=SequencedVisionAdapter(ready_after_capture=None),
            input_adapter=input_adapter,
        )

    return factory


def runtime_factory_with_screen(screen_adapter: RecordingScreenAdapter):
    def factory(
        _profile: Profile,
        _mode: str,
        _logger: logging.Logger,
        _artifact_dir: object,
        _profile_dir: object,
    ) -> RuntimeContext:
        window = TargetWindow("test", "test.exe", 0, 0, 1280, 720)
        return RuntimeContext(
            mode="live",
            window=window,
            window_adapter=StaticWindowAdapter(),
            screen_adapter=screen_adapter,
            vision_adapter=SequencedVisionAdapter(ready_after_capture=1),
            input_adapter=NoInputAdapter(),
        )

    return factory


def profile_for_wait(timeout_seconds: float) -> Profile:
    return Profile(
        version=1,
        name="Wait Profile",
        target=Target(process_name="test.exe"),
        resolution=Resolution(width=1280, height=720),
        initial_state="home",
        max_retries=1,
        states={
            "home": State(
                name="home",
                required_anchors=[Anchor(name="home_title", type="text", text="Home")],
                actions=[
                    Action(
                        type="wait_for_state",
                        data={
                            "state": "done",
                            "timeout_seconds": timeout_seconds,
                            "poll_interval_seconds": 0,
                        },
                    )
                ],
                on_success="done",
            ),
            "done": State(
                name="done",
                required_anchors=[Anchor(name="done_title", type="text", text="Done")],
                terminal=True,
                result="success",
            ),
        },
    )


def terminal_profile() -> Profile:
    return Profile(
        version=1,
        name="Terminal Profile",
        target=Target(process_name="test.exe"),
        resolution=Resolution(width=1280, height=720),
        initial_state="done",
        max_retries=1,
        states={
            "done": State(
                name="done",
                required_anchors=[Anchor(name="done_title", type="text", text="Done")],
                terminal=True,
                result="success",
            ),
        },
    )


def stop_profile() -> Profile:
    return Profile(
        version=1,
        name="Stop Profile",
        target=Target(process_name="test.exe"),
        resolution=Resolution(width=1280, height=720),
        initial_state="home",
        max_retries=1,
        states={
            "home": State(
                name="home",
                required_anchors=[Anchor(name="home_title", type="text", text="Home")],
                actions=[Action(type="stop", data={"result": "operator_stopped"})],
            ),
        },
    )


def action_only_profile() -> Profile:
    return Profile(
        version=1,
        name="Action Only Profile",
        target=Target(process_name="test.exe", input_mode="background_window_messages"),
        resolution=Resolution(width=1280, height=720),
        initial_state="startup_sequence",
        max_retries=1,
        regions={},
        states={
            "startup_sequence": State(
                name="startup_sequence",
                actions=[
                    Action(
                        type="click_point",
                        data={
                            "region": "startup_click",
                            "input_mode": "foreground",
                        },
                    ),
                    Action(
                        type="hold_click",
                        data={
                            "region": "startup_click",
                            "seconds": 1.25,
                            "input_mode": "foreground",
                        },
                    ),
                    Action(type="click_point", data={"region": "startup_click"}),
                    Action(type="press_key", data={"key": "2", "seconds": 0.2}),
                    Action(type="hold_keys", data={"keys": ["shift", "w"], "seconds": 0.5}),
                    Action(type="press_keys", data={"keys": ["ctrl", "c"]}),
                    Action(
                        type="repeat_key",
                        data={
                            "key": "space",
                            "repeat_for_seconds": 1.0,
                            "repeat_every_seconds": 0.25,
                            "tap_duration_seconds": 0.05,
                        },
                    ),
                    Action(
                        type="move_mouse",
                        data={"dx": 120, "dy": -30, "seconds": 0.2, "input_mode": "foreground"},
                    ),
                    Action(
                        type="hold_mouse_button_and_move",
                        data={
                            "button": "right",
                            "dx": 40,
                            "dy": 10,
                            "seconds": 0.1,
                            "input_mode": "foreground",
                        },
                    ),
                    Action(
                        type="scroll_mouse",
                        data={
                            "direction": "down",
                            "steps": 2,
                            "input_mode": "foreground",
                        },
                    ),
                    Action(
                        type="start_continuous_input",
                        data={
                            "name": "forward_motion",
                            "action": "hold_key",
                            "key": "w",
                        },
                    ),
                    Action(
                        type="hold_key_while_repeating_key",
                        data={
                            "hold_key": "w",
                            "hold_seconds": 2.0,
                            "tap_key": "space",
                            "tap_every_seconds": 0.5,
                            "tap_duration_seconds": 0.1,
                        },
                    ),
                    Action(type="stop_continuous_input", data={"name": "forward_motion"}),
                    Action(type="press_key", data={"key": "e"}),
                ],
                on_success="complete",
                on_failure="failed",
            ),
            "complete": State(
                name="complete",
                terminal=True,
                result="success",
            ),
            "failed": State(
                name="failed",
                terminal=True,
                result="failed_known_screen",
            ),
        },
    )


def quiet_logger(name: str) -> logging.Logger:
    test_logger = logging.getLogger(name)
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())
    test_logger.propagate = False
    return test_logger


def capture_logger(name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    test_logger = logging.getLogger(name)
    test_logger.handlers.clear()
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False
    return test_logger, stream


class EngineWaitForStateTests(unittest.TestCase):
    def test_wait_for_state_polls_until_anchor_is_present(self) -> None:
        slept: list[float] = []

        result = Engine(
            profile=profile_for_wait(timeout_seconds=1),
            mode="live",
            logger=quiet_logger("tests.wait_success"),
            runtime_factory=runtime_factory(ready_after_capture=3),
            sleeper=slept.append,
        ).run()

        self.assertEqual(result, "success")
        self.assertEqual(slept, [0.05])

    def test_wait_for_state_times_out(self) -> None:
        result = Engine(
            profile=profile_for_wait(timeout_seconds=0),
            mode="live",
            logger=quiet_logger("tests.wait_timeout"),
            runtime_factory=runtime_factory(ready_after_capture=None),
        ).run()

        self.assertEqual(result, "failed_home")

    def test_wait_for_state_logs_elapsed_wait_time_on_success(self) -> None:
        logger, stream = capture_logger("tests.wait_elapsed")

        with patch(
            "game_script_dev.engine.time.monotonic",
            side_effect=[10.0, 10.02, 10.08, 10.10, 10.12, 10.14, 10.16, 10.18],
        ):
            result = Engine(
                profile=profile_for_wait(timeout_seconds=1),
                mode="live",
                logger=logger,
                runtime_factory=runtime_factory(ready_after_capture=2),
                sleeper=lambda _seconds: None,
            ).run()

        self.assertEqual(result, "success")
        self.assertIn(
            "Wait for state succeeded after 0.06 seconds: done",
            stream.getvalue(),
        )

    def test_initial_state_logs_anchor_confirmation_time(self) -> None:
        logger, stream = capture_logger("tests.initial_state_elapsed")

        with patch(
            "game_script_dev.engine.time.monotonic",
            side_effect=[20.0, 20.03],
        ):
            result = Engine(
                profile=terminal_profile(),
                mode="live",
                logger=logger,
                runtime_factory=runtime_factory(ready_after_capture=1),
            ).run()

        self.assertEqual(result, "success")
        self.assertIn(
            "State 'done' confirmed after 0.03 seconds using anchors: done_title",
            stream.getvalue(),
        )

    def test_live_terminal_success_captures_final_screenshot(self) -> None:
        screen_adapter = RecordingScreenAdapter()

        result = Engine(
            profile=terminal_profile(),
            mode="live",
            logger=quiet_logger("tests.terminal_success"),
            runtime_factory=runtime_factory_with_screen(screen_adapter),
        ).run()

        self.assertEqual(result, "success")
        self.assertEqual(
            screen_adapter.contexts,
            ["state-done-confirm", "final-state-done-success"],
        )

    def test_live_stop_action_captures_final_screenshot(self) -> None:
        screen_adapter = RecordingScreenAdapter()
        events: list[dict[str, object]] = []

        result = Engine(
            profile=stop_profile(),
            mode="live",
            logger=quiet_logger("tests.stop_success"),
            runtime_factory=runtime_factory_with_screen(screen_adapter),
            event_handler=events.append,
        ).run()

        self.assertEqual(result, "operator_stopped")
        self.assertEqual(
            screen_adapter.contexts,
            ["state-home-confirm", "final-state-home-stop-operator_stopped"],
        )
        self.assertEqual(
            [event["event"] for event in events],
            ["state_started", "action_started", "action_completed"],
        )
        self.assertEqual(events[1]["action_type"], "stop")
        self.assertEqual(events[1]["action_summary"], "stop operator_stopped")
        self.assertEqual(events[2]["result"], "operator_stopped")

    def test_action_only_live_profile_runs_without_screenshots(self) -> None:
        input_adapter = RecordingInputAdapter()

        result = Engine(
            profile=action_only_profile(),
            mode="live",
            logger=quiet_logger("tests.action_only_no_capture"),
            runtime_factory=runtime_factory_for_action_only(input_adapter),
        ).run()

        self.assertEqual(result, "success")
        self.assertEqual(
            input_adapter.actions,
            [
                ("click_region", "startup_click", "foreground"),
                ("hold_click", "startup_click", 1.25, "foreground"),
                ("click_region", "startup_click", None),
                ("press_key", "2", 0.2),
                ("hold_keys", ("shift", "w"), 0.5),
                ("press_keys", ("ctrl", "c")),
                ("repeat_key", "space", 1.0, 0.25, 0.05),
                ("move_mouse", 120.0, -30.0, 0.2, "foreground"),
                (
                    "hold_mouse_button_and_move",
                    "right",
                    40.0,
                    10.0,
                    0.1,
                    "foreground",
                ),
                ("scroll_mouse", "down", 2, "foreground"),
                (
                    "start_continuous_input",
                    "forward_motion",
                    "hold_key",
                    (("key", "w"),),
                ),
                (
                    "hold_key_while_repeating_key",
                    "w",
                    2.0,
                    "space",
                    0.5,
                    0.1,
                ),
                ("stop_continuous_input", "forward_motion"),
                ("press_key", "e"),
                ("stop_all_continuous_inputs",),
            ],
        )


if __name__ == "__main__":
    unittest.main()
