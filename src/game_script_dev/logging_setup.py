from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    day_dir: Path
    daily_log: Path
    run_log: Path


def create_run_logger(log_root: Path, profile_name: str) -> tuple[logging.Logger, RunPaths]:
    now = datetime.now()
    day_dir = log_root / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    safe_profile_name = profile_name.lower().replace(" ", "_")
    run_log = day_dir / f"run_{now.strftime('%H%M%S')}_{safe_profile_name}.log"
    daily_log = day_dir / "automation_activity.log"

    logger = logging.getLogger(f"game_script_dev.{now.strftime('%H%M%S%f')}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for path in (daily_log, run_log):
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger, RunPaths(day_dir=day_dir, daily_log=daily_log, run_log=run_log)
