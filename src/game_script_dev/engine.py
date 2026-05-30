from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from game_script_dev.actions import ActionRunner
from game_script_dev.adapters.base import Screenshot
from game_script_dev.runtime import RuntimeContext, create_runtime
from game_script_dev.schema import Anchor, Interruption, Profile, State


class LiveModeUnavailable(Exception):
    """Raised when live mode reaches an adapter that is not implemented yet."""


class StateExecutionError(Exception):
    """Raised when the current state cannot be confirmed or executed."""


class Engine:
    def __init__(
        self,
        profile: Profile,
        mode: str,
        logger: logging.Logger,
        runtime_factory: Callable[
            [Profile, str, logging.Logger, Path | None, Path | None],
            RuntimeContext,
        ] = create_runtime,
        artifact_dir: Path | None = None,
        profile_dir: Path | None = None,
    ) -> None:
        self.profile = profile
        self.mode = mode
        self.logger = logger
        self.runtime_factory = runtime_factory
        self.artifact_dir = artifact_dir
        self.profile_dir = profile_dir

    def run(self) -> str:
        try:
            runtime = self.runtime_factory(
                self.profile,
                self.mode,
                self.logger,
                self.artifact_dir,
                self.profile_dir,
            )
        except Exception as error:
            raise LiveModeUnavailable(
                str(error)
            ) from error

        actions = ActionRunner(runtime=runtime, logger=self.logger)

        current_state = self.profile.initial_state
        max_steps = max(1, len(self.profile.states) * (self.profile.max_retries + 2))
        failures_by_state: dict[str, int] = {}

        for _ in range(max_steps):
            state = self.profile.states[current_state]
            try:
                self._handle_interruptions(runtime, actions)
                screenshot = runtime.screen_adapter.capture(runtime.window)
                self._confirm_state(state, runtime, screenshot)

                if state.terminal:
                    result = state.result or "success"
                    self.logger.info(
                        "Reached terminal state '%s': %s",
                        state.name,
                        result,
                    )
                    return result

                stop_result = self._execute_state_actions(state, actions, screenshot)
                if stop_result is not None:
                    return stop_result

                if state.on_success is None:
                    return "failed_missing_transition"

                failures_by_state[state.name] = 0
                self.logger.info("Transition: %s -> %s", state.name, state.on_success)
                current_state = state.on_success
            except StateExecutionError as error:
                failures_by_state[state.name] = (
                    failures_by_state.get(state.name, 0) + 1
                )
                failure_count = failures_by_state[state.name]
                self.logger.warning(
                    "State '%s' failed attempt %s/%s: %s",
                    state.name,
                    failure_count,
                    self.profile.max_retries,
                    error,
                )

                if failure_count < self.profile.max_retries:
                    self.logger.info("Retrying state: %s", state.name)
                    continue

                if state.on_failure == "graceful_termination":
                    self.logger.error(
                        "Graceful termination from state '%s' after %s failures",
                        state.name,
                        failure_count,
                    )
                    return f"failed_{state.name}"

                self.logger.info(
                    "Failure transition: %s -> %s",
                    state.name,
                    state.on_failure,
                )
                current_state = state.on_failure

        self.logger.error("Exceeded maximum dry-run steps: %s", max_steps)
        return "failed_max_steps"

    def _handle_interruptions(
        self,
        runtime: RuntimeContext,
        actions: ActionRunner,
    ) -> None:
        if runtime.mode == "dry-run":
            self.logger.info("Dry-run global interruption scan")
            return

        for interruption in self.profile.interruptions:
            screenshot = runtime.screen_adapter.capture(runtime.window)
            if self._interruption_present(interruption, runtime, screenshot):
                self.logger.warning(
                    "Global interruption detected: %s",
                    interruption.name,
                )
                for action in interruption.recovery_actions:
                    actions.execute(action, screenshot)

    def _interruption_present(
        self,
        interruption: Interruption,
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> bool:
        return all(
            runtime.vision_adapter.anchor_present(anchor, screenshot)
            for anchor in interruption.required_anchors
        )

    def _confirm_state(
        self,
        state: State,
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> None:
        self.logger.info("Confirming state: %s", state.name)
        self._check_anchors("required", state.required_anchors, runtime, screenshot)
        self._check_optional_anchors(state.optional_anchors, runtime, screenshot)
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
                raise StateExecutionError(
                    f"{label} anchor '{anchor.name}' was not found"
                )

    def _check_optional_anchors(
        self,
        anchors: list[Anchor],
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> None:
        for anchor in anchors:
            if runtime.vision_adapter.anchor_present(anchor, screenshot):
                self.logger.info("Optional anchor found: %s", anchor.name)
            else:
                self.logger.info("Optional anchor absent: %s", anchor.name)

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
                raise StateExecutionError(
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
