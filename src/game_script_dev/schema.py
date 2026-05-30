from __future__ import annotations

import math
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
SUPPORTED_KEY_NAMES = {
    *{chr(code).lower() for code in range(ord("A"), ord("Z") + 1)},
    *{str(number) for number in range(10)},
    "alt",
    "backspace",
    "control",
    "ctrl",
    "down",
    "enter",
    "esc",
    "escape",
    "left",
    "right",
    "shift",
    "space",
    "tab",
    "up",
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
class ClickRegion:
    name: str
    x: int
    y: int
    width: int
    height: int


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
    regions: dict[str, ClickRegion] = field(default_factory=dict)
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
    regions_raw = raw.get("regions", {})
    if not isinstance(regions_raw, dict):
        raise ValueError("regions must be a mapping")
    regions = {
        region_name: _region_from_mapping(region_name, region_raw)
        for region_name, region_raw in regions_raw.items()
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
        regions=regions,
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

    _validate_duration(
        profile.default_timeout_seconds,
        "execution default_timeout_seconds",
        errors,
    )

    if profile.initial_state not in profile.states:
        errors.append(f"initial_state is missing from states: {profile.initial_state}")

    for state in profile.states.values():
        _validate_anchors(state.required_anchors, profile_dir, errors)
        _validate_anchors(state.optional_anchors, profile_dir, errors)
        _validate_anchors(state.forbidden_anchors, profile_dir, errors)
        _validate_actions(
            state.actions,
            profile.states,
            profile.regions,
            profile_dir,
            errors,
        )

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
            profile.regions,
            profile_dir,
            errors,
        )

    _validate_state_graph(profile, errors)

    if errors:
        raise ProfileValidationError("; ".join(errors))


def _validate_state_graph(profile: Profile, errors: list[str]) -> None:
    if profile.initial_state not in profile.states:
        return

    reachable = {profile.initial_state}
    pending = [profile.initial_state]
    while pending:
        state = profile.states[pending.pop()]
        for next_state in _state_successors(state):
            if next_state in profile.states and next_state not in reachable:
                reachable.add(next_state)
                pending.append(next_state)

    for state_name in sorted(set(profile.states) - reachable):
        errors.append(f"state '{state_name}' is unreachable from initial_state")

    if not any(profile.states[state_name].terminal for state_name in reachable):
        errors.append("state graph must include a reachable terminal state")


def _state_successors(state: State) -> list[str]:
    successors: list[str] = []
    if state.on_success is not None:
        successors.append(state.on_success)
    if state.on_failure != "graceful_termination":
        successors.append(state.on_failure)
    return successors


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


def _region_from_mapping(name: str, raw: Any) -> ClickRegion:
    if not isinstance(raw, dict):
        raise ValueError(f"region '{name}' must be a mapping")

    return ClickRegion(
        name=name,
        x=int(raw["x"]),
        y=int(raw["y"]),
        width=int(raw["width"]),
        height=int(raw["height"]),
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
    regions: dict[str, ClickRegion],
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
            if "timeout_seconds" in action.data:
                _validate_duration(
                    action.data["timeout_seconds"],
                    "wait_for_state timeout_seconds",
                    errors,
                )
            if "poll_interval_seconds" in action.data:
                _validate_duration(
                    action.data["poll_interval_seconds"],
                    "wait_for_state poll_interval_seconds",
                    errors,
                )
        if action.type in {"click_template"}:
            target = action.data.get("target")
            if not target:
                errors.append(f"{action.type} must define target")
            elif not (profile_dir / str(target)).exists():
                errors.append(f"{action.type} target asset missing: {target}")
        if action.type == "click_point":
            region = action.data.get("region")
            if not region:
                errors.append("click_point must define region")
            elif region not in regions:
                errors.append(f"click_point references unknown region '{region}'")
        if action.type in {"press_key", "hold_key"}:
            if "key" not in action.data:
                errors.append(f"{action.type} must define key")
            else:
                _validate_key(action.data["key"], action.type, errors)
        if action.type == "hold_key" and "seconds" in action.data:
            _validate_duration(action.data["seconds"], "hold_key seconds", errors)
        if action.type == "wait":
            if "seconds" not in action.data:
                errors.append("wait must define seconds")
            else:
                _validate_duration(action.data["seconds"], "wait seconds", errors)


def _validate_duration(value: object, label: str, errors: list[str]) -> None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number")
        return

    if not math.isfinite(seconds) or seconds < 0:
        errors.append(f"{label} must be a finite non-negative number")


def _validate_key(value: object, action_type: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{action_type} key must be a non-empty string")
        return

    normalized = value.strip().lower()
    if normalized not in SUPPORTED_KEY_NAMES:
        errors.append(f"{action_type} uses unsupported key '{value}'")


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
