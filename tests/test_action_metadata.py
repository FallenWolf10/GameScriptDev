from __future__ import annotations

import unittest

from game_script_dev.action_metadata import (
    ACTION_DEFINITIONS,
    CONTINUOUS_INPUT_ACTION_DEFINITIONS,
    SCROLL_MOUSE_CONTINUOUS_FIELDS,
    SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES,
    get_continuous_input_action_definition,
)
from game_script_dev.schema import SUPPORTED_ACTION_TYPES


class ActionMetadataTests(unittest.TestCase):
    def test_continuous_input_registry_includes_scroll_mouse(self) -> None:
        self.assertIn("scroll_mouse", SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES)

        definition = get_continuous_input_action_definition("scroll_mouse")

        self.assertEqual(definition.action_type, "scroll_mouse")
        self.assertEqual(definition.label, "Continuous Scroll Mouse")

    def test_continuous_scroll_mouse_fields_match_expected_shape(self) -> None:
        field_names = [field.name for field in SCROLL_MOUSE_CONTINUOUS_FIELDS]
        required_fields = [field.name for field in SCROLL_MOUSE_CONTINUOUS_FIELDS if field.required]
        input_mode_field = next(
            field for field in SCROLL_MOUSE_CONTINUOUS_FIELDS if field.name == "input_mode"
        )

        self.assertEqual(
            field_names,
            [
                "direction",
                "steps",
                "repeat_every_seconds",
                "input_mode",
                "stop_after_seconds",
            ],
        )
        self.assertEqual(required_fields, ["direction", "repeat_every_seconds"])
        self.assertEqual(
            input_mode_field.choices,
            ("background_window_messages", "foreground"),
        )

    def test_registry_keys_match_definition_action_types(self) -> None:
        self.assertEqual(
            set(CONTINUOUS_INPUT_ACTION_DEFINITIONS),
            {
                definition.action_type
                for definition in CONTINUOUS_INPUT_ACTION_DEFINITIONS.values()
            },
        )

    def test_builder_registry_covers_every_schema_action(self) -> None:
        self.assertEqual(set(ACTION_DEFINITIONS), SUPPORTED_ACTION_TYPES)
        self.assertEqual(
            set(ACTION_DEFINITIONS),
            {definition.action_type for definition in ACTION_DEFINITIONS.values()},
        )

    def test_every_builder_definition_exposes_complete_editor_metadata(self) -> None:
        for action_type, definition in ACTION_DEFINITIONS.items():
            with self.subTest(action_type=action_type):
                self.assertTrue(definition.label)
                self.assertTrue(definition.category)
                self.assertTrue(definition.keywords)
                if definition.fields:
                    self.assertTrue(definition.summary_fields)
                self.assertEqual(
                    len({field.name for field in definition.fields}),
                    len(definition.fields),
                )
                for field in definition.fields:
                    self.assertTrue(field.kind)
                    self.assertTrue(field.hint)

    def test_wait_definition_exposes_structured_editor_contract(self) -> None:
        definition = ACTION_DEFINITIONS["wait"]

        self.assertTrue(definition.structured)
        self.assertEqual(definition.category, "flow_timing")
        self.assertIn("delay", definition.keywords)
        self.assertEqual(definition.summary_fields, ("seconds",))
        self.assertEqual(definition.fields[0].name, "seconds")
        self.assertTrue(definition.fields[0].required)
        self.assertEqual(definition.fields[0].default, 1)

    def test_initial_common_actions_expose_structured_forms(self) -> None:
        expected = {
            "wait",
            "log",
            "press_key",
            "hold_key",
            "click_point",
            "wait_for_state",
            "stop",
        }

        self.assertEqual(
            {
                action_type
                for action_type, definition in ACTION_DEFINITIONS.items()
                if definition.structured
            },
            expected,
        )


if __name__ == "__main__":
    unittest.main()
