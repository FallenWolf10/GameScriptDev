from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from game_script_dev.schema import Anchor, Profile, Resolution


@dataclass(frozen=True)
class TargetWindow:
    title: str
    process_name: str | None
    left: int
    top: int
    width: int
    height: int
    handle: int | None = None
    process_id: int | None = None


@dataclass(frozen=True)
class Screenshot:
    source: str
    path: Path | None = None


class WindowAdapter(Protocol):
    def find_target(self, profile: Profile) -> TargetWindow | None:
        """Return the target window when it is available."""

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        """Focus and verify or resize the target window."""

    def verify_window(self, window: TargetWindow, profile: Profile) -> TargetWindow:
        """Return a refreshed target window after confirming it is still valid."""


class ScreenAdapter(Protocol):
    def capture(
        self,
        window: TargetWindow,
        context: str | None = None,
    ) -> Screenshot:
        """Capture the target window or screen."""


class VisionAdapter(Protocol):
    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        """Return whether the anchor is present in the screenshot."""

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        """Return the center of a matched template."""


class OCRAdapter(Protocol):
    def contains_text(self, text: str, screenshot: Screenshot) -> bool:
        """Return whether the screenshot contains the requested text."""


class InputAdapter(Protocol):
    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        """Click a detected template target."""

    def click_region(self, region_name: str) -> None:
        """Click a named profile region."""

    def click_coordinates(self, x: int, y: int, label: str) -> None:
        """Click a target-window-relative point."""

    def hold_click(self, region_name: str, seconds: float) -> None:
        """Hold the left mouse button on a named profile region."""

    def press_key(self, key: str, seconds: float | None = None) -> None:
        """Press a key, optionally overriding the tap duration."""

    def press_keys(self, keys: list[str], seconds: float | None = None) -> None:
        """Press multiple keys together, optionally overriding the tap duration."""

    def hold_key(self, key: str, seconds: float) -> None:
        """Hold a key for a duration."""

    def hold_keys(self, keys: list[str], seconds: float) -> None:
        """Hold multiple keys together for a duration."""

    def hold_key_while_repeating_key(
        self,
        hold_key: str,
        hold_seconds: float,
        tap_key: str,
        tap_every_seconds: float,
        tap_duration_seconds: float | None = None,
    ) -> None:
        """Hold one key while tapping another key on an interval."""

    def wait(self, seconds: float) -> None:
        """Wait for a bounded duration."""
