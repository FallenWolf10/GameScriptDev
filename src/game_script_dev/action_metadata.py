from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionFieldDefinition:
    name: str
    kind: str
    required: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    label: str
    fields: tuple[ActionFieldDefinition, ...] = field(default_factory=tuple)


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
