from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.adapters.live import LiveAdaptersUnavailable, LiveScreenAdapter


class LiveScreenAdapterTests(unittest.TestCase):
    def test_capture_saves_window_bbox_image(self) -> None:
        captured_bboxes: list[tuple[int, int, int, int]] = []

        def fake_grabber(bbox: tuple[int, int, int, int]) -> Image.Image:
            captured_bboxes.append(bbox)
            return Image.new("RGB", (20, 10), "blue")

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LiveScreenAdapter(Path(temp_dir), grabber=fake_grabber)

            screenshot = adapter.capture(
                TargetWindow(
                    title="Demo",
                    process_name="demo.exe",
                    left=100,
                    top=200,
                    width=20,
                    height=10,
                    handle=123,
                )
            )

            self.assertEqual(captured_bboxes, [(100, 200, 120, 210)])
            self.assertIsNotNone(screenshot.path)
            assert screenshot.path is not None
            self.assertTrue(screenshot.path.exists())

    def test_capture_requires_window_handle(self) -> None:
        adapter = LiveScreenAdapter(Path("unused"))

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.capture(
                TargetWindow(
                    title="Demo",
                    process_name="demo.exe",
                    left=100,
                    top=200,
                    width=20,
                    height=10,
                    handle=None,
                )
            )


if __name__ == "__main__":
    unittest.main()
