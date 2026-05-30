from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_ANCHOR_TYPES = {"template", "text"}
SUPPORTED_ACTION_TYPES = {
    "wait_for_state",
    "click_template",
    "click_point",
    "press_key",
    "hold_key",
    "wait",
    "log",
    "stop",
}


class ProfileValidationError(Exception):
    """Raised when a profile does not satisfy the strict schema."""


@dataclass(frozen=True)
class Target:
    process_name: str | None = None
    window_title_contains: str | None = None


@dataclass(frozen=True)
class Resolution:
    width: int
    height: int
    policy: str = "verify_only"


@dataclass(frozen=True)
class Anchor:
    name: str
    type: str
    asset: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class Action:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class State:
    name: str
    required_anchors: list[Anchor] = field(default_factory=list)
    optional_anchors: list[Anchor] = field(default_factory=list)
    forbidden_anchors: list[Anchor] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    on_success: str | None = None
    on_failure: str = "graceful_termination"
    terminal: bool = False
    result: str | None = None


@dataclass(frozen=True)
class Interruption:
    name: str
    required_anchors: list[Anchor] = field(default_factory=list)
    recovery_actions: list[Action] = field(default_factory=list)
    max_retries: int = 1


@dataclass(frozen=True)
class Profile:
    version: int
    name: str
    target: Target
    resolution: Resolution
    initial_state: str
    states: dict[str, State]
    interruptions: list[Interruption] = field(default_factory=list)
    default_timeout_seconds: float = 30.0
    max_retries: int = 3


def profile_from_mapping(raw: dict[str, Any]) -> Profile:
    target_raw = _mapping(raw, "target")
    window_raw = _mapping(raw, "window")
    resolution_raw = _mapping(window_raw, "resolution")
    execution_raw = raw.get("execution", {})
    if not isinstance(execution_raw, dict):
        raise ValueError("execution must be a mapping")

    states_raw = _mapping(raw, "states")
    states = {
        state_name: _state_from_mapping(state_name, state_raw)
        for state_name, state_raw in states_raw.items()
    }

    interruptions_raw = raw.get("interruptions", [])
    if not isinstance(interruptions_raw, list):
        raise ValueError("interruptions must be a list")

    return Profile(
        version=int(raw.get("version", 1)),
        name=_string(raw, "name"),
        target=Target(
            process_name=target_raw.get("process_name"),
            window_title_contains=target_raw.get("window_title_contains"),
        ),
        resolution=Resolution(
            width=int(resolution_raw["width"]),
            height=int(resolution_raw["height"]),
            policy=str(resolution_raw.get("policy", "verify_only")),
        ),
        initial_state=_string(raw, "initial_state"),
        states=states,
        interruptions=[
            _interruption_from_mapping(interruption_raw)
            for interruption_raw in interruptions_raw
        ],
        default_timeout_seconds=float(execution_raw.get("default_timeout_seconds", 30)),
        max_retries=int(execution_raw.get("max_retries", 3)),
    )


def validate_profile(profile: Profile, profile_dir: Path) -> None:
    errors: list[str] = []

    if not profile.target.process_name and not profile.target.window_title_contains:
        errors.append("target must define process_name or window_title_contains")

    if profile.resolution.policy not in {"verify_only", "attempt_resize", "ignore"}:
        errors.append(f"unknown resolution policy: {profile.resolution.policy}")

    if profile.initial_state not in profile.states:
        errors.append(f"initial_state is missing from states: {profile.initial_state}")

    for state in profile.states.values():
        _validate_anchors(state.required_anchors, profile_dir, errors)
        _validate_anchors(state.optional_anchors, profile_dir, errors)
        _validate_anchors(state.forbidden_anchors, profile_dir, errors)
        _validate_actions(state.actions, profile.states, profile_dir, errors)

        if state.terminal:
            if not state.result:
                errors.append(f"terminal state '{state.name}' must define result")
        elif not state.on_success:
            errors.append(f"state '{state.name}' must define on_success")
        elif state.on_success not in profile.states:
            errors.append(
                f"state '{state.name}' on_success references unknown state "
                f"'{state.on_success}'"
            )
        if (
            state.on_failure != "graceful_termination"
            and state.on_failure not in profile.states
        ):
            errors.append(
                f"state '{state.name}' on_failure references unknown state "
                f"'{state.on_failure}'"
            )

    for interruption in profile.interruptions:
        _validate_anchors(interruption.required_anchors, profile_dir, errors)
        _validate_actions(
            interruption.recovery_actions,
            profile.states,
            profile_dir,
            errors,
        )

    if errors:
        raise ProfileValidationError("; ".join(errors))


def _state_from_mapping(name: str, raw: Any) -> State:
    if not isinstance(raw, dict):
        raise ValueError(f"state '{name}' must be a mapping")

    return State(
        name=name,
        required_anchors=_anchors_from_list(raw.get("required_anchors", [])),
        optional_anchors=_anchors_from_list(raw.get("optional_anchors", [])),
        forbidden_anchors=_anchors_from_list(raw.get("forbidden_anchors", [])),
        actions=_actions_from_list(raw.get("actions", [])),
        on_success=raw.get("on_success"),
        on_failure=str(raw.get("on_failure", "graceful_termination")),
        terminal=bool(raw.get("terminal", False)),
        result=raw.get("result"),
    )


def _interruption_from_mapping(raw: Any) -> Interruption:
    if not isinstance(raw, dict):
        raise ValueError("interruption must be a mapping")

    return Interruption(
        name=_string(raw, "name"),
        required_anchors=_anchors_from_list(raw.get("required_anchors", [])),
        recovery_actions=_actions_from_list(raw.get("recovery_actions", [])),
        max_retries=int(raw.get("max_retries", 1)),
    )


def _anchors_from_list(raw: Any) -> list[Anchor]:
    if not isinstance(raw, list):
        raise ValueError("anchors must be a list")

    anchors = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("anchor must be a mapping")
        anchors.append(
            Anchor(
                name=_string(item, "name"),
                type=_string(item, "type"),
                asset=item.get("asset"),
                text=item.get("text"),
            )
        )
    return anchors


def _actions_from_list(raw: Any) -> list[Action]:
    if not isinstance(raw, list):
        raise ValueError("actions must be a list")

    actions = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("action must be a mapping")
        action_type = _string(item, "type")
        actions.append(
            Action(
                type=action_type,
                data={k: v for k, v in item.items() if k != "type"},
            )
        )
    return actions


def _validate_anchors(
    anchors: list[Anchor],
    profile_dir: Path,
    errors: list[str],
) -> None:
    for anchor in anchors:
        if anchor.type not in SUPPORTED_ANCHOR_TYPES:
            errors.append(f"anchor '{anchor.name}' uses unknown type '{anchor.type}'")
        if anchor.type == "template":
            if not anchor.asset:
                errors.append(f"template anchor '{anchor.name}' must define asset")
            elif not (profile_dir / anchor.asset).exists():
                errors.append(f"template anchor asset missing: {anchor.asset}")
        if anchor.type == "text" and not anchor.text:
            errors.append(f"text anchor '{anchor.name}' must define text")


def _validate_actions(
    actions: list[Action],
    states: dict[str, State],
    profile_dir: Path,
    errors: list[str],
) -> None:
    for action in actions:
        if action.type not in SUPPORTED_ACTION_TYPES:
            errors.append(f"unknown action type: {action.type}")
        if action.type == "wait_for_state":
            state_name = action.data.get("state")
            if state_name not in states:
                errors.append(f"wait_for_state references unknown state '{state_name}'")
        if action.type in {"click_template"}:
            target = action.data.get("target")
            if not target:
                errors.append(f"{action.type} must define target")
            elif not (profile_dir / str(target)).exists():
                errors.append(f"{action.type} target asset missing: {target}")
        if action.type == "click_point" and "region" not in action.data:
            errors.append("click_point must define region")
        if action.type in {"press_key", "hold_key"} and "key" not in action.data:
            errors.append(f"{action.type} must define key")
        if action.type == "wait" and "seconds" not in action.data:
            errors.append("wait must define seconds")


def _mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
