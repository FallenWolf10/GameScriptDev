from __future__ import annotations

from dataclasses import dataclass

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from game_script_dev.action_metadata import ACTION_DEFINITIONS


class StructuredActionMutationError(ValueError):
    """Raised when a structured action mutation cannot be applied safely."""


@dataclass(frozen=True)
class ActionLocation:
    state_name: str
    state_node: MappingNode
    actions_key: ScalarNode | None
    actions_node: Node | None


def mutate_action_source(source: str, mutation: dict[str, object]) -> str:
    operation = _required_text(mutation, "operation")
    state_name = _required_text(mutation, "state")
    root = _compose_mapping(source)
    location = _locate_actions(root, state_name)

    if operation == "insert":
        action_type = _required_text(mutation, "action_type")
        if action_type not in ACTION_DEFINITIONS:
            raise StructuredActionMutationError(
                f"unknown Action type: {action_type}"
            )
        fields = mutation.get("fields", {})
        if not isinstance(fields, dict):
            raise StructuredActionMutationError("fields must be an object")
        action = _new_action(action_type, fields)
        index = _optional_index(mutation.get("index"))
        return _insert_action(source, location, action, index)

    index = _required_index(mutation.get("index"))
    actions = _action_nodes(location)
    if index >= len(actions):
        raise StructuredActionMutationError(
            f"Action index {index} is outside State '{state_name}'"
        )

    if operation == "update":
        fields = mutation.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise StructuredActionMutationError("fields must be a non-empty object")
        return _update_action(source, actions[index], fields)
    if operation == "move":
        target_index = _required_index(mutation.get("target_index"))
        if target_index >= len(actions):
            raise StructuredActionMutationError(
                f"target Action index {target_index} is outside State '{state_name}'"
            )
        return _move_action(source, location, index, target_index)
    if operation == "duplicate":
        return _duplicate_action(source, location, index)
    if operation in {"disable", "enable"}:
        return _update_action(
            source,
            actions[index],
            {"disabled": operation == "disable"},
        )
    if operation == "delete":
        return _delete_action(source, location, index)
    raise StructuredActionMutationError(f"unknown Action operation: {operation}")


def _compose_mapping(source: str) -> MappingNode:
    try:
        root = yaml.compose(source)
    except yaml.YAMLError as error:
        raise StructuredActionMutationError(
            "The YAML Draft must be parseable before structured editing."
        ) from error
    if not isinstance(root, MappingNode):
        raise StructuredActionMutationError("profile root must be a mapping")
    return root


def _locate_actions(root: MappingNode, state_name: str) -> ActionLocation:
    states_node = _mapping_value(root, "states")
    if not isinstance(states_node, MappingNode):
        raise StructuredActionMutationError("states must be a mapping")
    state_node = _mapping_value(states_node, state_name)
    if not isinstance(state_node, MappingNode):
        raise StructuredActionMutationError(f"unknown State: {state_name}")
    for key_node, value_node in state_node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == "actions":
            if not isinstance(value_node, (SequenceNode, ScalarNode)):
                raise StructuredActionMutationError(
                    f"State '{state_name}' actions must be a list"
                )
            return ActionLocation(state_name, state_node, key_node, value_node)
    return ActionLocation(state_name, state_node, None, None)


def _mapping_value(node: MappingNode, key: str) -> Node | None:
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return value_node
    return None


def _action_nodes(location: ActionLocation) -> list[MappingNode]:
    if location.actions_node is None:
        return []
    if isinstance(location.actions_node, ScalarNode):
        if location.actions_node.value in {"", "[]"}:
            return []
        raise StructuredActionMutationError(
            f"State '{location.state_name}' actions must be a list"
        )
    if not isinstance(location.actions_node, SequenceNode):
        raise StructuredActionMutationError(
            f"State '{location.state_name}' actions must be a list"
        )
    if not all(isinstance(item, MappingNode) for item in location.actions_node.value):
        raise StructuredActionMutationError("every Action must be a mapping")
    return list(location.actions_node.value)  # type: ignore[return-value]


def _new_action(action_type: str, fields: dict[object, object]) -> dict[str, object]:
    definition = ACTION_DEFINITIONS[action_type]
    allowed = {field.name for field in definition.fields}
    unexpected = sorted(str(key) for key in fields if str(key) not in allowed)
    if unexpected:
        raise StructuredActionMutationError(
            f"unsupported fields for {action_type}: {', '.join(unexpected)}"
        )
    action: dict[str, object] = {"type": action_type}
    for field in definition.fields:
        if field.name in fields:
            action[field.name] = fields[field.name]
        elif field.default is not None:
            action[field.name] = field.default
    return action


def _insert_action(
    source: str,
    location: ActionLocation,
    action: dict[str, object],
    requested_index: int | None,
) -> str:
    action_nodes = _action_nodes(location)
    index = len(action_nodes) if requested_index is None else requested_index
    if index > len(action_nodes):
        raise StructuredActionMutationError(
            f"Action index {index} is outside State '{location.state_name}'"
        )

    if action_nodes:
        indent = _line_indent(source, action_nodes[0].start_mark.line)
        block = _dump_action_block(action, indent)
        insertion = (
            _line_start(source, action_nodes[index].start_mark.line)
            if index < len(action_nodes)
            else _line_start(source, location.actions_node.end_mark.line)
        )
        return source[:insertion] + block + source[insertion:]

    child_indent = location.state_node.start_mark.column
    if location.actions_node is None:
        insertion = _line_start(source, location.state_node.end_mark.line)
        block = (
            " " * child_indent
            + "actions:\n"
            + _dump_action_block(action, child_indent + 2)
        )
        return source[:insertion] + block + source[insertion:]

    replacement = "\n" + _dump_action_block(action, child_indent + 2).rstrip("\n")
    start = location.actions_node.start_mark.index
    end = location.actions_node.end_mark.index
    return source[:start] + replacement + source[end:]


def _update_action(
    source: str,
    action_node: MappingNode,
    fields: dict[object, object],
) -> str:
    action_type_node = _mapping_value(action_node, "type")
    if not isinstance(action_type_node, ScalarNode):
        raise StructuredActionMutationError("Action type must be a scalar")
    definition = ACTION_DEFINITIONS.get(action_type_node.value)
    allowed = (
        {field.name for field in definition.fields} | {"disabled"}
        if definition is not None
        else {"disabled"}
    )
    normalized = {str(key): value for key, value in fields.items()}
    unexpected = sorted(set(normalized) - allowed)
    if unexpected:
        raise StructuredActionMutationError(
            f"unsupported fields for {action_type_node.value}: "
            + ", ".join(unexpected)
        )

    replacements: list[tuple[int, int, str]] = []
    existing: set[str] = set()
    for key_node, value_node in action_node.value:
        if not isinstance(key_node, ScalarNode) or key_node.value not in normalized:
            continue
        if not isinstance(value_node, ScalarNode):
            raise StructuredActionMutationError(
                f"Field '{key_node.value}' requires raw YAML editing"
            )
        existing.add(key_node.value)
        replacements.append(
            (
                value_node.start_mark.index,
                value_node.end_mark.index,
                _dump_scalar(normalized[key_node.value]),
            )
        )

    missing = [key for key in normalized if key not in existing]
    if missing:
        insertion = _line_start(source, action_node.end_mark.line)
        indent = action_node.start_mark.column
        addition = "".join(
            f"{' ' * indent}{key}: {_dump_scalar(normalized[key])}\n"
            for key in missing
        )
        replacements.append((insertion, insertion, addition))

    for start, end, value in sorted(replacements, reverse=True):
        source = source[:start] + value + source[end:]
    return source


def _move_action(
    source: str,
    location: ActionLocation,
    index: int,
    target_index: int,
) -> str:
    if index == target_index:
        return source
    nodes = _action_nodes(location)
    spans = _action_spans(source, location, nodes)
    blocks = [source[start:end] for start, end in spans]
    block = blocks.pop(index)
    blocks.insert(target_index, block)
    return source[: spans[0][0]] + "".join(blocks) + source[spans[-1][1] :]


def _duplicate_action(source: str, location: ActionLocation, index: int) -> str:
    nodes = _action_nodes(location)
    spans = _action_spans(source, location, nodes)
    start, end = spans[index]
    return source[:end] + source[start:end] + source[end:]


def _delete_action(source: str, location: ActionLocation, index: int) -> str:
    nodes = _action_nodes(location)
    spans = _action_spans(source, location, nodes)
    start, end = spans[index]
    if len(nodes) > 1:
        return source[:start] + source[end:]
    indent = _line_indent(source, nodes[0].start_mark.line)
    return source[:start] + " " * indent + "[]\n" + source[end:]


def _action_spans(
    source: str,
    location: ActionLocation,
    nodes: list[MappingNode],
) -> list[tuple[int, int]]:
    starts = [_line_start(source, node.start_mark.line) for node in nodes]
    sequence_end = _line_start(source, location.actions_node.end_mark.line)
    return [
        (start, starts[index + 1] if index + 1 < len(starts) else sequence_end)
        for index, start in enumerate(starts)
    ]


def _dump_action_block(action: dict[str, object], indent: int) -> str:
    dumped = yaml.safe_dump(
        [action],
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip()
    return "\n".join(" " * indent + line for line in dumped.splitlines()) + "\n"


def _dump_scalar(value: object) -> str:
    if isinstance(value, (dict, list)):
        raise StructuredActionMutationError("nested values require raw YAML editing")
    dumped = yaml.safe_dump(
        value,
        default_flow_style=True,
        allow_unicode=True,
    ).strip()
    if dumped.endswith("\n..."):
        dumped = dumped[:-4]
    return dumped


def _line_start(source: str, line: int) -> int:
    if line <= 0:
        return 0
    offset = 0
    for current, text in enumerate(source.splitlines(keepends=True)):
        if current == line:
            return offset
        offset += len(text)
    return len(source)


def _line_indent(source: str, line: int) -> int:
    start = _line_start(source, line)
    end = source.find("\n", start)
    if end < 0:
        end = len(source)
    text = source[start:end]
    return len(text) - len(text.lstrip(" "))


def _required_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StructuredActionMutationError(f"{key} is required")
    return value.strip()


def _required_index(value: object) -> int:
    index = _optional_index(value)
    if index is None:
        raise StructuredActionMutationError("index is required")
    return index


def _optional_index(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StructuredActionMutationError("Action index must be a non-negative integer")
    return value
