from __future__ import annotations

from pathlib import Path

import yaml

from game_script_dev.authoring import check_profile_pack
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import (
    ACTION_DEFINITIONS,
    REQUIRED_COMPATIBILITY_CHECKS,
    SUPPORTED_ANCHOR_TYPES,
    SUPPORTED_BACKGROUND_KEY_METHODS,
    SUPPORTED_DETECTION_STRATEGIES,
    SUPPORTED_FOREGROUND_KEY_METHODS,
    SUPPORTED_INPUT_MODES,
    SUPPORTED_KEY_NAMES,
    SUPPORTED_MOUSE_BUTTONS,
    SUPPORTED_SCROLL_DIRECTIONS,
    Action,
    Anchor,
    ClickRegion,
    Interruption,
    Profile,
    ProfileValidationError,
    State,
    profile_from_mapping,
    collect_validation_errors,
)

EDITABLE_ACTION_TYPES = (
    "click_template",
    "hold_click",
    "log",
    "move_mouse",
    "press_keys",
    "wait",
    "press_key",
    "hold_key",
    "hold_keys",
    "repeat_key",
    "hold_key_while_repeating_key",
    "hold_mouse_button_and_move",
    "scroll_mouse",
    "click_point",
    "start_continuous_input",
    "stop_continuous_input",
    "wait_for_state",
    "stop",
)

CONTINUOUS_ACTION_DEFINITIONS: dict[str, dict[str, object]] = {
    "click_point": {
        "label": "Continuous Click Point",
        "fields": [
            {"name": "region", "kind": "region", "required": True},
            {"name": "input_mode", "kind": "input_mode", "required": False},
            {"name": "repeat_every_seconds", "kind": "duration", "required": True},
        ],
    },
    "hold_click": {
        "label": "Continuous Hold Click",
        "fields": [
            {"name": "region", "kind": "region", "required": True},
            {"name": "input_mode", "kind": "input_mode", "required": False},
        ],
    },
    "press_key": {
        "label": "Continuous Press Key",
        "fields": [
            {"name": "key", "kind": "key", "required": True},
            {"name": "repeat_every_seconds", "kind": "duration", "required": True},
            {"name": "seconds", "kind": "duration", "required": False},
        ],
    },
    "press_keys": {
        "label": "Continuous Press Keys",
        "fields": [
            {"name": "keys", "kind": "key_list", "required": True},
            {"name": "repeat_every_seconds", "kind": "duration", "required": True},
            {"name": "seconds", "kind": "duration", "required": False},
        ],
    },
    "hold_key": {
        "label": "Continuous Hold Key",
        "fields": [
            {"name": "key", "kind": "key", "required": True},
        ],
    },
    "hold_keys": {
        "label": "Continuous Hold Keys",
        "fields": [
            {"name": "keys", "kind": "key_list", "required": True},
        ],
    },
    "repeat_key": {
        "label": "Continuous Repeat Key",
        "fields": [
            {"name": "key", "kind": "key", "required": True},
            {"name": "repeat_every_seconds", "kind": "duration", "required": True},
            {"name": "tap_duration_seconds", "kind": "duration", "required": False},
        ],
    },
    "hold_key_while_repeating_key": {
        "label": "Continuous Hold Key While Repeating Key",
        "fields": [
            {"name": "hold_key", "kind": "key", "required": True},
            {"name": "tap_key", "kind": "key", "required": True},
            {"name": "tap_every_seconds", "kind": "duration", "required": True},
            {"name": "tap_duration_seconds", "kind": "duration", "required": False},
        ],
    },
    "scroll_mouse": {
        "label": "Continuous Scroll Mouse",
        "fields": [
            {"name": "direction", "kind": "scroll_direction", "required": True},
            {"name": "steps", "kind": "integer", "required": False},
            {"name": "input_mode", "kind": "input_mode", "required": False},
            {"name": "repeat_every_seconds", "kind": "duration", "required": True},
        ],
    },
    "sequence": {
        "label": "Continuous Sequence",
        "fields": [
            {"name": "sequence", "kind": "continuous_sequence", "required": True},
        ],
    },
}


def build_profile_draft(profile_id: str, profile_path: Path) -> dict[str, object]:
    source = profile_path.read_text(encoding="utf-8")
    notes = read_profile_notes(profile_path)
    try:
        profile = load_profile(profile_path)
    except ProfileLoadError as error:
        return {
            "profile_id": profile_id,
            "path": str(profile_path),
            "source": source,
            "notes": notes,
            "profile": None,
            "validation_errors": [str(error)],
            "load_error": str(error),
            "valid": False,
            "graph": None,
            "pack_check": None,
        }

    return build_profile_payload(
        profile_id,
        profile_path,
        profile,
        source=source,
        notes=notes,
    )


def preview_profile_draft(
    profile_id: str,
    profile_path: Path,
    profile_payload: object,
) -> dict[str, object]:
    notes = read_profile_notes(profile_path)
    try:
        notes = normalize_notes_payload(
            profile_payload.get("notes") if isinstance(profile_payload, dict) else None,
            fallback=notes,
        )
    except ValueError as error:
        return {
            "profile_id": profile_id,
            "path": str(profile_path),
            "source": "",
            "notes": read_profile_notes(profile_path),
            "profile": None,
            "validation_errors": [str(error)],
            "load_error": str(error),
            "valid": False,
            "graph": None,
            "pack_check": None,
        }
    try:
        mapping = profile_mapping_from_payload(profile_payload)
    except ValueError as error:
        return {
            "profile_id": profile_id,
            "path": str(profile_path),
            "source": "",
            "notes": notes,
            "profile": None,
            "validation_errors": [str(error)],
            "load_error": str(error),
            "valid": False,
            "graph": None,
            "pack_check": None,
        }

    source = dump_profile_mapping(mapping)
    try:
        profile = profile_from_mapping(mapping)
    except ValueError as error:
        return {
            "profile_id": profile_id,
            "path": str(profile_path),
            "source": source,
            "notes": notes,
            "profile": None,
            "validation_errors": [str(error)],
            "load_error": str(error),
            "valid": False,
            "graph": None,
            "pack_check": None,
        }

    return build_profile_payload(
        profile_id,
        profile_path,
        profile,
        source=source,
        notes=notes,
    )


def save_profile_draft(
    profile_id: str,
    profile_path: Path,
    profile_payload: object,
) -> dict[str, object]:
    draft = preview_profile_draft(profile_id, profile_path, profile_payload)
    if not draft["valid"]:
        return draft
    profile_path.write_text(str(draft["source"]), encoding="utf-8")
    notes_path = profile_path.parent / "notes.md"
    notes_path.write_text(str(draft["notes"]), encoding="utf-8")
    return build_profile_draft(profile_id, profile_path)


def validate_profile_draft(profile_path: Path) -> dict[str, object]:
    try:
        profile = load_profile(profile_path)
    except ProfileLoadError as error:
        return {
            "valid": False,
            "errors": [str(error)],
        }

    try:
        errors = collect_validation_errors(profile, profile_path.parent)
    except ProfileValidationError as error:
        return {
            "valid": False,
            "errors": [str(error)],
        }
    return {
        "valid": not errors,
        "errors": errors,
    }


def profile_schema_payload() -> dict[str, object]:
    return {
        "actions": ACTION_DEFINITIONS,
        "continuous_actions": CONTINUOUS_ACTION_DEFINITIONS,
        "editable_action_types": list(EDITABLE_ACTION_TYPES),
        "supported_anchor_types": sorted(SUPPORTED_ANCHOR_TYPES),
        "supported_input_modes": sorted(SUPPORTED_INPUT_MODES),
        "supported_foreground_key_methods": sorted(SUPPORTED_FOREGROUND_KEY_METHODS),
        "supported_background_key_methods": sorted(SUPPORTED_BACKGROUND_KEY_METHODS),
        "supported_detection_strategies": sorted(SUPPORTED_DETECTION_STRATEGIES),
        "supported_keys": sorted(SUPPORTED_KEY_NAMES),
        "supported_mouse_buttons": sorted(SUPPORTED_MOUSE_BUTTONS),
        "supported_scroll_directions": sorted(SUPPORTED_SCROLL_DIRECTIONS),
        "required_compatibility_checks": sorted(REQUIRED_COMPATIBILITY_CHECKS),
    }


def build_profile_payload(
    profile_id: str,
    profile_path: Path,
    profile: Profile,
    *,
    source: str,
    notes: str,
) -> dict[str, object]:
    validation_errors = collect_validation_errors(profile, profile_path.parent)
    pack_check = check_profile_pack(profile_path.parent)
    return {
        "profile_id": profile_id,
        "path": str(profile_path),
        "source": source,
        "notes": notes,
        "profile": serialize_profile(profile),
        "validation_errors": validation_errors,
        "load_error": None,
        "valid": not validation_errors,
        "graph": build_graph_summary(profile),
        "pack_check": {
            "ok": pack_check.ok,
            "errors": pack_check.errors,
            "warnings": pack_check.warnings,
        },
    }


def serialize_profile(profile: Profile) -> dict[str, object]:
    return {
        "version": profile.version,
        "name": profile.name,
        "initial_state": profile.initial_state,
        "target": {
            "process_name": profile.target.process_name,
            "window_title_contains": profile.target.window_title_contains,
            "input_mode": profile.target.input_mode,
            "foreground_key_method": profile.target.foreground_key_method,
            "background_key_method": profile.target.background_key_method,
            "use_qwerty_physical_keys": profile.target.use_qwerty_physical_keys,
        },
        "resolution": {
            "width": profile.resolution.width,
            "height": profile.resolution.height,
            "policy": profile.resolution.policy,
        },
        "execution": {
            "default_timeout_seconds": profile.default_timeout_seconds,
            "max_retries": profile.max_retries,
            "allow_infinite_run": profile.allow_infinite_run,
            "manual_stop_is_dry_run_success": profile.manual_stop_is_dry_run_success,
        },
        "profile_pack": serialize_profile_pack(profile.profile_pack),
        "regions": [serialize_region(region) for region in profile.regions.values()],
        "interruptions": [
            serialize_interruption(interruption) for interruption in profile.interruptions
        ],
        "states": [serialize_state(state) for state in profile.states.values()],
    }


def read_profile_notes(profile_path: Path) -> str:
    notes_path = profile_path.parent / "notes.md"
    if not notes_path.is_file():
        return ""
    return notes_path.read_text(encoding="utf-8")


def normalize_notes_payload(notes_payload: object, *, fallback: str) -> str:
    if notes_payload is None:
        return fallback
    if not isinstance(notes_payload, str):
        raise ValueError("notes must be a string")
    return notes_payload


def build_graph_summary(profile: Profile) -> dict[str, object]:
    reachable = compute_reachable_states(profile)
    edges: list[dict[str, object]] = []
    for state in profile.states.values():
        if state.on_success:
            edges.append(
                {
                    "from": state.name,
                    "to": state.on_success,
                    "kind": "success",
                    "valid": state.on_success in profile.states,
                }
            )
        if state.on_failure != "graceful_termination":
            edges.append(
                {
                    "from": state.name,
                    "to": state.on_failure,
                    "kind": "failure",
                    "valid": state.on_failure in profile.states,
                }
            )
    terminal_states = sorted(
        state.name for state in profile.states.values() if state.terminal
    )
    reachable_terminal_states = sorted(
        state_name for state_name in terminal_states if state_name in reachable
    )
    return {
        "reachable_states": sorted(reachable),
        "unreachable_states": sorted(set(profile.states) - reachable),
        "terminal_states": terminal_states,
        "reachable_terminal_states": reachable_terminal_states,
        "has_reachable_terminal_state": bool(reachable_terminal_states),
        "edges": edges,
    }


def compute_reachable_states(profile: Profile) -> set[str]:
    if profile.initial_state not in profile.states:
        return set()
    reachable = {profile.initial_state}
    pending = [profile.initial_state]
    while pending:
        current = pending.pop()
        state = profile.states[current]
        next_states = []
        if state.on_success:
            next_states.append(state.on_success)
        if state.on_failure != "graceful_termination":
            next_states.append(state.on_failure)
        for next_state in next_states:
            if next_state in profile.states and next_state not in reachable:
                reachable.add(next_state)
                pending.append(next_state)
    return reachable


def serialize_state(state: State) -> dict[str, object]:
    return {
        "name": state.name,
        "required_anchors": [serialize_anchor(anchor) for anchor in state.required_anchors],
        "optional_anchors": [serialize_anchor(anchor) for anchor in state.optional_anchors],
        "forbidden_anchors": [serialize_anchor(anchor) for anchor in state.forbidden_anchors],
        "actions": [
            {
                "type": action.type,
                "label": ACTION_DEFINITIONS.get(action.type, {}).get("label", action.type),
                "editable": action.type in EDITABLE_ACTION_TYPES,
                "data": action.data,
            }
            for action in state.actions
        ],
        "on_success": state.on_success,
        "on_failure": state.on_failure,
        "terminal": state.terminal,
        "result": state.result,
    }


def serialize_anchor(anchor: Anchor) -> dict[str, object]:
    return {
        "name": anchor.name,
        "type": anchor.type,
        "asset": anchor.asset,
        "text": anchor.text,
    }


def serialize_region(region: ClickRegion) -> dict[str, object]:
    return {
        "name": region.name,
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
    }


def serialize_interruption(interruption: Interruption) -> dict[str, object]:
    return {
        "name": interruption.name,
        "required_anchors": [
            serialize_anchor(anchor) for anchor in interruption.required_anchors
        ],
        "recovery_actions": [
            {
                "type": action.type,
                "label": ACTION_DEFINITIONS.get(action.type, {}).get("label", action.type),
                "editable": action.type in EDITABLE_ACTION_TYPES,
                "data": action.data,
            }
            for action in interruption.recovery_actions
        ],
        "max_retries": interruption.max_retries,
    }


def serialize_profile_pack(profile_pack: object) -> dict[str, object] | None:
    if profile_pack is None:
        return None
    return {
        "game": profile_pack.game,
        "game_mode": profile_pack.game_mode,
        "detection_strategy": profile_pack.detection_strategy,
        "known_limitations": profile_pack.known_limitations,
        "compatibility": profile_pack.compatibility,
        "compatibility_complete": profile_pack.compatibility_complete,
        "missing_compatibility_checks": profile_pack.missing_compatibility_checks,
    }


def profile_mapping_from_payload(profile_payload: object) -> dict[str, object]:
    if not isinstance(profile_payload, dict):
        raise ValueError("profile draft must be an object")

    states_raw = profile_payload.get("states")
    if not isinstance(states_raw, list):
        raise ValueError("profile draft states must be a list")

    mapping: dict[str, object] = {
        "version": _coerce_int(profile_payload.get("version"), "version"),
        "name": _coerce_string(profile_payload.get("name"), "name"),
        "target": profile_target_mapping(profile_payload.get("target")),
        "window": {
            "resolution": profile_resolution_mapping(profile_payload.get("resolution"))
        },
        "execution": profile_execution_mapping(profile_payload.get("execution")),
        "initial_state": _coerce_string(
            profile_payload.get("initial_state"),
            "initial_state",
        ),
        "states": {
            state_mapping["name"]: state_mapping_to_yaml(state_mapping)
            for state_mapping in [profile_state_mapping(item) for item in states_raw]
        },
    }

    regions = profile_regions_mapping(profile_payload.get("regions", []))
    if regions:
        mapping["regions"] = regions

    interruptions = profile_interruptions_mapping(
        profile_payload.get("interruptions", [])
    )
    if interruptions:
        mapping["interruptions"] = interruptions

    profile_pack = serialize_profile_pack_payload(profile_payload.get("profile_pack"))
    if profile_pack is not None:
        mapping["profile_pack"] = profile_pack

    return mapping


def dump_profile_mapping(mapping: dict[str, object]) -> str:
    return yaml.safe_dump(
        mapping,
        sort_keys=False,
        allow_unicode=True,
    )


def profile_target_mapping(target_payload: object) -> dict[str, object]:
    if not isinstance(target_payload, dict):
        raise ValueError("target must be an object")
    target: dict[str, object] = {}
    if target_payload.get("process_name"):
        target["process_name"] = str(target_payload["process_name"])
    if target_payload.get("window_title_contains"):
        target["window_title_contains"] = str(target_payload["window_title_contains"])
    if target_payload.get("input_mode"):
        target["input_mode"] = str(target_payload["input_mode"])
    if target_payload.get("foreground_key_method"):
        target["foreground_key_method"] = str(target_payload["foreground_key_method"])
    if target_payload.get("background_key_method"):
        target["background_key_method"] = str(target_payload["background_key_method"])
    if target_payload.get("use_qwerty_physical_keys"):
        target["use_qwerty_physical_keys"] = bool(
            target_payload["use_qwerty_physical_keys"]
        )
    return target


def profile_resolution_mapping(resolution_payload: object) -> dict[str, object]:
    if not isinstance(resolution_payload, dict):
        raise ValueError("resolution must be an object")
    resolution = {
        "width": _coerce_int(resolution_payload.get("width"), "resolution.width"),
        "height": _coerce_int(resolution_payload.get("height"), "resolution.height"),
    }
    policy = resolution_payload.get("policy")
    if policy:
        resolution["policy"] = str(policy)
    return resolution


def profile_execution_mapping(execution_payload: object) -> dict[str, object]:
    if not isinstance(execution_payload, dict):
        raise ValueError("execution must be an object")
    execution: dict[str, object] = {}
    timeout = execution_payload.get("default_timeout_seconds")
    retries = execution_payload.get("max_retries")
    if timeout is not None:
        execution["default_timeout_seconds"] = float(timeout)
    if retries is not None:
        execution["max_retries"] = _coerce_int(retries, "execution.max_retries")
    if execution_payload.get("allow_infinite_run"):
        execution["allow_infinite_run"] = True
    if execution_payload.get("manual_stop_is_dry_run_success"):
        execution["manual_stop_is_dry_run_success"] = True
    return execution


def profile_state_mapping(state_payload: object) -> dict[str, object]:
    if not isinstance(state_payload, dict):
        raise ValueError("state must be an object")
    name = _coerce_string(state_payload.get("name"), "state.name")
    return {
        "name": name,
        "required_anchors": anchors_to_yaml(state_payload.get("required_anchors", [])),
        "optional_anchors": anchors_to_yaml(state_payload.get("optional_anchors", [])),
        "forbidden_anchors": anchors_to_yaml(state_payload.get("forbidden_anchors", [])),
        "actions": actions_to_yaml(state_payload.get("actions", [])),
        "on_success": state_payload.get("on_success"),
        "on_failure": state_payload.get("on_failure", "graceful_termination"),
        "terminal": bool(state_payload.get("terminal", False)),
        "result": state_payload.get("result"),
    }


def state_mapping_to_yaml(state_mapping: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for anchor_key in ("required_anchors", "optional_anchors", "forbidden_anchors"):
        anchors = state_mapping[anchor_key]
        if anchors:
            payload[anchor_key] = anchors
    actions = state_mapping["actions"]
    if actions:
        payload["actions"] = actions
    if state_mapping["on_success"]:
        payload["on_success"] = str(state_mapping["on_success"])
    if state_mapping["on_failure"] and state_mapping["on_failure"] != "graceful_termination":
        payload["on_failure"] = str(state_mapping["on_failure"])
    if state_mapping["terminal"]:
        payload["terminal"] = True
    if state_mapping["result"]:
        payload["result"] = str(state_mapping["result"])
    return payload


def profile_regions_mapping(regions_payload: object) -> dict[str, object]:
    if not isinstance(regions_payload, list):
        raise ValueError("regions must be a list")
    regions: dict[str, object] = {}
    for item in regions_payload:
        if not isinstance(item, dict):
            raise ValueError("region must be an object")
        name = _coerce_string(item.get("name"), "region.name")
        regions[name] = {
            "x": _coerce_int(item.get("x"), f"region '{name}'.x"),
            "y": _coerce_int(item.get("y"), f"region '{name}'.y"),
            "width": _coerce_int(item.get("width"), f"region '{name}'.width"),
            "height": _coerce_int(item.get("height"), f"region '{name}'.height"),
        }
    return regions


def profile_interruptions_mapping(interruptions_payload: object) -> list[dict[str, object]]:
    if not isinstance(interruptions_payload, list):
        raise ValueError("interruptions must be a list")
    interruptions: list[dict[str, object]] = []
    for item in interruptions_payload:
        if not isinstance(item, dict):
            raise ValueError("interruption must be an object")
        interruption = {
            "name": _coerce_string(item.get("name"), "interruption.name"),
            "required_anchors": anchors_to_yaml(item.get("required_anchors", [])),
            "recovery_actions": actions_to_yaml(item.get("recovery_actions", [])),
        }
        max_retries = item.get("max_retries")
        if max_retries is not None:
            interruption["max_retries"] = _coerce_int(
                max_retries,
                f"interruption '{interruption['name']}'.max_retries",
            )
        interruptions.append(
            {key: value for key, value in interruption.items() if value not in ([], None)}
        )
    return interruptions


def serialize_profile_pack_payload(profile_pack_payload: object) -> dict[str, object] | None:
    if profile_pack_payload is None:
        return None
    if not isinstance(profile_pack_payload, dict):
        raise ValueError("profile_pack must be an object")
    compatibility = profile_pack_payload.get("compatibility")
    if not isinstance(compatibility, dict):
        raise ValueError("profile_pack.compatibility must be an object")
    known_limitations = profile_pack_payload.get("known_limitations")
    if not isinstance(known_limitations, list):
        raise ValueError("profile_pack.known_limitations must be a list")
    return {
        "game": _coerce_string(profile_pack_payload.get("game"), "profile_pack.game"),
        "game_mode": _coerce_string(
            profile_pack_payload.get("game_mode"),
            "profile_pack.game_mode",
        ),
        "detection_strategy": _coerce_string(
            profile_pack_payload.get("detection_strategy"),
            "profile_pack.detection_strategy",
        ),
        "known_limitations": [str(item) for item in known_limitations],
        "compatibility": {str(key): value for key, value in compatibility.items()},
    }


def anchors_to_yaml(anchors_payload: object) -> list[dict[str, object]]:
    if not isinstance(anchors_payload, list):
        raise ValueError("anchors must be a list")
    anchors: list[dict[str, object]] = []
    for item in anchors_payload:
        if not isinstance(item, dict):
            raise ValueError("anchor must be an object")
        anchor = {
            "name": _coerce_string(item.get("name"), "anchor.name"),
            "type": _coerce_string(item.get("type"), "anchor.type"),
        }
        if item.get("asset"):
            anchor["asset"] = str(item["asset"])
        if item.get("text"):
            anchor["text"] = str(item["text"])
        anchors.append(anchor)
    return anchors


def actions_to_yaml(actions_payload: object) -> list[dict[str, object]]:
    if not isinstance(actions_payload, list):
        raise ValueError("actions must be a list")
    actions: list[dict[str, object]] = []
    for item in actions_payload:
        if not isinstance(item, dict):
            raise ValueError("action must be an object")
        action_type = _coerce_string(item.get("type"), "action.type")
        data = item.get("data", {})
        if not isinstance(data, dict):
            raise ValueError(f"action '{action_type}' data must be an object")
        action = {"type": action_type}
        action.update(data)
        actions.append(action)
    return actions


def _coerce_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _coerce_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value
