from __future__ import annotations

import logging

from game_script_dev.schema import Action


class ActionRunner:
    def __init__(self, mode: str, logger: logging.Logger) -> None:
        self.mode = mode
        self.logger = logger

    def execute(self, action: Action) -> str | None:
        handler = getattr(self, f"_execute_{action.type}", None)
        if handler is None:
            raise ValueError(f"unsupported action: {action.type}")
        return handler(action)

    def _execute_wait_for_state(self, action: Action) -> str:
        state = str(action.data["state"])
        self.logger.info("Dry-run wait_for_state: %s", state)
        return state

    def _execute_click_template(self, action: Action) -> None:
        self.logger.info("Dry-run click_template: %s", action.data["target"])
        return None

    def _execute_click_point(self, action: Action) -> None:
        self.logger.info("Dry-run click_point region: %s", action.data["region"])
        return None

    def _execute_press_key(self, action: Action) -> None:
        self.logger.info("Dry-run press_key: %s", action.data["key"])
        return None

    def _execute_hold_key(self, action: Action) -> None:
        duration = action.data.get("seconds", "profile-default")
        self.logger.info("Dry-run hold_key: %s for %s seconds", action.data["key"], duration)
        return None

    def _execute_wait(self, action: Action) -> None:
        self.logger.info("Dry-run bounded wait: %s seconds", action.data["seconds"])
        return None

    def _execute_log(self, action: Action) -> None:
        self.logger.info("Profile log: %s", action.data.get("message", "checkpoint"))
        return None

    def _execute_stop(self, action: Action) -> str:
        result = str(action.data.get("result", "stopped"))
        self.logger.info("Profile requested stop: %s", result)
        return result
