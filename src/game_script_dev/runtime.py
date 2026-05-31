from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from game_script_dev.adapters.base import (
    InputAdapter,
    ScreenAdapter,
    TargetWindow,
    VisionAdapter,
    WindowAdapter,
)
from game_script_dev.adapters.dry_run import (
    DryRunInputAdapter,
    DryRunScreenAdapter,
    DryRunVisionAdapter,
    DryRunWindowAdapter,
)
from game_script_dev.adapters.live import LiveInputAdapter
from game_script_dev.adapters.live import LiveScreenAdapter
from game_script_dev.adapters.live import LiveVisionAdapter
from game_script_dev.adapters.live import WindowsWindowAdapter
from game_script_dev.schema import Profile


@dataclass(frozen=True)
class RuntimeContext:
    mode: str
    window: TargetWindow
    window_adapter: WindowAdapter
    screen_adapter: ScreenAdapter
    vision_adapter: VisionAdapter
    input_adapter: InputAdapter


def create_runtime(
    profile: Profile,
    mode: str,
    logger: logging.Logger,
    artifact_dir: Path | None = None,
    profile_dir: Path | None = None,
) -> RuntimeContext:
    if mode == "live":
        window_adapter = WindowsWindowAdapter(logger)
        screen_adapter = LiveScreenAdapter(
            artifact_dir or Path("logs/live_captures"),
            window_adapter=window_adapter,
            profile=profile,
        )
        vision_adapter = LiveVisionAdapter(profile_dir or Path("."), logger)
    else:
        window_adapter = DryRunWindowAdapter(logger)
        screen_adapter = DryRunScreenAdapter(logger)
        vision_adapter = DryRunVisionAdapter(logger)
        input_adapter = DryRunInputAdapter(logger)

    window = window_adapter.find_target(profile)
    if window is None:
        raise RuntimeError("target application is not running")

    window_adapter.prepare_window(window, profile.resolution)

    if mode == "live":
        input_adapter = LiveInputAdapter(
            target_window=window,
            profile=profile,
            regions=profile.regions,
            window_adapter=window_adapter,
        )

    return RuntimeContext(
        mode=mode,
        window=window,
        window_adapter=window_adapter,
        screen_adapter=screen_adapter,
        vision_adapter=vision_adapter,
        input_adapter=input_adapter,
    )
