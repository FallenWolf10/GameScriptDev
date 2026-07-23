from __future__ import annotations

import unittest

from game_script_dev.action_metadata import (
    CONTINUOUS_INPUT_ACTION_DEFINITIONS,
    SCROLL_MOUSE_CONTINUOUS_FIELDS,
    SUPPORTED_CONTINUOUS_INPUT_ACTION_TYPES,
    get_continuous_input_action_definition,
)


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


if __name__ == "__main__":
    unittest.main()
