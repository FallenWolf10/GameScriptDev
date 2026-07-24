from __future__ import annotations

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode


class StructuredFlowMutationError(ValueError):
    """Raised when a structured State mutation cannot be applied safely."""


def mutate_flow_source(source: str, mutation: dict[str, object]) -> str:
    operation = _required_text(mutation, "operation")
    if operation != "update_state":
        raise StructuredFlowMutationError(f"unknown Flow operation: {operation}")

    state_name = _required_text(mutation, "state")
    terminal = mutation.get("terminal")
    make_initial = mutation.get("make_initial", False)
    if not isinstance(terminal, bool):
        raise StructuredFlowMutationError("terminal must be a boolean")
    if not isinstance(make_initial, bool):
        raise StructuredFlowMutationError("make_initial must be a boolean")

    root = _compose_mapping(source)
    states = _mapping_value(root, "states")
    if not isinstance(states, MappingNode):
        raise StructuredFlowMutationError("states must be a mapping")
    state_node = _mapping_value(states, state_name)
    if not isinstance(state_node, MappingNode):
        raise StructuredFlowMutationError(f"unknown State: {state_name}")

    state_names = {
        key.value
        for key, value in states.value
        if isinstance(key, ScalarNode) and isinstance(value, MappingNode)
    }
    on_success = _optional_target(mutation.get("on_success"), "on_success")
    on_failure = _optional_target(mutation.get("on_failure"), "on_failure")
    result = _optional_text(mutation.get("result"), "result")
    for field_name, target in (
        ("on_success", on_success),
        ("on_failure", on_failure),
    ):
        if target is not None and target != "graceful_termination":
            if target not in state_names:
                raise StructuredFlowMutationError(
                    f"{field_name} references unknown State: {target}"
                )

    if make_initial:
        source = _set_mapping_scalar(source, root, "initial_state", state_name)
        root, state_node = _locate_state(source, state_name)

    if terminal:
        source = _set_mapping_scalar(source, state_node, "terminal", True)
        root, state_node = _locate_state(source, state_name)
        source = _set_mapping_scalar(
            source,
            state_node,
            "result",
            result or "success",
        )
        root, state_node = _locate_state(source, state_name)
        source = _set_mapping_scalar(source, state_node, "on_success", None)
        root, state_node = _locate_state(source, state_name)
        return _set_mapping_scalar(source, state_node, "on_failure", None)

    source = _set_mapping_scalar(source, state_node, "on_success", on_success)
    root, state_node = _locate_state(source, state_name)
    source = _set_mapping_scalar(source, state_node, "on_failure", on_failure)
    root, state_node = _locate_state(source, state_name)
    source = _set_mapping_scalar(source, state_node, "terminal", None)
    root, state_node = _locate_state(source, state_name)
    return _set_mapping_scalar(source, state_node, "result", None)


def deterministic_flow_layout(document: dict[str, object]) -> dict[str, dict[str, int]]:
    raw_states = document.get("states")
    if not isinstance(raw_states, dict):
        return {}
    state_names = [str(name) for name in raw_states]
    if not state_names:
        return {}

    initial = str(document.get("initial_state", ""))
    ordered_roots = [initial] if initial in raw_states else []
    ordered_roots.extend(sorted(name for name in state_names if name != initial))
    levels: dict[str, int] = {}
    pending: list[tuple[str, int]] = [(ordered_roots[0], 0)]
    while pending:
        state_name, level = pending.pop(0)
        if state_name in levels:
            continue
        levels[state_name] = level
        state_value = raw_states.get(state_name)
        if not isinstance(state_value, dict):
            continue
        for field in ("on_success", "on_failure"):
            target = state_value.get(field)
            if isinstance(target, str) and target in raw_states and target not in levels:
                pending.append((target, level + 1))

    max_level = max(levels.values(), default=-1)
    for state_name in ordered_roots:
        if state_name not in levels:
            max_level += 1
            levels[state_name] = max_level

    grouped: dict[int, list[str]] = {}
    for state_name, level in levels.items():
        grouped.setdefault(level, []).append(state_name)
    positions: dict[str, dict[str, int]] = {}
    for level in sorted(grouped):
        names = grouped[level]
        if level != 0:
            names.sort()
        for row, state_name in enumerate(names):
            positions[state_name] = {
                "x": 48 + level * 250,
                "y": 48 + row * 132,
            }
    return positions


def _locate_state(source: str, state_name: str) -> tuple[MappingNode, MappingNode]:
    root = _compose_mapping(source)
    states = _mapping_value(root, "states")
    if not isinstance(states, MappingNode):
        raise StructuredFlowMutationError("states must be a mapping")
    state_node = _mapping_value(states, state_name)
    if not isinstance(state_node, MappingNode):
        raise StructuredFlowMutationError(f"unknown State: {state_name}")
    return root, state_node


def _compose_mapping(source: str) -> MappingNode:
    try:
        root = yaml.compose(source)
    except yaml.YAMLError as error:
        raise StructuredFlowMutationError(
            "The YAML Draft must be parseable before structured editing."
        ) from error
    if not isinstance(root, MappingNode):
        raise StructuredFlowMutationError("profile root must be a mapping")
    return root


def _mapping_value(node: MappingNode, key: str) -> Node | None:
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return value_node
    return None


def _mapping_pair(
    node: MappingNode,
    key: str,
) -> tuple[ScalarNode, Node] | None:
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode) and key_node.value == key:
            return key_node, value_node
    return None


def _set_mapping_scalar(
    source: str,
    node: MappingNode,
    key: str,
    value: object | None,
) -> str:
    pair = _mapping_pair(node, key)
    if pair is not None:
        key_node, value_node = pair
        if value is None:
            start = _line_start(source, key_node.start_mark.line)
            end = _line_start(source, value_node.end_mark.line + 1)
            return source[:start] + source[end:]
        if not isinstance(value_node, ScalarNode):
            raise StructuredFlowMutationError(
                f"Field '{key}' requires raw YAML editing"
            )
        rendered = _dump_scalar(value)
        return (
            source[: value_node.start_mark.index]
            + rendered
            + source[value_node.end_mark.index :]
        )
    if value is None:
        return source

    insertion = _line_start(source, node.end_mark.line)
    indent = node.start_mark.column
    addition = f"{' ' * indent}{key}: {_dump_scalar(value)}\n"
    return source[:insertion] + addition + source[insertion:]


def _line_start(source: str, line_number: int) -> int:
    if line_number <= 0:
        return 0
    offset = 0
    for _ in range(line_number):
        newline = source.find("\n", offset)
        if newline < 0:
            return len(source)
        offset = newline + 1
    return offset


def _dump_scalar(value: object) -> str:
    rendered = yaml.safe_dump(
        value,
        default_flow_style=True,
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    return rendered.removesuffix("\n...")


def _required_text(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StructuredFlowMutationError(f"{key} is required")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise StructuredFlowMutationError(f"{field_name} must be text")
    return value.strip() or None


def _optional_target(value: object, field_name: str) -> str | None:
    target = _optional_text(value, field_name)
    if target is not None and len(target) > 128:
        raise StructuredFlowMutationError(
            f"{field_name} must not exceed 128 characters"
        )
    return target
