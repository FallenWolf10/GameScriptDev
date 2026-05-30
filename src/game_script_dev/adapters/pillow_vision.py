from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from game_script_dev.adapters.base import Screenshot
from game_script_dev.schema import Anchor


class PillowVisionAdapter:
    def __init__(
        self,
        profile_dir: Path,
        logger: logging.Logger,
        default_threshold: float = 0.98,
    ) -> None:
        self.profile_dir = profile_dir
        self.logger = logger
        self.default_threshold = default_threshold

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        if anchor.type == "template":
            if anchor.asset is None:
                return False
            return self.find_template_center(anchor.asset, screenshot) is not None

        self.logger.info("OCR anchor is not implemented yet: %s", anchor.name)
        return False

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        if screenshot.path is None:
            raise ValueError("PillowVisionAdapter requires a screenshot path")

        template_path = self.profile_dir / asset
        match = find_template_center(
            screenshot_path=screenshot.path,
            template_path=template_path,
            threshold=self.default_threshold,
        )
        self.logger.info(
            "Pillow template match: asset=%s screenshot=%s result=%s",
            asset,
            screenshot.path,
            match,
        )
        return match


def find_template_center(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.98,
) -> tuple[int, int] | None:
    screenshot = _load_rgb_array(screenshot_path)
    template = _load_rgb_array(template_path)

    screen_height, screen_width, _ = screenshot.shape
    template_height, template_width, _ = template.shape

    if template_height > screen_height or template_width > screen_width:
        return None

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
        return None

    x, y = best_xy
    return (x + template_width // 2, y + template_height // 2)


def _load_rgb_array(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def _similarity_score(patch: np.ndarray, template: np.ndarray) -> float:
    max_distance = 255.0
    mean_distance = np.mean(np.abs(patch - template))
    return float(1.0 - (mean_distance / max_distance))
