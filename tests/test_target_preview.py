from __future__ import annotations

import io
import logging
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.dashboard.target_preview import TargetPreviewService


PROFILE_YAML = """
version: 1
name: Preview Demo
target:
  window_title_contains: Preview Window
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: done
states:
  done:
    required_anchors:
      - name: done_title
        type: text
        text: Done
    terminal: true
    result: success
"""


class TargetPreviewTests(unittest.TestCase):
    def test_capture_returns_data_url_and_target_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(PROFILE_YAML, encoding="utf-8")
            adapter = FakeWindowAdapter()
            capture = FakeWindowCapture()
            service = TargetPreviewService(
                logging.getLogger("tests.preview"),
                window_adapter=adapter,  # type: ignore[arg-type]
                window_capture=capture,  # type: ignore[arg-type]
            )

            preview = service.capture(profile_path)

            self.assertEqual(preview.title, "Preview Window")
            self.assertEqual(preview.process_name, "python.exe")
            self.assertEqual(preview.width, 320)
            self.assertEqual(preview.height, 180)
            self.assertTrue(preview.data_url.startswith("data:image/png;base64,"))
            self.assertEqual(capture.windows, [adapter.window])

    def test_capture_reports_client_dimensions_for_decorated_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(PROFILE_YAML, encoding="utf-8")
            adapter = FakeDecoratedWindowAdapter()
            capture = FakeWindowCapture()
            service = TargetPreviewService(
                logging.getLogger("tests.preview"),
                window_adapter=adapter,  # type: ignore[arg-type]
                window_capture=capture,  # type: ignore[arg-type]
            )

            preview = service.capture(profile_path)

            self.assertEqual(preview.width, 1280)
            self.assertEqual(preview.height, 720)
            self.assertEqual(capture.windows, [adapter.window])

    def test_inspect_returns_target_metadata_without_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(PROFILE_YAML, encoding="utf-8")
            adapter = FakeWindowAdapter()
            capture = FakeWindowCapture()
            service = TargetPreviewService(
                logging.getLogger("tests.preview"),
                window_adapter=adapter,  # type: ignore[arg-type]
                window_capture=capture,  # type: ignore[arg-type]
            )

            preview = service.inspect(profile_path)

            self.assertEqual(preview.title, "Preview Window")
            self.assertEqual(preview.process_name, "python.exe")
            self.assertEqual(preview.width, 320)
            self.assertEqual(preview.height, 180)
            self.assertEqual(capture.windows, [])

    def test_capture_jpeg_downscales_preview_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(PROFILE_YAML, encoding="utf-8")
            adapter = FakeWindowAdapter()
            capture = FakeWindowCapture()
            service = TargetPreviewService(
                logging.getLogger("tests.preview"),
                window_adapter=adapter,  # type: ignore[arg-type]
                window_capture=capture,  # type: ignore[arg-type]
            )

            preview, jpeg_bytes = service.capture_jpeg(profile_path, max_width=8)

            self.assertEqual(preview.width, 320)
            self.assertEqual(preview.height, 180)
            self.assertTrue(jpeg_bytes.startswith(b"\xff\xd8"))
            with Image.open(io.BytesIO(jpeg_bytes)) as image:
                self.assertEqual(image.size, (8, 4))
                red, green, blue = image.getpixel((0, 0))
                self.assertLess(red, 40)
                self.assertGreater(green, 100)
                self.assertLess(blue, 40)


class FakeWindowAdapter:
    def __init__(self) -> None:
        self.window = TargetWindow(
            title="Preview Window",
            process_name="python.exe",
            left=10,
            top=20,
            width=320,
            height=180,
            handle=123,
            process_id=456,
        )

    def find_target(self, profile: object) -> TargetWindow:
        return self.window

    def verify_window(self, window: TargetWindow, profile: object) -> TargetWindow:
        return window


class FakeWindowCapture:
    def __init__(self) -> None:
        self.windows: list[TargetWindow] = []

    def capture_client(self, window: TargetWindow) -> Image.Image:
        self.windows.append(window)
        return Image.new("RGB", (16, 9), "green")


class FakeDecoratedWindowAdapter:
    def __init__(self) -> None:
        self.window = TargetWindow(
            title="Preview Window",
            process_name="python.exe",
            left=10,
            top=20,
            width=1296,
            height=759,
            handle=123,
            process_id=456,
            client_left=18,
            client_top=51,
            client_width=1280,
            client_height=720,
        )

    def find_target(self, profile: object) -> TargetWindow:
        return self.window

    def verify_window(self, window: TargetWindow, profile: object) -> TargetWindow:
        return window


if __name__ == "__main__":
    unittest.main()
