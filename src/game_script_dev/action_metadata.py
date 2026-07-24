from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionFieldDefinition:
    name: str
    kind: str
    required: bool = False
    choices: tuple[str, ...] = ()
    default: object | None = None
    hint: str = ""

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
        }
        if self.choices:
            payload["choices"] = list(self.choices)
        if self.default is not None:
            payload["default"] = self.default
        if self.hint:
            payload["hint"] = self.hint
        return payload


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    label: str
    category: str = "advanced"
    keywords: tuple[str, ...] = ()
    fields: tuple[ActionFieldDefinition, ...] = field(default_factory=tuple)
    summary_fields: tuple[str, ...] = ()
    structured: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.action_type,
            "label": self.label,
            "category": self.category,
            "keywords": list(self.keywords),
            "fields": [definition.to_dict() for definition in self.fields],
            "summary_fields": list(self.summary_fields),
            "structured": self.structured,
        }


def _field(
    name: str,
    kind: str,
    *,
    required: bool = False,
    choices: tuple[str, ...] = (),
    default: object | None = None,
    hint: str = "",
) -> ActionFieldDefinition:
    return ActionFieldDefinition(
        name=name,
        kind=kind,
        required=required,
        choices=choices,
        default=default,
        hint=hint,
    )


ACTION_DEFINITIONS: dict[str, ActionDefinition] = {
    "wait_for_state": ActionDefinition(
        "wait_for_state",
        "Wait for State",
        "flow_timing",
        ("screen", "detect", "poll", "transition"),
        (
            _field("state", "state", required=True),
            _field("timeout_seconds", "positive_duration"),
            _field("poll_interval_seconds", "positive_duration"),
        ),
        ("state", "timeout_seconds"),
    ),
    "click_template": ActionDefinition(
        "click_template",
        "Click Template",
        "pointer",
        ("image", "asset", "button"),
        (_field("target", "asset", required=True),),
        ("target",),
    ),
    "click_point": ActionDefinition(
        "click_point",
        "Click Point",
        "pointer",
        ("region", "mouse", "button"),
        (
            _field("region", "region", required=True),
            _field(
                "input_mode",
                "input_mode",
                choices=("background_window_messages", "foreground"),
            ),
        ),
        ("region",),
    ),
    "hold_click": ActionDefinition(
        "hold_click",
        "Hold Click",
        "pointer",
        ("region", "mouse", "drag"),
        (
            _field("region", "region", required=True),
            _field("seconds", "duration", required=True),
            _field(
                "input_mode",
                "input_mode",
                choices=("background_window_messages", "foreground"),
            ),
        ),
        ("region", "seconds"),
    ),
    "press_key": ActionDefinition(
        "press_key",
        "Press Key",
        "keyboard",
        ("tap", "type", "button"),
        (
            _field("key", "key", required=True),
            _field("seconds", "duration"),
        ),
        ("key", "seconds"),
    ),
    "press_keys": ActionDefinition(
        "press_keys",
        "Press Keys",
        "keyboard",
        ("shortcut", "combo", "tap"),
        (
            _field("keys", "keys", required=True),
            _field("seconds", "duration"),
        ),
        ("keys", "seconds"),
    ),
    "hold_key": ActionDefinition(
        "hold_key",
        "Hold Key",
        "keyboard",
        ("down", "duration", "movement"),
        (
            _field("key", "key", required=True),
            _field("seconds", "duration", default=1),
        ),
        ("key", "seconds"),
    ),
    "hold_keys": ActionDefinition(
        "hold_keys",
        "Hold Keys",
        "keyboard",
        ("shortcut", "combo", "duration"),
        (
            _field("keys", "keys", required=True),
            _field("seconds", "duration", default=1),
        ),
        ("keys", "seconds"),
    ),
    "repeat_key": ActionDefinition(
        "repeat_key",
        "Repeat Key",
        "keyboard",
        ("tap", "loop", "interval"),
        (
            _field("key", "key", required=True),
            _field("repeat_for_seconds", "duration", required=True),
            _field("repeat_every_seconds", "positive_duration", required=True),
            _field("tap_duration_seconds", "duration"),
        ),
        ("key", "repeat_for_seconds", "repeat_every_seconds"),
    ),
    "hold_key_while_repeating_key": ActionDefinition(
        "hold_key_while_repeating_key",
        "Hold Key While Repeating Key",
        "keyboard",
        ("overlap", "tap", "movement", "loop"),
        (
            _field("hold_key", "key", required=True),
            _field("hold_seconds", "duration", required=True),
            _field("tap_key", "key", required=True),
            _field("tap_every_seconds", "positive_duration", required=True),
            _field("tap_duration_seconds", "duration"),
        ),
        ("hold_key", "tap_key", "hold_seconds"),
    ),
    "move_mouse": ActionDefinition(
        "move_mouse",
        "Move Mouse",
        "pointer",
        ("relative", "camera", "look"),
        (
            _field("dx", "number", required=True),
            _field("dy", "number", required=True),
            _field("seconds", "duration"),
            _field("input_mode", "input_mode", choices=("foreground",)),
        ),
        ("dx", "dy", "seconds"),
    ),
    "hold_mouse_button_and_move": ActionDefinition(
        "hold_mouse_button_and_move",
        "Hold Mouse Button and Move",
        "pointer",
        ("drag", "camera", "look"),
        (
            _field("button", "mouse_button", required=True, choices=("left", "right")),
            _field("dx", "number", required=True),
            _field("dy", "number", required=True),
            _field("seconds", "duration"),
            _field("input_mode", "input_mode", choices=("foreground",)),
        ),
        ("button", "dx", "dy", "seconds"),
    ),
    "scroll_mouse": ActionDefinition(
        "scroll_mouse",
        "Scroll Mouse",
        "pointer",
        ("wheel", "up", "down"),
        (
            _field("direction", "scroll_direction", required=True, choices=("up", "down")),
            _field("steps", "positive_integer", default=1),
            _field("input_mode", "input_mode", choices=("foreground",)),
        ),
        ("direction", "steps"),
    ),
    "start_continuous_input": ActionDefinition(
        "start_continuous_input",
        "Start Continuous Input",
        "continuous_input",
        ("background", "repeat", "sequence", "parallel"),
        (
            _field("name", "text", required=True),
            _field(
                "action",
                "continuous_action",
                required=True,
                choices=(
                    "click_point",
                    "hold_click",
                    "scroll_mouse",
                    "press_key",
                    "press_keys",
                    "hold_key",
                    "hold_keys",
                    "repeat_key",
                    "hold_key_while_repeating_key",
                    "sequence",
                ),
            ),
            _field("stop_after_seconds", "positive_duration"),
        ),
        ("name", "action", "stop_after_seconds"),
    ),
    "stop_continuous_input": ActionDefinition(
        "stop_continuous_input",
        "Stop Continuous Input",
        "continuous_input",
        ("end", "cancel", "background"),
        (_field("name", "text", required=True),),
        ("name",),
    ),
    "wait": ActionDefinition(
        "wait",
        "Wait",
        "flow_timing",
        ("pause", "delay", "sleep", "timing"),
        (
            _field(
                "seconds",
                "duration",
                required=True,
                default=1,
                hint="A finite non-negative number of seconds.",
            ),
        ),
        ("seconds",),
        True,
    ),
    "log": ActionDefinition(
        "log",
        "Log Message",
        "flow_timing",
        ("message", "checkpoint", "note"),
        (_field("message", "text", required=True),),
        ("message",),
    ),
    "stop": ActionDefinition(
        "stop",
        "Stop Run",
        "flow_timing",
        ("finish", "result", "terminate"),
        (_field("result", "text"),),
        ("result",),
    ),
}


def get_action_definition(action_type: str) -> ActionDefinition:
    return ACTION_DEFINITIONS[action_type]


def action_schema_payload() -> dict[str, object]:
    return {
        "version": 1,
        "actions": [
            ACTION_DEFINITIONS[action_type].to_dict()
            for action_type in sorted(ACTION_DEFINITIONS)
        ],
    }


SCROLL_MOUSE_CONTINUOUS_FIELDS: tuple[ActionFieldDefinition, ...] = (
    ActionFieldDefinition(
        name="direction",
        kind="scroll_direction",
        required=True,
        choices=("down", "up"),
    ),
    ActionFieldDefinition(
        name="steps",
        kind="positive_integer",
        required=False,
    ),
    ActionFieldDefinition(
        name="repeat_every_seconds",
        kind="positive_duration",
        required=True,
    ),
    ActionFieldDefinition(
        name="input_mode",
        kind="input_mode",
        required=False,
        choices=("background_window_messages", "foreground"),
    ),
    ActionFieldDefinition(
        name="stop_after_seconds",
        kind="positive_duration",
        required=False,
    ),
)


CONTINUOUS_INPUT_ACTION_DEFINITIONS: dict[str, ActionDefinition] = {
    "click_point": ActionDefinition(
        action_type="click_point",
        label="Continuous Click Point",
        fields=(
            ActionFieldDefinition(name="region", kind="region", required=True),
            ActionFieldDefinition(
                name="repeat_every_seconds",
                kind="positive_duration",
                required=True,
            ),
            ActionFieldDefinition(
                name="input_mode",
                kind="input_mode",
                required=False,
                choices=("background_window_messages", "foreground"),
            ),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "hold_click": ActionDefinition(
        action_type="hold_click",
        label="Continuous Hold Click",
        fields=(
            ActionFieldDefinition(name="region", kind="region", required=True),
            ActionFieldDefinition(
                name="input_mode",
                kind="input_mode",
                required=False,
                choices=("background_window_messages", "foreground"),
            ),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "press_key": ActionDefinition(
        action_type="press_key",
        label="Continuous Press Key",
        fields=(
            ActionFieldDefinition(name="key", kind="key", required=True),
            ActionFieldDefinition(
                name="repeat_every_seconds",
                kind="positive_duration",
                required=True,
            ),
            ActionFieldDefinition(name="seconds", kind="duration", required=False),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "press_keys": ActionDefinition(
        action_type="press_keys",
        label="Continuous Press Keys",
        fields=(
            ActionFieldDefinition(name="keys", kind="keys", required=True),
            ActionFieldDefinition(
                name="repeat_every_seconds",
                kind="positive_duration",
                required=True,
            ),
            ActionFieldDefinition(name="seconds", kind="duration", required=False),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "hold_key": ActionDefinition(
        action_type="hold_key",
        label="Continuous Hold Key",
        fields=(
            ActionFieldDefinition(name="key", kind="key", required=True),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "hold_keys": ActionDefinition(
        action_type="hold_keys",
        label="Continuous Hold Keys",
        fields=(
            ActionFieldDefinition(name="keys", kind="keys", required=True),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "repeat_key": ActionDefinition(
        action_type="repeat_key",
        label="Continuous Repeat Key",
        fields=(
            ActionFieldDefinition(name="key", kind="key", required=True),
            ActionFieldDefinition(
                name="repeat_every_seconds",
                kind="positive_duration",
                required=True,
            ),
            ActionFieldDefinition(
                name="tap_duration_seconds",
                kind="duration",
                required=False,
            ),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "hold_key_while_repeating_key": ActionDefinition(
        action_type="hold_key_while_repeating_key",
        label="Continuous Hold Key While Repeating Key",
        fields=(
            ActionFieldDefinition(name="hold_key", kind="key", required=True),
            ActionFieldDefinition(name="tap_key", kind="key", required=True),
            ActionFieldDefinition(
                name="tap_every_seconds",
                kind="positive_duration",
                required=True,
            ),
            ActionFieldDefinition(
                name="tap_duration_seconds",
                kind="duration",
                required=False,
            ),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
    "scroll_mouse": ActionDefinition(
        action_type="scroll_mouse",
        label="Continuous Scroll Mouse",
        fields=SCROLL_MOUSE_CONTINUOUS_FIELDS,
    ),
    "sequence": ActionDefinition(
        action_type="sequence",
        label="Continuous Sequence",
        fields=(
            ActionFieldDefinition(name="sequence", kind="sequence", required=True),
            ActionFieldDefinition(
                name="stop_after_seconds",
                kind="positive_duration",
                required=False,
            ),
        ),
    ),
}


SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES: tuple[str, ...] = tuple(
    CONTINUOUS_INPUT_ACTION_DEFINITIONS.keys()
)


def get_continuous_input_action_definition(action_type: str) -> ActionDefinition:
    return CONTINUOUS_INPUT_ACTION_DEFINITIONS[action_type]
