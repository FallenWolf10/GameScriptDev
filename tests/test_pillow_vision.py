from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.pillow_vision import find_template_center


class PillowVisionTests(unittest.TestCase):
    def test_finds_template_center(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            screenshot_path = root / "screen.png"
            template_path = root / "template.png"

            screenshot = Image.new("RGB", (40, 30), "black")
            template = Image.new("RGB", (6, 4), "red")
            screenshot.paste(template, (10, 8))

            screenshot.save(screenshot_path)
            template.save(template_path)

            self.assertEqual(
                find_template_center(screenshot_path, template_path),
                (13, 10),
            )

    def test_returns_none_when_template_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            screenshot_path = root / "screen.png"
            template_path = root / "template.png"

            Image.new("RGB", (40, 30), "black").save(screenshot_path)
            Image.new("RGB", (6, 4), "red").save(template_path)

            self.assertIsNone(find_template_center(screenshot_path, template_path))


if __name__ == "__main__":
    unittest.main()
