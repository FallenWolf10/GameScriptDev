from __future__ import annotations

import logging
import unittest

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

    def click_region(self, region_name: str) -> None:
        return None

    def press_key(self, key: str) -> None:
        return None

    def hold_key(self, key: str, seconds: float) -> None:
        return None

    def wait(self, seconds: float) -> None:
        return None


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
                required_anchors=[
                    Anchor(name="home_title", type="text", text="Home")
                ],
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
                required_anchors=[
                    Anchor(name="done_title", type="text", text="Done")
                ],
                terminal=True,
                result="success",
            ),
        },
    )


def quiet_logger(name: str) -> logging.Logger:
    test_logger = logging.getLogger(name)
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())
    test_logger.propagate = False
    return test_logger


class EngineWaitForStateTests(unittest.TestCase):
    def test_wait_for_state_polls_until_anchor_is_present(self) -> None:
        result = Engine(
            profile=profile_for_wait(timeout_seconds=1),
            mode="live",
            logger=quiet_logger("tests.wait_success"),
            runtime_factory=runtime_factory(ready_after_capture=3),
        ).run()

        self.assertEqual(result, "success")

    def test_wait_for_state_times_out(self) -> None:
        result = Engine(
            profile=profile_for_wait(timeout_seconds=0),
            mode="live",
            logger=quiet_logger("tests.wait_timeout"),
            runtime_factory=runtime_factory(ready_after_capture=None),
        ).run()

        self.assertEqual(result, "failed_home")


if __name__ == "__main__":
    unittest.main()
