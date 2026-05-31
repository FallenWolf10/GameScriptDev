from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from game_script_dev.adapters.base import Screenshot


class TesseractOCRAdapter:
    """Optional OCR adapter backed by pytesseract when it is installed locally."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def contains_text(self, text: str, screenshot: Screenshot) -> bool:
        if screenshot.path is None:
            raise ValueError("OCR requires a screenshot path")

        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError:
            self.logger.info("OCR adapter unavailable: pytesseract is not installed")
            return False

        with Image.open(Path(screenshot.path)) as image:
            detected = pytesseract.image_to_string(image)

        return text.strip().lower() in detected.lower()
