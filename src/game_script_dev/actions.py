from __future__ import annotations

import logging

from game_script_dev.adapters.base import Screenshot
from game_script_dev.runtime import RuntimeContext
from game_script_dev.schema import Action


class ActionRunner:
    def __init__(self, runtime: RuntimeContext, logger: logging.Logger) -> None:
        self.runtime = runtime
        self.logger = logger

    def execute(self, action: Action, screenshot: Screenshot) -> str | None:
        handler = getattr(self, f"_execute_{action.type}", None)
        if handler is None:
            raise ValueError(f"unsupported action: {action.type}")
        return handler(action, screenshot)

    def _execute_wait_for_state(
        self,
        action: Action,
        screenshot: Screenshot,
    ) -> str:
        state = str(action.data["state"])
        self.logger.info("Bounded wait for state: %s", state)
        return state

    def _execute_click_template(
        self,
        action: Action,
        screenshot: Screenshot,
    ) -> None:
        asset = str(action.data["target"])
        center = self.runtime.vision_adapter.find_template_center(asset, screenshot)
        if center is None:
            raise ValueError(f"template target was not found: {asset}")
        x, y = center
        self.runtime.input_adapter.click_coordinates(x, y, f"template:{asset}")
        return None

    def _execute_click_point(self, action: Action, screenshot: Screenshot) -> None:
        self.runtime.input_adapter.click_region(str(action.data["region"]))
        return None

    def _execute_hold_click(self, action: Action, screenshot: Screenshot) -> None:
        duration = float(action.data["seconds"])
        self.runtime.input_adapter.hold_click(str(action.data["region"]), duration)
        return None

    def _execute_press_key(self, action: Action, screenshot: Screenshot) -> None:
        duration = (
            float(action.data["seconds"]) if "seconds" in action.data else None
        )
        self.runtime.input_adapter.press_key(str(action.data["key"]), duration)
        return None

    def _execute_press_keys(self, action: Action, screenshot: Screenshot) -> None:
        duration = (
            float(action.data["seconds"]) if "seconds" in action.data else None
        )
        keys = [str(key) for key in action.data["keys"]]
        self.runtime.input_adapter.press_keys(keys, duration)
        return None

    def _execute_hold_key(self, action: Action, screenshot: Screenshot) -> None:
        duration = float(action.data.get("seconds", 1))
        self.runtime.input_adapter.hold_key(str(action.data["key"]), duration)
        return None

    def _execute_hold_keys(self, action: Action, screenshot: Screenshot) -> None:
        duration = float(action.data.get("seconds", 1))
        keys = [str(key) for key in action.data["keys"]]
        self.runtime.input_adapter.hold_keys(keys, duration)
        return None

    def _execute_hold_key_while_repeating_key(
        self,
        action: Action,
        screenshot: Screenshot,
    ) -> None:
        tap_duration = (
            float(action.data["tap_duration_seconds"])
            if "tap_duration_seconds" in action.data
            else None
        )
        self.runtime.input_adapter.hold_key_while_repeating_key(
            hold_key=str(action.data["hold_key"]),
            hold_seconds=float(action.data["hold_seconds"]),
            tap_key=str(action.data["tap_key"]),
            tap_every_seconds=float(action.data["tap_every_seconds"]),
            tap_duration_seconds=tap_duration,
        )
        return None

    def _execute_wait(self, action: Action, screenshot: Screenshot) -> None:
        self.runtime.input_adapter.wait(float(action.data["seconds"]))
        return None

    def _execute_log(self, action: Action, screenshot: Screenshot) -> None:
        self.logger.info("Profile log: %s", action.data.get("message", "checkpoint"))
        return None

    def _execute_stop(self, action: Action, screenshot: Screenshot) -> str:
        result = str(action.data.get("result", "stopped"))
        self.logger.info("Profile requested stop: %s", result)
        return result
