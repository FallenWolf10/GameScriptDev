from __future__ import annotations

import logging
import unittest

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.engine import Engine
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import Anchor, Profile, Resolution, State, Target


class StaticWindowAdapter:
    def find_target(self, profile: Profile) -> TargetWindow:
        return TargetWindow("test", "test.exe", 1280, 720)

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        return None


class StaticScreenAdapter:
    def capture(self, window: TargetWindow) -> Screenshot:
        return Screenshot(source=window.title)


class StaticInputAdapter:
    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        return None

    def click_region(self, region_name: str) -> None:
        return None

    def press_key(self, key: str) -> None:
        return None

    def hold_key(self, key: str, seconds: float) -> None:
        return None

    def wait(self, seconds: float) -> None:
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
    window = TargetWindow("test", "test.exe", 1280, 720)
    return RuntimeContext(
        mode="test",
        window=window,
        window_adapter=StaticWindowAdapter(),
        screen_adapter=StaticScreenAdapter(),
        vision_adapter=StaticVisionAdapter(present_anchor_names),
        input_adapter=StaticInputAdapter(),
    )


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
            runtime_factory=lambda _profile, _mode, _logger: runtime_with_anchors(
                set()
            ),
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
            runtime_factory=lambda _profile, _mode, _logger: runtime_with_anchors(
                {"known_failure_title"}
            ),
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
            runtime_factory=lambda _profile, _mode, _logger: runtime_with_anchors(
                {"home_title", "disconnect"}
            ),
        ).run()

        self.assertEqual(result, "failed_home")


if __name__ == "__main__":
    unittest.main()
