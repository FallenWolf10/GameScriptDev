from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.adapters.live import LiveAdaptersUnavailable, LiveScreenAdapter
from game_script_dev.schema import Profile, Resolution, Target


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

    def test_capture_uses_client_bbox_when_available(self) -> None:
        captured_bboxes: list[tuple[int, int, int, int]] = []

        def fake_grabber(bbox: tuple[int, int, int, int]) -> Image.Image:
            captured_bboxes.append(bbox)
            return Image.new("RGB", (20, 10), "blue")

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LiveScreenAdapter(Path(temp_dir), grabber=fake_grabber)

            adapter.capture(
                TargetWindow(
                    title="Demo",
                    process_name="demo.exe",
                    left=100,
                    top=200,
                    width=36,
                    height=49,
                    handle=123,
                    client_left=108,
                    client_top=231,
                    client_width=20,
                    client_height=10,
                )
            )

            self.assertEqual(captured_bboxes, [(108, 231, 128, 241)])

    def test_repeated_context_captures_include_sequence_numbers(self) -> None:
        def fake_grabber(bbox: tuple[int, int, int, int]) -> Image.Image:
            return Image.new("RGB", (20, 10), "blue")

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LiveScreenAdapter(Path(temp_dir), grabber=fake_grabber)
            window = TargetWindow(
                title="Demo",
                process_name="demo.exe",
                left=100,
                top=200,
                width=20,
                height=10,
                handle=123,
            )

            first = adapter.capture(window, context="wait-for-done")
            second = adapter.capture(window, context="wait-for-done")

            assert first.path is not None
            assert second.path is not None
            self.assertTrue(first.path.name.endswith("_wait-for-done_01.png"))
            self.assertTrue(second.path.name.endswith("_wait-for-done_02.png"))

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

    def test_background_input_mode_uses_window_handle_capture(self) -> None:
        class FakeWindowCapture:
            def __init__(self) -> None:
                self.windows: list[TargetWindow] = []

            def capture_client(self, window: TargetWindow) -> Image.Image:
                self.windows.append(window)
                return Image.new("RGB", (12, 8), "red")

        fake_capture = FakeWindowCapture()
        profile = Profile(
            version=1,
            name="Demo",
            target=Target(window_title_contains="Demo", input_mode="background_window_messages"),
            resolution=Resolution(width=1280, height=720, policy="ignore"),
            initial_state="done",
            states={},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LiveScreenAdapter(
                Path(temp_dir),
                profile=profile,
                window_capture=fake_capture,
            )
            window = TargetWindow(
                title="Demo",
                process_name="demo.exe",
                left=100,
                top=200,
                width=20,
                height=10,
                handle=123,
            )

            screenshot = adapter.capture(window)

            self.assertEqual(fake_capture.windows, [window])
            assert screenshot.path is not None
            self.assertTrue(screenshot.path.exists())

    def test_background_capture_failure_falls_back_to_window_bounds(self) -> None:
        class FailingWindowCapture:
            def capture_client(self, window: TargetWindow) -> Image.Image:
                raise LiveAdaptersUnavailable("Win32 PrintWindow failed")

        captured_bboxes: list[tuple[int, int, int, int]] = []

        def fake_grabber(bbox: tuple[int, int, int, int]) -> Image.Image:
            captured_bboxes.append(bbox)
            return Image.new("RGB", (20, 10), "green")

        profile = Profile(
            version=1,
            name="Demo",
            target=Target(
                window_title_contains="Demo",
                input_mode="background_window_messages",
            ),
            resolution=Resolution(width=1280, height=720, policy="ignore"),
            initial_state="done",
            states={},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = LiveScreenAdapter(
                Path(temp_dir),
                grabber=fake_grabber,
                profile=profile,
                window_capture=FailingWindowCapture(),
            )

            screenshot = adapter.capture(
                TargetWindow(
                    title="Demo",
                    process_name="demo.exe",
                    left=100,
                    top=200,
                    width=20,
                    height=10,
                    handle=123,
                    client_left=108,
                    client_top=231,
                    client_width=20,
                    client_height=10,
                )
            )

            self.assertEqual(captured_bboxes, [(108, 231, 128, 241)])
            assert screenshot.path is not None
            self.assertTrue(screenshot.path.exists())


if __name__ == "__main__":
    unittest.main()
