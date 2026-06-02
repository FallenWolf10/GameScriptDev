from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from PIL import ImageChops
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from game_script_dev.adapters.live import (  # noqa: E402
    LiveAdaptersUnavailable,
    LiveInputAdapter,
    Win32WindowCapture,
    WindowsWindowAdapter,
)
from game_script_dev.profile_loader import load_profile  # noqa: E402


METHODS = [
    "sendinput_vk",
    "sendinput_scancode",
    "sendinput_vk_scancode",
    "sendinput_unicode",
    "keybd_event_vk",
    "keybd_event_scancode",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Try multiple foreground keyboard delivery methods against NTE's L hotkey."
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "profiles" / "neverness_the_everness" / "team_screen_l" / "profile.yaml",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ROOT / "logs" / "diagnostics" / "foreground_l_sweep",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.2,
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=0.0,
        help="Hold the key for this many seconds instead of tapping it.",
    )
    return parser.parse_args()


def _count_changed_pixels(diff_image) -> int:
    mask = diff_image.convert("L").point(lambda value: 255 if value else 0)
    return int(mask.histogram()[255])


def _capture_window(capture: Win32WindowCapture, window):
    try:
        return capture.capture_client(window)
    except LiveAdaptersUnavailable:
        bbox = (
            int(window.left),
            int(window.top),
            int(window.left + window.width),
            int(window.top + window.height),
        )
        return ImageGrab.grab(bbox)


def main() -> int:
    args = parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("foreground-l-sweep")

    profile = load_profile(args.profile)
    window_adapter = WindowsWindowAdapter(logger, require_foreground=False)
    capture = Win32WindowCapture.create()
    results: list[dict[str, object]] = []

    for method in METHODS:
        window = window_adapter.find_target(profile)
        if window is None:
            raise RuntimeError("target application is not running")
        window_adapter.prepare_window(window, profile.resolution)

        before = _capture_window(capture, window)
        before_path = args.artifact_dir / f"{method}_before.png"
        before.save(before_path)

        adapter = LiveInputAdapter(
            target_window=window,
            profile=profile,
            window_adapter=window_adapter,
            input_mode="foreground",
            foreground_key_method=method,
        )
        if args.hold_seconds > 0:
            adapter.hold_key("l", args.hold_seconds)
        else:
            adapter.press_key("l")
        time.sleep(args.sleep_seconds)

        refreshed = window_adapter.verify_window(window, profile)
        after = _capture_window(capture, refreshed)
        after_path = args.artifact_dir / f"{method}_after.png"
        after.save(after_path)

        diff = ImageChops.difference(before, after)
        diff_bbox = diff.getbbox()
        changed_pixels = _count_changed_pixels(diff)
        result = {
            "method": method,
            "before": str(before_path),
            "after": str(after_path),
            "bbox": list(diff_bbox) if diff_bbox else None,
            "changed_pixels": changed_pixels,
        }
        results.append(result)
        logger.info(
            "%s hold=%ss -> changed_pixels=%s bbox=%s",
            method,
            args.hold_seconds,
            changed_pixels,
            diff_bbox,
        )

    summary_path = args.artifact_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("Wrote %s", summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
