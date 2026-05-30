from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import Screenshot
from game_script_dev.adapters.live import LiveVisionAdapter
from game_script_dev.schema import Anchor


class LiveVisionAdapterTests(unittest.TestCase):
    def test_finds_template_anchor_in_captured_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset_dir = root / "assets"
            asset_dir.mkdir()
            screenshot_path = root / "capture.png"
            template_path = asset_dir / "button.png"

            screenshot = Image.new("RGB", (40, 30), "black")
            template = Image.new("RGB", (6, 4), "green")
            screenshot.paste(template, (12, 9))
            screenshot.save(screenshot_path)
            template.save(template_path)

            adapter = LiveVisionAdapter(
                profile_dir=root,
                logger=logging.getLogger("tests.live_vision"),
            )

            self.assertTrue(
                adapter.anchor_present(
                    Anchor(
                        name="button",
                        type="template",
                        asset="assets/button.png",
                    ),
                    Screenshot(source="capture", path=screenshot_path),
                )
            )
            self.assertEqual(
                adapter.find_template_center(
                    "assets/button.png",
                    Screenshot(source="capture", path=screenshot_path),
                ),
                (15, 11),
            )


if __name__ == "__main__":
    unittest.main()
