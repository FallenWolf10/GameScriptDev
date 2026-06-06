from __future__ import annotations

import base64
import io
import logging
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
class TargetPreview:
    title: str
    process_name: str | None
    width: int
    height: int
    data_url: str

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "process_name": self.process_name,
            "width": self.width,
            "height": self.height,
            "data_url": self.data_url,
        }


class TargetPreviewService:
    def __init__(
        self,
        logger: logging.Logger | None = None,
        window_adapter: WindowsWindowAdapter | None = None,
        window_capture: Win32WindowCapture | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.window_adapter = window_adapter
        self.window_capture = window_capture

    def capture(self, profile_path: Path) -> TargetPreview:
        try:
            profile = load_profile(profile_path)
            validate_profile(profile, profile_path.parent)
        except (ProfileLoadError, ProfileValidationError) as error:
            raise TargetPreviewError(str(error)) from error

        adapter = self.window_adapter or WindowsWindowAdapter(
            self.logger,
            require_foreground=False,
        )
        target = adapter.find_target(profile)
        if target is None:
            raise TargetPreviewError("target window is not running")

        try:
            adapter.verify_window(target, profile)
            image = self._capture_window(target)
        except (LiveAdaptersUnavailable, TargetWindowNotReady, OSError) as error:
            raise TargetPreviewError(str(error)) from error

        return TargetPreview(
            title=target.title,
            process_name=target.process_name,
            width=target.content_width,
            height=target.content_height,
            data_url=_image_data_url(image),
        )

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
