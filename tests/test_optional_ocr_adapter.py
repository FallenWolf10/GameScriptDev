from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import Screenshot
from game_script_dev.adapters.pillow_vision import PillowVisionAdapter
from game_script_dev.schema import Anchor


class FakeOCRAdapter:
    def __init__(self, text: str) -> None:
        self.text = text

    def contains_text(self, text: str, screenshot: Screenshot) -> bool:
        return text.lower() in self.text.lower()


class OptionalOCRAdapterTests(unittest.TestCase):
    def test_text_anchor_uses_injected_ocr_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            screenshot_path = Path(temp_dir) / "screen.png"
            Image.new("RGB", (10, 10), "white").save(screenshot_path)

            adapter = PillowVisionAdapter(
                profile_dir=Path(temp_dir),
                logger=logging.getLogger("tests.ocr"),
                ocr_adapter=FakeOCRAdapter("All Tasks Completed"),
            )

            self.assertTrue(
                adapter.anchor_present(
                    Anchor(
                        name="completion",
                        type="text",
                        text="tasks completed",
                    ),
                    Screenshot(source="screen", path=screenshot_path),
                )
            )

    def test_text_anchor_fails_closed_without_ocr_adapter(self) -> None:
        adapter = PillowVisionAdapter(
            profile_dir=Path("."),
            logger=logging.getLogger("tests.ocr"),
        )

        self.assertFalse(
            adapter.anchor_present(
                Anchor(name="completion", type="text", text="Done"),
                Screenshot(source="dry"),
            )
        )


if __name__ == "__main__":
    unittest.main()
