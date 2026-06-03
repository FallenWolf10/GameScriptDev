from __future__ import annotations

import logging
import unittest

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.engine import Engine
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import (
    Action,
    Anchor,
    Interruption,
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


class StaticScreenAdapter:
    def capture(self, window: TargetWindow) -> Screenshot:
        return Screenshot(source=window.title)


class StaticInputAdapter:
    def __init__(self) -> None:
        self.wait_count = 0

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

    def press_key(self, key: str) -> None:
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
        self.wait_count += 1
        return None


class StaticVisionAdapter:
    def __init__(self, present_anchor_names: set[str]) -> None:
        self.present_anchor_names = present_anchor_names

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        return anchor.name in self.present_anchor_names

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return None


def runtime_with_anchors(
    present_anchor_names: set[str],
) -> RuntimeContext:
    window = TargetWindow("test", "test.exe", 0, 0, 1280, 720)
    return RuntimeContext(
        mode="test",
        window=window,
        window_adapter=StaticWindowAdapter(),
        screen_adapter=StaticScreenAdapter(),
        vision_adapter=StaticVisionAdapter(present_anchor_names),
        input_adapter=StaticInputAdapter(),
    )


def runtime_factory_with_runtime(runtime: RuntimeContext):
    def factory(
        _profile: Profile,
        _mode: str,
        _logger: logging.Logger,
        _artifact_dir: object,
        _profile_dir: object,
    ) -> RuntimeContext:
        return runtime

    return factory


def runtime_factory_with_anchors(present_anchor_names: set[str]):
    def factory(
        _profile: Profile,
        _mode: str,
        _logger: logging.Logger,
        _artifact_dir: object,
        _profile_dir: object,
    ) -> RuntimeContext:
        return runtime_with_anchors(present_anchor_names)

    return factory


def logger() -> logging.Logger:
    test_logger = logging.getLogger("tests.engine_retries")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())
    return test_logger


class EngineRetryTests(unittest.TestCase):
    def test_gracefully_terminates_after_state_retry_limit(self) -> None:
        profile = Profile(
            version=1,
            name="Retry Profile",
            target=Target(process_name="test.exe"),
            resolution=Resolution(width=1280, height=720),
            initial_state="home",
            max_retries=3,
            states={
                "home": State(
                    name="home",
                    required_anchors=[
                        Anchor(name="home_title", type="text", text="Home")
                    ],
                    on_success="done",
                ),
                "done": State(name="done", terminal=True, result="success"),
            },
        )

        result = Engine(
            profile=profile,
            mode="test",
            logger=logger(),
            runtime_factory=runtime_factory_with_anchors(set()),
        ).run()

        self.assertEqual(result, "failed_home")

    def test_uses_failure_transition_after_retry_limit(self) -> None:
        profile = Profile(
            version=1,
            name="Retry Profile",
            target=Target(process_name="test.exe"),
            resolution=Resolution(width=1280, height=720),
            initial_state="home",
            max_retries=2,
            states={
                "home": State(
                    name="home",
                    required_anchors=[
                        Anchor(name="home_title", type="text", text="Home")
                    ],
                    on_success="done",
                    on_failure="known_failure",
                ),
                "known_failure": State(
                    name="known_failure",
                    terminal=True,
                    result="failure_known_screen",
                ),
                "done": State(name="done", terminal=True, result="success"),
            },
        )

        result = Engine(
            profile=profile,
            mode="test",
            logger=logger(),
            runtime_factory=runtime_factory_with_anchors({"known_failure_title"}),
        ).run()

        self.assertEqual(result, "failure_known_screen")

    def test_forbidden_anchor_causes_state_failure(self) -> None:
        profile = Profile(
            version=1,
            name="Forbidden Profile",
            target=Target(process_name="test.exe"),
            resolution=Resolution(width=1280, height=720),
            initial_state="home",
            max_retries=1,
            states={
                "home": State(
                    name="home",
                    required_anchors=[
                        Anchor(name="home_title", type="text", text="Home")
                    ],
                    forbidden_anchors=[
                        Anchor(name="disconnect", type="text", text="Disconnected")
                    ],
                    on_success="done",
                ),
                "done": State(name="done", terminal=True, result="success"),
            },
        )

        result = Engine(
            profile=profile,
            mode="test",
            logger=logger(),
            runtime_factory=runtime_factory_with_anchors({"home_title", "disconnect"}),
        ).run()

        self.assertEqual(result, "failed_home")

    def test_interruption_recovery_stops_after_retry_limit(self) -> None:
        input_adapter = StaticInputAdapter()
        runtime = RuntimeContext(
            mode="live",
            window=TargetWindow("test", "test.exe", 0, 0, 1280, 720),
            window_adapter=StaticWindowAdapter(),
            screen_adapter=StaticScreenAdapter(),
            vision_adapter=StaticVisionAdapter({"home_title", "popup"}),
            input_adapter=input_adapter,
        )
        profile = Profile(
            version=1,
            name="Interruption Profile",
            target=Target(process_name="test.exe"),
            resolution=Resolution(width=1280, height=720),
            initial_state="home",
            max_retries=1,
            states={
                "home": State(
                    name="home",
                    required_anchors=[
                        Anchor(name="home_title", type="text", text="Home")
                    ],
                    on_success="home",
                ),
            },
            interruptions=[
                Interruption(
                    name="popup",
                    required_anchors=[Anchor(name="popup", type="text", text="Popup")],
                    recovery_actions=[Action(type="wait", data={"seconds": 0})],
                    max_retries=1,
                )
            ],
        )

        result = Engine(
            profile=profile,
            mode="live",
            logger=logger(),
            runtime_factory=runtime_factory_with_runtime(runtime),
        ).run()

        self.assertEqual(result, "failed_home")
        self.assertEqual(input_adapter.wait_count, 1)


if __name__ == "__main__":
    unittest.main()
