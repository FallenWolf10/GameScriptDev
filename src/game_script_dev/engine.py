from __future__ import annotations

import logging

from game_script_dev.actions import ActionRunner
from game_script_dev.adapters.base import Screenshot
from game_script_dev.runtime import RuntimeContext, create_runtime
from game_script_dev.schema import Anchor, Profile, State


class LiveModeUnavailable(Exception):
    """Raised when live mode reaches an adapter that is not implemented yet."""


class Engine:
    def __init__(self, profile: Profile, mode: str, logger: logging.Logger) -> None:
        self.profile = profile
        self.mode = mode
        self.logger = logger

    def run(self) -> str:
        try:
            runtime = create_runtime(self.profile, self.mode, self.logger)
        except Exception as error:
            raise LiveModeUnavailable(
                str(error)
            ) from error

        actions = ActionRunner(runtime=runtime, logger=self.logger)

        current_state = self.profile.initial_state
        max_steps = max(1, len(self.profile.states) * (self.profile.max_retries + 2))

        for _ in range(max_steps):
            state = self.profile.states[current_state]
            screenshot = runtime.screen_adapter.capture(runtime.window)
            self._confirm_state(state, runtime, screenshot)

            if state.terminal:
                result = state.result or "success"
                self.logger.info("Reached terminal state '%s': %s", state.name, result)
                return result

            stop_result = self._execute_state_actions(state, actions, screenshot)
            if stop_result is not None:
                return stop_result

            if state.on_success is None:
                return "failed_missing_transition"

            self.logger.info("Transition: %s -> %s", state.name, state.on_success)
            current_state = state.on_success

        self.logger.error("Exceeded maximum dry-run steps: %s", max_steps)
        return "failed_max_steps"

    def _confirm_state(
        self,
        state: State,
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> None:
        self.logger.info("Confirming state: %s", state.name)
        self._check_anchors("required", state.required_anchors, runtime, screenshot)
        self._check_anchors("optional", state.optional_anchors, runtime, screenshot)
        self._check_forbidden_anchors(state.forbidden_anchors, runtime, screenshot)

    def _check_anchors(
        self,
        label: str,
        anchors: list[Anchor],
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> None:
        for anchor in anchors:
            if not runtime.vision_adapter.anchor_present(anchor, screenshot):
                raise LiveModeUnavailable(
                    f"{label} anchor '{anchor.name}' was not found"
                )

    def _check_forbidden_anchors(
        self,
        anchors: list[Anchor],
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> None:
        for anchor in anchors:
            if runtime.mode == "dry-run":
                self.logger.info("Dry-run forbidden anchor absent: %s", anchor.name)
                continue
            if runtime.vision_adapter.anchor_present(anchor, screenshot):
                raise LiveModeUnavailable(
                    f"forbidden anchor '{anchor.name}' was found"
                )

    def _execute_state_actions(
        self,
        state: State,
        actions: ActionRunner,
        screenshot: Screenshot,
    ) -> str | None:
        for action in state.actions:
            result = actions.execute(action, screenshot)
            if action.type == "stop":
                return result or "stopped"
        return None
