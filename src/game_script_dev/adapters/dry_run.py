from __future__ import annotations

import logging

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.schema import Anchor, Profile, Resolution


class DryRunWindowAdapter:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def find_target(self, profile: Profile) -> TargetWindow:
        title = profile.target.window_title_contains or "dry-run target"
        self.logger.info(
            "Dry-run target lookup: process=%s title_contains=%s",
            profile.target.process_name,
            profile.target.window_title_contains,
        )
        return TargetWindow(
            title=title,
            process_name=profile.target.process_name,
            left=0,
            top=0,
            width=profile.resolution.width,
            height=profile.resolution.height,
            handle=None,
        )

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        self.logger.info(
            "Dry-run prepare window '%s': %sx%s policy=%s",
            window.title,
            resolution.width,
            resolution.height,
            resolution.policy,
        )


class DryRunScreenAdapter:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def capture(self, window: TargetWindow) -> Screenshot:
        self.logger.info("Dry-run capture window: %s", window.title)
        return Screenshot(source=window.title)


class DryRunVisionAdapter:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        detail = anchor.asset if anchor.type == "template" else anchor.text
        self.logger.info(
            "Dry-run detect anchor '%s' on %s: %s",
            anchor.name,
            screenshot.source,
            detail,
        )
        return True

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int]:
        self.logger.info(
            "Dry-run find template center on %s: %s",
            screenshot.source,
            asset,
        )
        return (0, 0)


class DryRunInputAdapter:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        self.logger.info("Dry-run click_template: %s on %s", asset, screenshot.source)

    def click_region(self, region_name: str) -> None:
        self.logger.info("Dry-run click_point region: %s", region_name)

    def press_key(self, key: str) -> None:
        self.logger.info("Dry-run press_key: %s", key)

    def hold_key(self, key: str, seconds: float) -> None:
        self.logger.info("Dry-run hold_key: %s for %s seconds", key, seconds)

    def wait(self, seconds: float) -> None:
        self.logger.info("Dry-run bounded wait: %s seconds", seconds)
