from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from game_script_dev.action_metadata import (
    ACTION_DEFINITIONS,
    SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES,
)

SUPPORTED_ANCHOR_TYPES = {"template", "text"}
SUPPORTED_ACTION_TYPES = set(ACTION_DEFINITIONS)
SUPPORTED_MOUSE_BUTTONS = {"left", "right"}
SUPPORTED_SCROLL_DIRECTIONS = {"up", "down"}
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
    "f1",
    "f4",
    "left",
    "left_shift",
    "right",
    "right_shift",
    "shift",
    "space",
    "tab",
    "up",
}
SUPPORTED_INPUT_MODES = {"foreground", "background_window_messages"}
DEFAULT_INPUT_MODE = "background_window_messages"
SUPPORTED_FOREGROUND_KEY_METHODS = {
    "sendinput_vk",
    "sendinput_scancode",
    "sendinput_vk_scancode",
    "sendinput_unicode",
    "keybd_event_vk",
    "keybd_event_scancode",
}
DEFAULT_FOREGROUND_KEY_METHOD = "sendinput_vk"
SUPPORTED_BACKGROUND_KEY_METHODS = {
    "post_message_simple",
    "post_message_scancode_all",
    "post_message_scancode_root",
    "send_message_timeout_scancode_all",
    "send_message_timeout_scancode_root",
}
DEFAULT_BACKGROUND_KEY_METHOD = "post_message_simple"
SUPPORTED_DETECTION_STRATEGIES = {"template_matching", "ocr_matching", "template_and_ocr"}
REQUIRED_COMPATIBILITY_CHECKS = {
    "target_identity",
    "supported_resolution",
    "required_assets",
    "full_state_graph",
    "terminal_states",
    "failure_transitions",
    "interruption_recovery",
    "known_limitations",
    "successful_validation_or_dry_run",
}


class ProfileValidationError(Exception):
    """Raised when a profile does not satisfy the strict schema."""


@dataclass(frozen=True)
class Target:
    process_name: str | None = None
    window_title_contains: str | None = None
    input_mode: str = DEFAULT_INPUT_MODE
    foreground_key_method: str = DEFAULT_FOREGROUND_KEY_METHOD
    background_key_method: str = DEFAULT_BACKGROUND_KEY_METHOD
    use_qwerty_physical_keys: bool = False


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
    disabled: bool = False


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
class ProfilePack:
    game: str
    game_mode: str
    detection_strategy: str
    known_limitations: list[str]
    compatibility: dict[str, bool]

    @property
    def compatibility_complete(self) -> bool:
        return all(
            self.compatibility.get(check) is True
            for check in REQUIRED_COMPATIBILITY_CHECKS
        )

    @property
    def missing_compatibility_checks(self) -> list[str]:
        return sorted(
            check
            for check in REQUIRED_COMPATIBILITY_CHECKS
            if self.compatibility.get(check) is not True
        )


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
    allow_infinite_run: bool = False
    manual_stop_is_dry_run_success: bool = False
    skip_dry_run_requirement: bool = False
    profile_pack: ProfilePack | None = None


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
        version=_integer(raw, "version", "version", default=1),
        name=_string(raw, "name"),
        target=Target(
            process_name=target_raw.get("process_name"),
            window_title_contains=target_raw.get("window_title_contains"),
            input_mode=str(target_raw.get("input_mode", DEFAULT_INPUT_MODE)),
            foreground_key_method=str(
                target_raw.get(
                    "foreground_key_method",
                    DEFAULT_FOREGROUND_KEY_METHOD,
                )
            ),
            background_key_method=str(
                target_raw.get(
                    "background_key_method",
                    DEFAULT_BACKGROUND_KEY_METHOD,
                )
            ),
            use_qwerty_physical_keys=_boolean(
                target_raw,
                "use_qwerty_physical_keys",
                default=False,
            ),
        ),
        resolution=Resolution(
            width=_integer(resolution_raw, "width", "window.resolution.width"),
            height=_integer(resolution_raw, "height", "window.resolution.height"),
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
        max_retries=_integer(
            execution_raw,
            "max_retries",
            "execution.max_retries",
            default=3,
        ),
        allow_infinite_run=_boolean(
            execution_raw,
            "allow_infinite_run",
            default=False,
        ),
        manual_stop_is_dry_run_success=_boolean(
            execution_raw,
            "manual_stop_is_dry_run_success",
            default=False,
        ),
        skip_dry_run_requirement=_boolean(
            execution_raw,
            "skip_dry_run_requirement",
            default=False,
        ),
        profile_pack=_profile_pack_from_mapping(raw.get("profile_pack")),
    )


def validate_profile(profile: Profile, profile_dir: Path) -> None:
    errors: list[str] = []

    if not profile.target.process_name and not profile.target.window_title_contains:
        errors.append("target must define process_name or window_title_contains")
    if profile.target.input_mode not in SUPPORTED_INPUT_MODES:
        errors.append(f"unknown target input_mode: {profile.target.input_mode}")
    if (
        profile.target.foreground_key_method
        not in SUPPORTED_FOREGROUND_KEY_METHODS
    ):
        errors.append(
            "unknown target foreground_key_method: "
            f"{profile.target.foreground_key_method}"
        )
    if (
        profile.target.background_key_method
        not in SUPPORTED_BACKGROUND_KEY_METHODS
    ):
        errors.append(
            "unknown target background_key_method: "
            f"{profile.target.background_key_method}"
        )

    if profile.resolution.policy not in {"verify_only", "attempt_resize", "ignore"}:
        errors.append(f"unknown resolution policy: {profile.resolution.policy}")

    if profile.profile_pack is not None:
        _validate_profile_pack(profile.profile_pack, errors)

    _validate_integer(
        profile.resolution.width,
        "window.resolution.width",
        errors,
        minimum=1,
    )
    _validate_integer(
        profile.resolution.height,
        "window.resolution.height",
        errors,
        minimum=1,
    )
    _validate_duration(
        profile.default_timeout_seconds,
        "execution.default_timeout_seconds",
        errors,
    )
    _validate_integer(profile.max_retries, "execution.max_retries", errors, minimum=1)

    if profile.initial_state not in profile.states:
        errors.append(f"initial_state is missing from states: {profile.initial_state}")

    for region in profile.regions.values():
        _validate_integer(region.x, f"region '{region.name}'.x", errors, minimum=0)
        _validate_integer(region.y, f"region '{region.name}'.y", errors, minimum=0)
        _validate_integer(
            region.width, f"region '{region.name}'.width", errors, minimum=1
        )
        _validate_integer(
            region.height, f"region '{region.name}'.height", errors, minimum=1
        )

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
            f"state '{state.name}' actions",
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
        _validate_integer(
            interruption.max_retries,
            f"interruption '{interruption.name}'.max_retries",
            errors,
            minimum=1,
        )
        _validate_anchors(interruption.required_anchors, profile_dir, errors)
        _validate_actions(
            interruption.recovery_actions,
            profile.states,
            profile.regions,
            profile_dir,
            errors,
            f"interruption '{interruption.name}' recovery_actions",
        )

    _validate_state_graph(profile, errors)
    _validate_continuous_input_lifecycle(profile, errors)

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

    if (
        not profile.allow_infinite_run
        and not any(profile.states[state_name].terminal for state_name in reachable)
    ):
        errors.append("state graph must include a reachable terminal state")

    _validate_failure_transition_loops(profile, errors)


def _state_successors(state: State) -> list[str]:
    successors: list[str] = []
    if state.on_success is not None:
        successors.append(state.on_success)
    if state.on_failure != "graceful_termination":
        successors.append(state.on_failure)
    return successors


def _validate_failure_transition_loops(
    profile: Profile,
    errors: list[str],
) -> None:
    reported: set[tuple[str, ...]] = set()
    for state_name in profile.states:
        path: list[str] = []
        current = state_name
        while current in profile.states:
            state = profile.states[current]
            if state.terminal or state.on_failure == "graceful_termination":
                break
            if current in path:
                cycle = path[path.index(current) :] + [current]
                key = tuple(cycle)
                if key not in reported:
                    reported.add(key)
                    errors.append(
                        "failure transition loop detected: " + " -> ".join(cycle)
                    )
                break
            path.append(current)
            current = state.on_failure


def _validate_continuous_input_lifecycle(
    profile: Profile,
    errors: list[str],
) -> None:
    if profile.initial_state not in profile.states:
        return

    pending: list[tuple[str, tuple[tuple[str, float | None], ...]]] = [
        (profile.initial_state, ())
    ]
    visited: set[tuple[str, tuple[tuple[str, float | None], ...]]] = set()
    reported: set[tuple[str, int, str]] = set()

    while pending:
        state_name, active_items = pending.pop()
        visit_key = (state_name, active_items)
        if visit_key in visited:
            continue
        visited.add(visit_key)

        state = profile.states[state_name]
        if state.terminal:
            continue

        active = dict(active_items)
        for index, action in enumerate(state.actions):
            if action.disabled:
                continue
            _expire_continuous_inputs(active)
            name = action.data.get("name")
            if not isinstance(name, str) or not name.strip():
                _advance_continuous_input_time(
                    active,
                    _action_duration_seconds(action),
                )
                continue
            name = name.strip()
            issue_key = (state_name, index, name)
            action_context = f"state '{state_name}' actions[{index}]"

            if action.type == "start_continuous_input":
                if name in active and issue_key not in reported:
                    reported.add(issue_key)
                    errors.append(
                        f"continuous input '{name}' is already active before "
                        f"{action_context}; stop it before starting it again"
                    )
                else:
                    stop_after = action.data.get("stop_after_seconds")
                    active[name] = (
                        float(stop_after)
                        if isinstance(stop_after, (int, float))
                        and not isinstance(stop_after, bool)
                        else None
                    )
            elif action.type == "stop_continuous_input":
                if name not in active and issue_key not in reported:
                    reported.add(issue_key)
                    errors.append(
                        f"continuous input '{name}' is not active before "
                        f"{action_context}; remove the stop or start it first"
                    )
                active.pop(name, None)

            _advance_continuous_input_time(
                active,
                _action_duration_seconds(action),
            )

        if state.on_success in profile.states:
            normalized_active = tuple(
                sorted(
                    (
                        name,
                        round(remaining, 9)
                        if remaining is not None
                        else None,
                    )
                    for name, remaining in active.items()
                )
            )
            pending.append((state.on_success, normalized_active))


def _expire_continuous_inputs(
    active: dict[str, float | None],
) -> None:
    for name in [
        name
        for name, remaining in active.items()
        if remaining is not None and remaining <= 0
    ]:
        active.pop(name, None)


def _advance_continuous_input_time(
    active: dict[str, float | None],
    seconds: float,
) -> None:
    if seconds <= 0:
        return
    for name, remaining in list(active.items()):
        if remaining is not None:
            active[name] = remaining - seconds
    _expire_continuous_inputs(active)


def _action_duration_seconds(action: Action) -> float:
    duration_field = {
        "hold_click": "seconds",
        "press_key": "seconds",
        "press_keys": "seconds",
        "hold_key": "seconds",
        "hold_keys": "seconds",
        "repeat_key": "repeat_for_seconds",
        "hold_key_while_repeating_key": "hold_seconds",
        "move_mouse": "seconds",
        "hold_mouse_button_and_move": "seconds",
        "wait": "seconds",
    }.get(action.type)
    if duration_field is None:
        return 0.0
    value = action.data.get(duration_field, 0.0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, float(value))
    return 0.0


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
        max_retries=_integer(
            raw,
            "max_retries",
            f"interruption '{_string(raw, 'name')}'.max_retries",
            default=1,
        ),
    )


def _profile_pack_from_mapping(raw: Any) -> ProfilePack | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("profile_pack must be a mapping")

    compatibility = raw.get("compatibility")
    if not isinstance(compatibility, dict):
        raise ValueError("profile_pack.compatibility must be a mapping")

    known_limitations = raw.get("known_limitations")
    if not isinstance(known_limitations, list):
        raise ValueError("profile_pack.known_limitations must be a list")

    return ProfilePack(
        game=_string(raw, "game"),
        game_mode=_string(raw, "game_mode"),
        detection_strategy=_string(raw, "detection_strategy"),
        known_limitations=known_limitations,
        compatibility={
            str(check): value for check, value in compatibility.items()
        },
    )


def _validate_profile_pack(profile_pack: ProfilePack, errors: list[str]) -> None:
    if profile_pack.detection_strategy not in SUPPORTED_DETECTION_STRATEGIES:
        errors.append(
            "profile_pack.detection_strategy uses unknown strategy "
            f"'{profile_pack.detection_strategy}'"
        )

    if not profile_pack.known_limitations:
        errors.append("profile_pack.known_limitations must include at least one item")
    for index, limitation in enumerate(profile_pack.known_limitations):
        if not isinstance(limitation, str) or not limitation.strip():
            errors.append(
                f"profile_pack.known_limitations[{index}] must be a non-empty string"
            )

    missing_checks = REQUIRED_COMPATIBILITY_CHECKS - profile_pack.compatibility.keys()
    for check in sorted(missing_checks):
        errors.append(f"profile_pack.compatibility.{check} is required")

    unknown_checks = profile_pack.compatibility.keys() - REQUIRED_COMPATIBILITY_CHECKS
    for check in sorted(unknown_checks):
        errors.append(f"profile_pack.compatibility.{check} is not supported")

    for check, value in profile_pack.compatibility.items():
        if not isinstance(value, bool):
            errors.append(f"profile_pack.compatibility.{check} must be a boolean")


def _region_from_mapping(name: str, raw: Any) -> ClickRegion:
    if not isinstance(raw, dict):
        raise ValueError(f"region '{name}' must be a mapping")

    return ClickRegion(
        name=name,
        x=_integer(raw, "x", f"region '{name}'.x"),
        y=_integer(raw, "y", f"region '{name}'.y"),
        width=_integer(raw, "width", f"region '{name}'.width"),
        height=_integer(raw, "height", f"region '{name}'.height"),
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
        disabled = item.get("disabled", False)
        if not isinstance(disabled, bool):
            raise ValueError("action disabled must be a boolean")
        actions.append(
            Action(
                type=action_type,
                data={
                    k: v
                    for k, v in item.items()
                    if k not in {"type", "disabled"}
                },
                disabled=disabled,
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
    context: str,
) -> None:
    for index, action in enumerate(actions):
        action_context = f"{context}[{index}].{action.type}"
        if action.type not in SUPPORTED_ACTION_TYPES:
            errors.append(f"{action_context} uses unknown action type")
            continue
        if action.disabled:
            continue
        if action.type == "wait_for_state":
            state_name = action.data.get("state")
            if state_name not in states:
                errors.append(
                    f"{action_context}.state references unknown state '{state_name}'"
                )
            if "timeout_seconds" in action.data:
                _validate_duration(
                    action.data["timeout_seconds"],
                    f"{action_context}.timeout_seconds",
                    errors,
                )
            if "poll_interval_seconds" in action.data:
                _validate_duration(
                    action.data["poll_interval_seconds"],
                    f"{action_context}.poll_interval_seconds",
                    errors,
                )
        if action.type in {"click_template"}:
            target = action.data.get("target")
            if not target:
                errors.append(f"{action_context}.target is required")
            elif not (profile_dir / str(target)).exists():
                errors.append(f"{action_context}.target asset missing: {target}")
        if action.type in {"click_point", "hold_click"}:
            region = action.data.get("region")
            if not region:
                errors.append(f"{action_context}.region is required")
            elif region not in regions:
                errors.append(
                    f"{action_context}.region references unknown region '{region}'"
                )
            if "input_mode" in action.data:
                input_mode = str(action.data["input_mode"])
                if input_mode not in SUPPORTED_INPUT_MODES:
                    errors.append(
                        f"{action_context}.input_mode uses unknown input mode '{input_mode}'"
                    )
        if action.type == "hold_click":
            if "seconds" not in action.data:
                errors.append(f"{action_context}.seconds is required")
            else:
                _validate_duration(
                    action.data["seconds"], f"{action_context}.seconds", errors
                )
        if action.type in {"press_key", "hold_key", "repeat_key"}:
            if "key" not in action.data:
                errors.append(f"{action_context}.key is required")
            else:
                _validate_key(action.data["key"], f"{action_context}.key", errors)
        if action.type in {"press_keys", "hold_keys"}:
            if "keys" not in action.data:
                errors.append(f"{action_context}.keys is required")
            else:
                _validate_keys(action.data["keys"], f"{action_context}.keys", errors)
        if action.type in {"press_key", "press_keys"} and "seconds" in action.data:
            _validate_duration(
                action.data["seconds"], f"{action_context}.seconds", errors
            )
        if action.type in {"hold_key", "hold_keys"} and "seconds" in action.data:
            _validate_duration(
                action.data["seconds"], f"{action_context}.seconds", errors
            )
        if action.type == "repeat_key":
            if "repeat_for_seconds" not in action.data:
                errors.append(f"{action_context}.repeat_for_seconds is required")
            else:
                _validate_duration(
                    action.data["repeat_for_seconds"],
                    f"{action_context}.repeat_for_seconds",
                    errors,
                )
            if "repeat_every_seconds" not in action.data:
                errors.append(f"{action_context}.repeat_every_seconds is required")
            else:
                _validate_positive_duration(
                    action.data["repeat_every_seconds"],
                    f"{action_context}.repeat_every_seconds",
                    errors,
                )
            if "tap_duration_seconds" in action.data:
                _validate_duration(
                    action.data["tap_duration_seconds"],
                    f"{action_context}.tap_duration_seconds",
                    errors,
                )
        if action.type == "hold_key_while_repeating_key":
            if "hold_key" not in action.data:
                errors.append(f"{action_context}.hold_key is required")
            else:
                _validate_key(
                    action.data["hold_key"],
                    f"{action_context}.hold_key",
                    errors,
                )
            if "tap_key" not in action.data:
                errors.append(f"{action_context}.tap_key is required")
            else:
                _validate_key(
                    action.data["tap_key"],
                    f"{action_context}.tap_key",
                    errors,
                )
            if "hold_seconds" not in action.data:
                errors.append(f"{action_context}.hold_seconds is required")
            else:
                _validate_duration(
                    action.data["hold_seconds"],
                    f"{action_context}.hold_seconds",
                    errors,
                )
            if "tap_every_seconds" not in action.data:
                errors.append(f"{action_context}.tap_every_seconds is required")
            else:
                _validate_positive_duration(
                    action.data["tap_every_seconds"],
                    f"{action_context}.tap_every_seconds",
                    errors,
                )
            if "tap_duration_seconds" in action.data:
                _validate_duration(
                    action.data["tap_duration_seconds"],
                    f"{action_context}.tap_duration_seconds",
                    errors,
                )
        if action.type in {"move_mouse", "hold_mouse_button_and_move"}:
            _validate_mouse_move_action(action, action_context, errors)
        if action.type == "scroll_mouse":
            _validate_scroll_mouse_action(action, action_context, errors)
        if action.type == "start_continuous_input":
            _validate_continuous_input_action(
                action,
                action_context,
                regions,
                errors,
            )
        if action.type == "stop_continuous_input":
            name = action.data.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{action_context}.name is required")
        if action.type == "wait":
            if "seconds" not in action.data:
                errors.append(f"{action_context}.seconds is required")
            else:
                _validate_duration(
                    action.data["seconds"], f"{action_context}.seconds", errors
                )


def _validate_continuous_input_action(
    action: Action,
    action_context: str,
    regions: dict[str, ClickRegion],
    errors: list[str],
) -> None:
    name = action.data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{action_context}.name is required")

    _validate_continuous_action_payload(
        action.data,
        action_context,
        regions,
        errors,
        duration_field="stop_after_seconds",
        duration_required=False,
        allow_sequence=True,
    )


def _validate_continuous_action_payload(
    data: dict[str, Any],
    action_context: str,
    regions: dict[str, ClickRegion],
    errors: list[str],
    *,
    duration_field: str,
    duration_required: bool,
    allow_sequence: bool,
) -> None:
    continuous_action = data.get("action")
    allowed_actions = set(SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES) - {"sequence"}
    if allow_sequence:
        allowed_actions.add("sequence")
    if continuous_action not in allowed_actions:
        errors.append(
            f"{action_context}.action must be one of: {', '.join(sorted(allowed_actions))}"
        )
        return

    if duration_field in data:
        _validate_positive_duration(
            data[duration_field],
            f"{action_context}.{duration_field}",
            errors,
        )
    elif duration_required:
        errors.append(f"{action_context}.{duration_field} is required")

    if continuous_action == "sequence":
        sequence = data.get("sequence")
        if not isinstance(sequence, list):
            errors.append(f"{action_context}.sequence must be a list")
            return
        if not sequence:
            errors.append(f"{action_context}.sequence must not be empty")
            return
        for index, step in enumerate(sequence):
            step_context = f"{action_context}.sequence[{index}]"
            if not isinstance(step, dict):
                errors.append(f"{step_context} must be an object")
                continue
            _validate_continuous_action_payload(
                step,
                step_context,
                regions,
                errors,
                duration_field="run_for_seconds",
                duration_required=True,
                allow_sequence=False,
            )
        return

    if continuous_action in {"press_key", "hold_key", "repeat_key"}:
        if "key" not in data:
            errors.append(f"{action_context}.key is required")
        else:
            _validate_key(data["key"], f"{action_context}.key", errors)

    if continuous_action in {"click_point", "hold_click"}:
        region = data.get("region")
        if not region:
            errors.append(f"{action_context}.region is required")
        elif region not in regions:
            errors.append(
                f"{action_context}.region references unknown region '{region}'"
            )
        if "input_mode" in data:
            input_mode = str(data["input_mode"])
            if input_mode not in SUPPORTED_INPUT_MODES:
                errors.append(
                    f"{action_context}.input_mode uses unknown input mode '{input_mode}'"
                )

    if continuous_action == "click_point":
        if "repeat_every_seconds" not in data:
            errors.append(f"{action_context}.repeat_every_seconds is required")
        else:
            _validate_positive_duration(
                data["repeat_every_seconds"],
                f"{action_context}.repeat_every_seconds",
                errors,
            )

    if continuous_action == "scroll_mouse":
        direction = data.get("direction")
        if not isinstance(direction, str) or not direction.strip():
            errors.append(f"{action_context}.direction is required")
        else:
            normalized = direction.strip().lower()
            if normalized not in SUPPORTED_SCROLL_DIRECTIONS:
                errors.append(
                    f"{action_context}.direction must be one of: "
                    f"{', '.join(sorted(SUPPORTED_SCROLL_DIRECTIONS))}"
                )
        if "steps" in data:
            _validate_integer(
                data["steps"],
                f"{action_context}.steps",
                errors,
                minimum=1,
            )
        if "repeat_every_seconds" not in data:
            errors.append(f"{action_context}.repeat_every_seconds is required")
        else:
            _validate_positive_duration(
                data["repeat_every_seconds"],
                f"{action_context}.repeat_every_seconds",
                errors,
            )
        if "input_mode" in data:
            input_mode = str(data["input_mode"])
            if input_mode not in SUPPORTED_INPUT_MODES:
                errors.append(
                    f"{action_context}.input_mode uses unknown input mode '{input_mode}'"
                )

    if continuous_action in {"press_keys", "hold_keys"}:
        if "keys" not in data:
            errors.append(f"{action_context}.keys is required")
        else:
            _validate_keys(data["keys"], f"{action_context}.keys", errors)

    if continuous_action in {"press_key", "press_keys"}:
        if "repeat_every_seconds" not in data:
            errors.append(f"{action_context}.repeat_every_seconds is required")
        else:
            _validate_positive_duration(
                data["repeat_every_seconds"],
                f"{action_context}.repeat_every_seconds",
                errors,
            )
        if "seconds" in data:
            _validate_duration(
                data["seconds"],
                f"{action_context}.seconds",
                errors,
            )

    if continuous_action in {"repeat_key", "hold_key_while_repeating_key"}:
        if "tap_duration_seconds" in data:
            _validate_duration(
                data["tap_duration_seconds"],
                f"{action_context}.tap_duration_seconds",
                errors,
            )

    if continuous_action == "repeat_key":
        if "repeat_every_seconds" not in data:
            errors.append(f"{action_context}.repeat_every_seconds is required")
        else:
            _validate_positive_duration(
                data["repeat_every_seconds"],
                f"{action_context}.repeat_every_seconds",
                errors,
            )

    if continuous_action == "hold_key_while_repeating_key":
        if "hold_key" not in data:
            errors.append(f"{action_context}.hold_key is required")
        else:
            _validate_key(
                data["hold_key"],
                f"{action_context}.hold_key",
                errors,
            )
        if "tap_key" not in data:
            errors.append(f"{action_context}.tap_key is required")
        else:
            _validate_key(
                data["tap_key"],
                f"{action_context}.tap_key",
                errors,
            )
        if "tap_every_seconds" not in data:
            errors.append(f"{action_context}.tap_every_seconds is required")
        else:
            _validate_positive_duration(
                data["tap_every_seconds"],
                f"{action_context}.tap_every_seconds",
                errors,
            )


def _validate_mouse_move_action(
    action: Action,
    action_context: str,
    errors: list[str],
) -> None:
    if "dx" not in action.data:
        errors.append(f"{action_context}.dx is required")
    else:
        _validate_number(action.data["dx"], f"{action_context}.dx", errors)
    if "dy" not in action.data:
        errors.append(f"{action_context}.dy is required")
    else:
        _validate_number(action.data["dy"], f"{action_context}.dy", errors)
    if "seconds" in action.data:
        _validate_duration(action.data["seconds"], f"{action_context}.seconds", errors)
    if "input_mode" in action.data:
        input_mode = str(action.data["input_mode"])
        if input_mode not in SUPPORTED_INPUT_MODES:
            errors.append(
                f"{action_context}.input_mode uses unknown input mode '{input_mode}'"
            )
        elif input_mode != "foreground":
            errors.append(
                f"{action_context}.input_mode must be foreground for mouse-look actions"
            )
    if action.type == "hold_mouse_button_and_move":
        if "button" not in action.data:
            errors.append(f"{action_context}.button is required")
        else:
            _validate_mouse_button(
                action.data["button"],
                f"{action_context}.button",
                errors,
            )


def _validate_scroll_mouse_action(
    action: Action,
    action_context: str,
    errors: list[str],
) -> None:
    direction = action.data.get("direction")
    if not isinstance(direction, str) or not direction.strip():
        errors.append(f"{action_context}.direction is required")
    else:
        normalized = direction.strip().lower()
        if normalized not in SUPPORTED_SCROLL_DIRECTIONS:
            errors.append(
                f"{action_context}.direction must be one of: "
                f"{', '.join(sorted(SUPPORTED_SCROLL_DIRECTIONS))}"
            )

    if "steps" in action.data:
        _validate_integer(
            action.data["steps"],
            f"{action_context}.steps",
            errors,
            minimum=1,
        )
    if "input_mode" in action.data:
        input_mode = str(action.data["input_mode"])
        if input_mode not in SUPPORTED_INPUT_MODES:
            errors.append(
                f"{action_context}.input_mode uses unknown input mode '{input_mode}'"
            )


def _validate_duration(value: object, label: str, errors: list[str]) -> None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number")
        return

    if not math.isfinite(seconds) or seconds < 0:
        errors.append(f"{label} must be a finite non-negative number")


def _validate_positive_duration(value: object, label: str, errors: list[str]) -> None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number")
        return

    if not math.isfinite(seconds) or seconds <= 0:
        errors.append(f"{label} must be a finite positive number")


def _validate_number(value: object, label: str, errors: list[str]) -> None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number")
        return

    if not math.isfinite(number):
        errors.append(f"{label} must be finite")


def _validate_integer(
    value: object,
    label: str,
    errors: list[str],
    minimum: int,
) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{label} must be an integer")
        return
    if value < minimum:
        errors.append(f"{label} must be at least {minimum}")


def _validate_key(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return

    normalized = value.strip().lower()
    if normalized not in SUPPORTED_KEY_NAMES:
        errors.append(f"{label} uses unsupported key '{value}'")


def _validate_mouse_button(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return

    normalized = value.strip().lower()
    if normalized not in SUPPORTED_MOUSE_BUTTONS:
        errors.append(f"{label} uses unsupported mouse button '{value}'")


def _validate_keys(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return
    if not value:
        errors.append(f"{label} must not be empty")
        return
    for index, item in enumerate(value):
        _validate_key(item, f"{label}[{index}]", errors)


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


def _integer(
    raw: dict[str, Any],
    key: str,
    label: str,
    default: int | None = None,
) -> int:
    if key not in raw:
        if default is None:
            raise ValueError(f"{label} is required")
        return default

    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _boolean(
    raw: dict[str, Any],
    key: str,
    *,
    default: bool,
) -> bool:
    if key not in raw:
        return default

    value = raw[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value
