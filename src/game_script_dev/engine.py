from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from game_script_dev.actions import ActionRunner
from game_script_dev.adapters.base import Screenshot
from game_script_dev.adapters.live import LiveAdaptersUnavailable, TargetWindowNotReady
from game_script_dev.runtime import RuntimeContext, create_runtime
from game_script_dev.schema import Action, Anchor, Interruption, Profile, State


MIN_LIVE_POLL_INTERVAL_SECONDS = 0.05
RunEventHandler = Callable[[dict[str, object]], None]
StopRequestedHandler = Callable[[], bool]


class LiveModeUnavailable(Exception):
    """Raised when live mode reaches an adapter that is not implemented yet."""


class StateExecutionError(Exception):
    """Raised when the current state cannot be confirmed or executed."""


class StopRequested(Exception):
    """Raised when the operator requests a running workflow to stop."""


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
        sleeper: Callable[[float], None] = time.sleep,
        event_handler: RunEventHandler | None = None,
        stop_requested: StopRequestedHandler | None = None,
    ) -> None:
        self.profile = profile
        self.mode = mode
        self.logger = logger
        self.runtime_factory = runtime_factory
        self.artifact_dir = artifact_dir
        self.profile_dir = profile_dir
        self.sleeper = sleeper
        self.event_handler = event_handler
        self.stop_requested = stop_requested

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
            raise LiveModeUnavailable(str(error)) from error

        if hasattr(runtime.input_adapter, "sleeper"):
            setattr(runtime.input_adapter, "sleeper", self.sleeper)

        actions = ActionRunner(runtime=runtime, logger=self.logger)

        current_state = self.profile.initial_state
        max_steps = max(1, len(self.profile.states) * (self.profile.max_retries + 2))
        failures_by_state: dict[str, int] = {}
        interruption_attempts: dict[str, int] = {}
        try:
            for _ in range(max_steps):
                self._check_stop_requested()
                state = self.profile.states[current_state]
                self._emit("state_started", state=state.name)
                try:
                    self._handle_interruptions(runtime, actions, interruption_attempts)
                    screenshot = self._capture_for_state_if_needed(runtime, state)

                    if state.terminal:
                        result = state.result or "success"
                        self.logger.info(
                            "Reached terminal state '%s': %s",
                            state.name,
                            result,
                        )
                        self._capture_final(runtime, state, result)
                        self._emit("finished", state=state.name, result=result)
                        return result

                    stop_result = self._execute_state_actions(
                        state,
                        actions,
                        runtime,
                        screenshot,
                    )
                    if stop_result is not None:
                        self._capture_final(runtime, state, f"stop-{stop_result}")
                        return stop_result

                    if state.on_success is None:
                        self._emit(
                            "finished",
                            state=state.name,
                            result="failed_missing_transition",
                            failure_reason="missing transition",
                        )
                        return "failed_missing_transition"

                    failures_by_state[state.name] = 0
                    self.logger.info("Transition: %s -> %s", state.name, state.on_success)
                    current_state = state.on_success
                except StopRequested:
                    self.logger.warning("Run stopped by operator")
                    self._capture_final(runtime, state, "stop-operator_stopped")
                    self._emit(
                        "finished",
                        state=state.name,
                        result="operator_stopped",
                        failure_reason="stop requested by operator",
                    )
                    return "operator_stopped"
                except StateExecutionError as error:
                    failures_by_state[state.name] = failures_by_state.get(state.name, 0) + 1
                    failure_count = failures_by_state[state.name]
                    self.logger.warning(
                        "State '%s' failed attempt %s/%s: %s",
                        state.name,
                        failure_count,
                        self.profile.max_retries,
                        error,
                    )
                    self._emit(
                        "state_failed",
                        state=state.name,
                        failure_count=failure_count,
                        failure_reason=str(error),
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
                        self._capture_final(
                            runtime,
                            state,
                            f"failed-{state.name}",
                        )
                        self._emit(
                            "finished",
                            state=state.name,
                            result=f"failed_{state.name}",
                            failure_reason=str(error),
                        )
                        return f"failed_{state.name}"

                    self.logger.info(
                        "Failure transition: %s -> %s",
                        state.name,
                        state.on_failure,
                    )
                    current_state = state.on_failure
                except LiveAdaptersUnavailable as error:
                    if runtime.mode == "live":
                        raise LiveModeUnavailable(str(error)) from error
                    raise

            self.logger.error("Exceeded maximum dry-run steps: %s", max_steps)
            self._emit(
                "finished",
                result="failed_max_steps",
                failure_reason="exceeded maximum workflow steps",
            )
            return "failed_max_steps"
        finally:
            runtime.input_adapter.stop_all_continuous_inputs()

    def _capture(self, runtime: RuntimeContext, context: str) -> Screenshot:
        self._check_stop_requested()
        try:
            try:
                return runtime.screen_adapter.capture(runtime.window, context=context)
            except TypeError:
                return runtime.screen_adapter.capture(runtime.window)
        except TargetWindowNotReady as error:
            raise StateExecutionError(f"target window is not ready: {error}") from error
        except LiveAdaptersUnavailable as error:
            raise StateExecutionError(f"live capture unavailable: {error}") from error

    def _capture_for_state_if_needed(
        self,
        runtime: RuntimeContext,
        state: State,
    ) -> Screenshot:
        if not self._state_needs_screenshot(state):
            self.logger.info(
                "Skipping screenshot for non-visual state '%s'",
                state.name,
            )
            return Screenshot(source=f"state-{state.name}-not-captured")

        screenshot = self._capture(runtime, f"state-{state.name}-confirm")
        self._confirm_state(state, runtime, screenshot)
        return screenshot

    def _state_needs_screenshot(self, state: State) -> bool:
        return bool(
            state.required_anchors
            or state.optional_anchors
            or state.forbidden_anchors
            or any(action.type == "click_template" for action in state.actions)
        )

    def _capture_final(
        self,
        runtime: RuntimeContext,
        state: State,
        reason: str,
    ) -> None:
        if runtime.mode != "live":
            return
        if not self._state_needs_screenshot(state):
            self.logger.info(
                "Skipping final screenshot for non-visual state '%s'",
                state.name,
            )
            return
        try:
            screenshot = self._capture(runtime, f"final-state-{state.name}-{reason}")
        except StateExecutionError as error:
            self.logger.warning("Final screenshot unavailable: %s", error)
            return
        self.logger.info(
            "Final diagnostic screenshot for state '%s': %s",
            state.name,
            screenshot.path or screenshot.source,
        )

    def _emit(self, event: str, **payload: object) -> None:
        if self.event_handler is None:
            return
        data = {"event": event, **payload}
        self.event_handler(data)

    def _handle_interruptions(
        self,
        runtime: RuntimeContext,
        actions: ActionRunner,
        attempts_by_name: dict[str, int],
    ) -> None:
        if runtime.mode == "dry-run":
            self.logger.info("Dry-run global interruption scan")
            return

        for interruption in self.profile.interruptions:
            self._check_stop_requested()
            screenshot = self._capture(
                runtime,
                f"interruption-{interruption.name}-scan",
            )
            if self._interruption_present(interruption, runtime, screenshot):
                attempts = attempts_by_name.get(interruption.name, 0) + 1
                attempts_by_name[interruption.name] = attempts
                if attempts > interruption.max_retries:
                    raise StateExecutionError(
                        "global interruption "
                        f"'{interruption.name}' exceeded recovery retry limit "
                        f"of {interruption.max_retries}"
                    )
                self.logger.warning(
                    "Global interruption detected: %s attempt %s/%s",
                    interruption.name,
                    attempts,
                    interruption.max_retries,
                )
                for action in interruption.recovery_actions:
                    self._check_stop_requested()
                    actions.execute(action, screenshot)
            else:
                attempts_by_name[interruption.name] = 0

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
        started_at = time.monotonic()
        self._check_anchors("required", state.required_anchors, runtime, screenshot)
        self._check_optional_anchors(state.optional_anchors, runtime, screenshot)
        self._check_forbidden_anchors(state.forbidden_anchors, runtime, screenshot)
        self.logger.info(
            "State '%s' confirmed after %s using anchors: %s",
            state.name,
            self._format_seconds(time.monotonic() - started_at),
            self._summarize_anchor_names(state),
        )

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
                raise StateExecutionError(f"forbidden anchor '{anchor.name}' was found")

    def _execute_state_actions(
        self,
        state: State,
        actions: ActionRunner,
        runtime: RuntimeContext,
        screenshot: Screenshot,
    ) -> str | None:
        for index, action in enumerate(state.actions, start=1):
            self._check_stop_requested()
            summary = self._action_summary(action)
            self._emit(
                "action_started",
                state=state.name,
                action_index=index,
                action_type=action.type,
                action_summary=summary,
            )
            try:
                if action.type == "wait_for_state" and runtime.mode != "dry-run":
                    self._wait_for_state(action.data, runtime)
                    result = None
                else:
                    result = actions.execute(action, screenshot)
            except LiveAdaptersUnavailable as error:
                self._emit(
                    "action_failed",
                    state=state.name,
                    action_index=index,
                    action_type=action.type,
                    action_summary=summary,
                    failure_reason=str(error),
                )
                raise
            except Exception as error:
                self._emit(
                    "action_failed",
                    state=state.name,
                    action_index=index,
                    action_type=action.type,
                    action_summary=summary,
                    failure_reason=str(error),
                )
                raise StateExecutionError(
                    f"action {summary} failed: {error}"
                ) from error

            event: dict[str, object] = {
                "state": state.name,
                "action_index": index,
                "action_type": action.type,
                "action_summary": summary,
            }
            if result is not None:
                event["result"] = result
            self._emit("action_completed", **event)
            if action.type == "stop":
                return result or "stopped"
        return None

    def _action_summary(self, action: Action) -> str:
        action_type = action.type
        action_data = action.data
        if action_type == "wait_for_state":
            return f"wait_for_state {action_data['state']}"
        if action_type == "click_point":
            return f"click_point {action_data['region']}"
        if action_type == "hold_click":
            return f"hold_click {action_data['region']} {action_data['seconds']}s"
        if action_type == "click_template":
            return f"click_template {action_data['target']}"
        if action_type == "press_key":
            if "seconds" in action_data:
                return f"press_key {action_data['key']} {action_data['seconds']}s"
            return f"press_key {action_data['key']}"
        if action_type == "press_keys":
            keys = " + ".join(str(key) for key in action_data["keys"])
            if "seconds" in action_data:
                return f"press_keys {keys} {action_data['seconds']}s"
            return f"press_keys {keys}"
        if action_type == "hold_key":
            seconds = action_data.get("seconds", 1)
            return f"hold_key {action_data['key']} {seconds}s"
        if action_type == "hold_keys":
            seconds = action_data.get("seconds", 1)
            keys = " + ".join(str(key) for key in action_data["keys"])
            return f"hold_keys {keys} {seconds}s"
        if action_type == "repeat_key":
            summary = (
                f"repeat_key {action_data['key']} every "
                f"{action_data['repeat_every_seconds']}s for "
                f"{action_data['repeat_for_seconds']}s"
            )
            if "tap_duration_seconds" in action_data:
                summary += f" with {action_data['tap_duration_seconds']}s taps"
            return summary
        if action_type == "hold_key_while_repeating_key":
            summary = (
                "hold_key_while_repeating_key "
                f"{action_data['hold_key']} for {action_data['hold_seconds']}s "
                f"while tapping {action_data['tap_key']} every "
                f"{action_data['tap_every_seconds']}s"
            )
            if "tap_duration_seconds" in action_data:
                summary += f" for {action_data['tap_duration_seconds']}s"
            return summary
        if action_type == "move_mouse":
            summary = f"move_mouse dx={action_data['dx']} dy={action_data['dy']}"
            if "seconds" in action_data:
                summary += f" {action_data['seconds']}s"
            return summary
        if action_type == "hold_mouse_button_and_move":
            summary = (
                "hold_mouse_button_and_move "
                f"{action_data['button']} dx={action_data['dx']} dy={action_data['dy']}"
            )
            if "seconds" in action_data:
                summary += f" {action_data['seconds']}s"
            return summary
        if action_type == "start_continuous_input":
            summary = (
                f"start_continuous_input {action_data['name']} "
                f"{action_data['action']}"
            )
            if "stop_after_seconds" in action_data:
                summary += f" for {action_data['stop_after_seconds']}s"
            return summary
        if action_type == "stop_continuous_input":
            return f"stop_continuous_input {action_data['name']}"
        if action_type == "wait":
            return f"wait {action_data['seconds']}s"
        if action_type == "log":
            return str(action_data.get("message", "checkpoint"))
        if action_type == "stop":
            return f"stop {action_data.get('result', 'stopped')}"
        return action_type

    def _wait_for_state(
        self,
        action_data: dict[str, object],
        runtime: RuntimeContext,
    ) -> None:
        state_name = str(action_data["state"])
        expected_state = self.profile.states[state_name]
        timeout_seconds = float(
            action_data.get("timeout_seconds", self.profile.default_timeout_seconds)
        )
        poll_interval_seconds = float(action_data.get("poll_interval_seconds", 0.5))
        started_at = time.monotonic()
        if poll_interval_seconds < MIN_LIVE_POLL_INTERVAL_SECONDS:
            self.logger.info(
                "Using minimum live poll interval %s seconds instead of %s",
                MIN_LIVE_POLL_INTERVAL_SECONDS,
                poll_interval_seconds,
            )
            poll_interval_seconds = MIN_LIVE_POLL_INTERVAL_SECONDS
        deadline = started_at + timeout_seconds

        self.logger.info(
            "Waiting for state '%s' for up to %s seconds",
            state_name,
            timeout_seconds,
        )

        while True:
            self._check_stop_requested()
            screenshot = self._capture(runtime, f"wait-for-{state_name}")
            try:
                self._confirm_state(expected_state, runtime, screenshot)
                self.logger.info(
                    "Wait for state succeeded after %s: %s",
                    self._format_seconds(time.monotonic() - started_at),
                    state_name,
                )
                return
            except StateExecutionError as error:
                if time.monotonic() >= deadline:
                    raise StateExecutionError(
                        f"timed out waiting for state '{state_name}' after "
                        f"{self._format_seconds(time.monotonic() - started_at)}: {error}"
                    ) from error
                self.sleeper(poll_interval_seconds)

    def _check_stop_requested(self) -> None:
        if self.stop_requested is not None and self.stop_requested():
            raise StopRequested()

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        return f"{max(0.0, seconds):.2f} seconds"

    @staticmethod
    def _summarize_anchor_names(state: State) -> str:
        names = [
            anchor.name
            for anchor in (
                state.required_anchors + state.optional_anchors + state.forbidden_anchors
            )
        ]
        if not names:
            return "none"
        return ", ".join(names)
