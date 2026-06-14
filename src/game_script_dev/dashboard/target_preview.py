from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PIL import ImageGrab

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    TargetWindowNotReady,
    WindowsWindowAdapter,
    Win32WindowCapture,
)
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile


class TargetPreviewError(Exception):
    """Raised when the selected target cannot be previewed."""


@dataclass(frozen=True)
class TargetPreviewMetadata:
    title: str
    process_name: str | None
    width: int
    height: int

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "process_name": self.process_name,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class TargetPreview(TargetPreviewMetadata):
    data_url: str

    def to_dict(self) -> dict[str, object]:
        return {**super().to_dict(), "data_url": self.data_url}


class TargetPreviewService:
    def __init__(
        self,
        logger: logging.Logger | None = None,
        window_adapter: WindowsWindowAdapter | None = None,
        window_capture: Win32WindowCapture | None = None,
        cache_ttl_seconds: float = 1.0,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.window_adapter = window_adapter
        self.window_capture = window_capture
        self.cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self._cache: dict[Path, tuple[float, TargetPreview]] = {}

    def inspect(self, profile_path: Path) -> TargetPreviewMetadata:
        target = self._resolve_target(profile_path)
        return TargetPreviewMetadata(
            title=target.title,
            process_name=target.process_name,
            width=target.content_width,
            height=target.content_height,
        )

    def capture(self, profile_path: Path) -> TargetPreview:
        now = time.monotonic()
        cached = self._cache.get(profile_path)
        if cached is not None and now - cached[0] <= self.cache_ttl_seconds:
            return cached[1]

        metadata, image = self.capture_image(profile_path)

        preview = TargetPreview(
            title=metadata.title,
            process_name=metadata.process_name,
            width=metadata.width,
            height=metadata.height,
            data_url=_image_data_url(image),
        )
        self._cache[profile_path] = (now, preview)
        return preview

    def capture_jpeg(
        self,
        profile_path: Path,
        *,
        max_width: int | None = None,
        quality: int = 75,
    ) -> tuple[TargetPreviewMetadata, bytes]:
        metadata, image = self.capture_image(profile_path)
        if max_width is not None and max_width > 0 and image.width > max_width:
            scale = max_width / image.width
            height = max(1, round(image.height * scale))
            image = image.resize((max_width, height))
        buffer = io.BytesIO()
        image.convert("RGB").save(
            buffer,
            format="JPEG",
            quality=max(30, min(quality, 95)),
            optimize=True,
        )
        return metadata, buffer.getvalue()

    def capture_image(
        self,
        profile_path: Path,
    ) -> tuple[TargetPreviewMetadata, Image.Image]:
        target = self._resolve_target(profile_path)
        image = self._capture_window(target)
        metadata = TargetPreviewMetadata(
            title=target.title,
            process_name=target.process_name,
            width=target.content_width,
            height=target.content_height,
        )
        return metadata, image

    def _resolve_target(self, profile_path: Path) -> TargetWindow:
        profile = self._load_profile(profile_path)
        adapter = self.window_adapter or WindowsWindowAdapter(
            self.logger,
            require_foreground=False,
        )
        target = adapter.find_target(profile)
        if target is None:
            raise TargetPreviewError("target window is not running")
        try:
            return adapter.verify_window(target, profile)
        except (LiveAdaptersUnavailable, TargetWindowNotReady, OSError) as error:
            raise TargetPreviewError(str(error)) from error

    def _load_profile(self, profile_path: Path):
        try:
            profile = load_profile(profile_path)
            validate_profile(profile, profile_path.parent)
        except (ProfileLoadError, ProfileValidationError) as error:
            raise TargetPreviewError(str(error)) from error
        return profile

    def _capture_window(self, target: TargetWindow) -> Image.Image:
        if target.handle is not None:
            capture = self.window_capture or Win32WindowCapture.create()
            return capture.capture_client(target)

        bbox = (
            target.content_left,
            target.content_top,
            target.content_left + target.content_width,
            target.content_top + target.content_height,
        )
        return ImageGrab.grab(bbox)


def _image_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
