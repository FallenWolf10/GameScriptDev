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


@dataclass(frozen=True)
class Screenshot:
    source: str
    path: Path | None = None


class WindowAdapter(Protocol):
    def find_target(self, profile: Profile) -> TargetWindow | None:
        """Return the target window when it is available."""

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        """Focus and verify or resize the target window."""


class ScreenAdapter(Protocol):
    def capture(self, window: TargetWindow) -> Screenshot:
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


class InputAdapter(Protocol):
    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        """Click a detected template target."""

    def click_region(self, region_name: str) -> None:
        """Click a named profile region."""

    def press_key(self, key: str) -> None:
        """Press a key."""

    def hold_key(self, key: str, seconds: float) -> None:
        """Hold a key for a duration."""

    def wait(self, seconds: float) -> None:
        """Wait for a bounded duration."""
