from __future__ import annotations

import logging
import unittest

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.adapters.live import LiveAdaptersUnavailable
from game_script_dev.engine import Engine, LiveModeUnavailable
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
        return TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1)

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        return None


class StaticScreenAdapter:
    def capture(self, window: TargetWindow) -> Screenshot:
        return Screenshot(source=window.title)


class PresentVisionAdapter:
    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        return True

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return None


class UnavailableInputAdapter:
    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        raise LiveAdaptersUnavailable("live mouse input is not implemented yet")

    def click_region(self, region_name: str) -> None:
        raise LiveAdaptersUnavailable("live mouse input is not implemented yet")

    def press_key(self, key: str) -> None:
        raise LiveAdaptersUnavailable("target window is not foreground")

    def hold_key(self, key: str, seconds: float) -> None:
        raise LiveAdaptersUnavailable("target window is not foreground")

    def wait(self, seconds: float) -> None:
        return None


def live_runtime_factory(
    _profile: Profile,
    _mode: str,
    _logger: logging.Logger,
    _artifact_dir: object,
    _profile_dir: object,
) -> RuntimeContext:
    window = TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1)
    return RuntimeContext(
        mode="live",
        window=window,
        window_adapter=StaticWindowAdapter(),
        screen_adapter=StaticScreenAdapter(),
        vision_adapter=PresentVisionAdapter(),
        input_adapter=UnavailableInputAdapter(),
    )


def profile_with_action(action: Action) -> Profile:
    return Profile(
        version=1,
        name="Live Failure Profile",
        target=Target(process_name="test.exe"),
        resolution=Resolution(width=1280, height=720),
        initial_state="home",
        max_retries=1,
        states={
            "home": State(
                name="home",
                required_anchors=[Anchor(name="home_title", type="text", text="Home")],
                actions=[action],
                terminal=False,
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


def quiet_logger() -> logging.Logger:
    logger = logging.getLogger("tests.live_failures")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


class EngineLiveFailureTests(unittest.TestCase):
    def test_live_input_unavailable_becomes_live_mode_unavailable(self) -> None:
        engine = Engine(
            profile=profile_with_action(
                Action(type="press_key", data={"key": "enter"})
            ),
            mode="live",
            logger=quiet_logger(),
            runtime_factory=live_runtime_factory,
        )

        with self.assertRaises(LiveModeUnavailable) as captured:
            engine.run()

        self.assertIn("target window is not foreground", str(captured.exception))

    def test_live_pointer_unavailable_becomes_live_mode_unavailable(self) -> None:
        engine = Engine(
            profile=profile_with_action(
                Action(type="click_point", data={"region": "start"})
            ),
            mode="live",
            logger=quiet_logger(),
            runtime_factory=live_runtime_factory,
        )

        with self.assertRaises(LiveModeUnavailable) as captured:
            engine.run()

        self.assertIn(
            "live mouse input is not implemented yet", str(captured.exception)
        )


if __name__ == "__main__":
    unittest.main()
