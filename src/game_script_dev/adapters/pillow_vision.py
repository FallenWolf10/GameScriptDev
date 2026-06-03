from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - optional acceleration path
    cv2 = None

from game_script_dev.adapters.base import OCRAdapter, Screenshot
from game_script_dev.schema import Anchor


class TemplateMatchResult(NamedTuple):
    center: tuple[int, int] | None
    best_score: float
    best_xy: tuple[int, int] | None
    backend: str


class PillowVisionAdapter:
    def __init__(
        self,
        profile_dir: Path,
        logger: logging.Logger,
        default_threshold: float = 0.98,
        ocr_adapter: OCRAdapter | None = None,
        prefer_opencv: bool = True,
    ) -> None:
        self.profile_dir = profile_dir
        self.logger = logger
        self.default_threshold = default_threshold
        self.ocr_adapter = ocr_adapter
        self.prefer_opencv = prefer_opencv

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        if anchor.type == "template":
            if anchor.asset is None:
                return False
            return self.find_template_center(anchor.asset, screenshot) is not None

        if anchor.type == "text":
            if anchor.text is None:
                return False
            if self.ocr_adapter is None:
                self.logger.info("OCR anchor unavailable: %s", anchor.name)
                return False
            present = self.ocr_adapter.contains_text(anchor.text, screenshot)
            self.logger.info(
                "OCR anchor match: anchor=%s screenshot=%s result=%s",
                anchor.name,
                screenshot.path or screenshot.source,
                present,
            )
            return present

        self.logger.info("Unsupported anchor type '%s': %s", anchor.type, anchor.name)
        return False

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        if screenshot.path is None:
            raise ValueError("PillowVisionAdapter requires a screenshot path")

        template_path = self.profile_dir / asset
        match = find_template_center_with_diagnostics(
            screenshot_path=screenshot.path,
            template_path=template_path,
            threshold=self.default_threshold,
            prefer_opencv=self.prefer_opencv,
        )
        self.logger.info(
            "Pillow template match: asset=%s screenshot=%s threshold=%s result=%s best_score=%.6f best_xy=%s backend=%s",
            asset,
            screenshot.path,
            self.default_threshold,
            match.center,
            match.best_score,
            match.best_xy,
            match.backend,
        )
        return match.center


def find_template_center(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.98,
    prefer_opencv: bool = True,
) -> tuple[int, int] | None:
    return find_template_center_with_diagnostics(
        screenshot_path=screenshot_path,
        template_path=template_path,
        threshold=threshold,
        prefer_opencv=prefer_opencv,
    ).center


def find_template_center_with_diagnostics(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.98,
    prefer_opencv: bool = True,
) -> TemplateMatchResult:
    if prefer_opencv and cv2 is not None:
        return _find_template_center_opencv(
            screenshot_path=screenshot_path,
            template_path=template_path,
            threshold=threshold,
        )
    return _find_template_center_numpy(
        screenshot_path=screenshot_path,
        template_path=template_path,
        threshold=threshold,
    )


def _find_template_center_opencv(
    screenshot_path: Path,
    template_path: Path,
    threshold: float,
) -> TemplateMatchResult:
    screenshot = _load_bgr_array(template_path=screenshot_path)
    template = _load_bgr_array(template_path=template_path)

    if screenshot is None or template is None:
        return _find_template_center_numpy(
            screenshot_path=screenshot_path,
            template_path=template_path,
            threshold=threshold,
        )

    screen_height, screen_width, _ = screenshot.shape
    template_height, template_width, _ = template.shape

    if template_height > screen_height or template_width > screen_width:
        return TemplateMatchResult(None, -1.0, None, "opencv")

    # TM_SQDIFF_NORMED gives a 0-best score; convert to a 1-best score so the
    # profile threshold semantics stay close to the existing matcher.
    response = cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF_NORMED)
    min_value, _, min_location, _ = cv2.minMaxLoc(response)
    best_score = float(1.0 - min_value)
    best_xy = (int(min_location[0]), int(min_location[1]))

    if best_score < threshold:
        return TemplateMatchResult(None, best_score, best_xy, "opencv")

    x, y = best_xy
    return TemplateMatchResult(
        (x + template_width // 2, y + template_height // 2),
        best_score,
        best_xy,
        "opencv",
    )


def _find_template_center_numpy(
    screenshot_path: Path,
    template_path: Path,
    threshold: float,
) -> TemplateMatchResult:
    screenshot = _load_rgb_array(screenshot_path)
    template = _load_rgb_array(template_path)

    screen_height, screen_width, _ = screenshot.shape
    template_height, template_width, _ = template.shape

    if template_height > screen_height or template_width > screen_width:
        return TemplateMatchResult(None, -1.0, None, "numpy")

    best_score = -1.0
    best_xy: tuple[int, int] | None = None

    for y in range(screen_height - template_height + 1):
        for x in range(screen_width - template_width + 1):
            patch = screenshot[y : y + template_height, x : x + template_width]
            score = _similarity_score(patch, template)
            if score > best_score:
                best_score = score
                best_xy = (x, y)

    if best_xy is None or best_score < threshold:
        return TemplateMatchResult(None, best_score, best_xy, "numpy")

    x, y = best_xy
    return TemplateMatchResult(
        (x + template_width // 2, y + template_height // 2),
        best_score,
        best_xy,
        "numpy",
    )


def _load_rgb_array(path: Path) -> np.ndarray:
    cache_key = _path_cache_key(path)
    return _load_rgb_array_cached(*cache_key)


def _load_bgr_array(template_path: Path) -> np.ndarray | None:
    if cv2 is None:
        return None
    cache_key = _path_cache_key(template_path)
    return _load_bgr_array_cached(*cache_key)


@functools.lru_cache(maxsize=256)
def _load_rgb_array_cached(path_text: str, mtime_ns: int) -> np.ndarray:
    del mtime_ns
    with Image.open(path_text) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


@functools.lru_cache(maxsize=256)
def _load_bgr_array_cached(path_text: str, mtime_ns: int) -> np.ndarray | None:
    del mtime_ns
    if cv2 is None:  # pragma: no cover - guarded before cached call
        return None
    return cv2.imread(path_text, cv2.IMREAD_COLOR)


def _path_cache_key(path: Path) -> tuple[str, int]:
    resolved = path.resolve()
    return (str(resolved), resolved.stat().st_mtime_ns)


def _similarity_score(patch: np.ndarray, template: np.ndarray) -> float:
    max_distance = 255.0
    mean_distance = np.mean(np.abs(patch - template))
    return float(1.0 - (mean_distance / max_distance))
