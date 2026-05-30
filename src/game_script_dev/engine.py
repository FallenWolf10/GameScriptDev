from __future__ import annotations

import logging

from game_script_dev.actions import ActionRunner
from game_script_dev.schema import Anchor, Profile, State


class LiveModeUnavailable(Exception):
    """Raised when live mode reaches an adapter that is not implemented yet."""


class Engine:
    def __init__(self, profile: Profile, mode: str, logger: logging.Logger) -> None:
        self.profile = profile
        self.mode = mode
        self.logger = logger
        self.actions = ActionRunner(mode=mode, logger=logger)

    def run(self) -> str:
        if self.mode == "live":
            raise LiveModeUnavailable(
                "Live mode confirmation is wired, but live desktop adapters are not "
                "implemented yet."
            )

        current_state = self.profile.initial_state
        max_steps = max(1, len(self.profile.states) * (self.profile.max_retries + 2))

        for _ in range(max_steps):
            state = self.profile.states[current_state]
            self._confirm_state(state)

            if state.terminal:
                result = state.result or "success"
                self.logger.info("Reached terminal state '%s': %s", state.name, result)
                return result

            stop_result = self._execute_state_actions(state)
            if stop_result is not None:
                return stop_result

            if state.on_success is None:
                return "failed_missing_transition"

            self.logger.info("Transition: %s -> %s", state.name, state.on_success)
            current_state = state.on_success

        self.logger.error("Exceeded maximum dry-run steps: %s", max_steps)
        return "failed_max_steps"

    def _confirm_state(self, state: State) -> None:
        self.logger.info("Confirming state: %s", state.name)
        self._log_anchors("required", state.required_anchors)
        self._log_anchors("optional", state.optional_anchors)
        self._log_anchors("forbidden_absent", state.forbidden_anchors)

    def _log_anchors(self, label: str, anchors: list[Anchor]) -> None:
        for anchor in anchors:
            detail = anchor.asset if anchor.type == "template" else anchor.text
            self.logger.info("Dry-run anchor %s: %s (%s)", label, anchor.name, detail)

    def _execute_state_actions(self, state: State) -> str | None:
        for action in state.actions:
            result = self.actions.execute(action)
            if action.type == "stop":
                return result or "stopped"
        return None
