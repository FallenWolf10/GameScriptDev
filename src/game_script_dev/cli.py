from __future__ import annotations

import argparse
import sys
from pathlib import Path

from game_script_dev.engine import Engine, LiveModeUnavailable
from game_script_dev.logging_setup import create_run_logger
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="game-script-dev",
        description="Run a declarative game automation profile.",
    )
    parser.add_argument(
        "--profile",
        required=True,
        type=Path,
        help="Path to a YAML profile file.",
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "live"),
        default="dry-run",
        help="Execution mode. Defaults to dry-run.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip live-mode confirmation. Has no effect in dry-run mode.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the profile and exit without running the workflow.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.profile)
        validate_profile(profile, args.profile.parent)
    except (ProfileLoadError, ProfileValidationError) as error:
        print(f"Profile error: {error}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Profile is valid: {profile.name}")
        return 0

    logger, run_paths = create_run_logger(Path("logs"), profile.name, args.mode)
    logger.info("Starting profile '%s' in %s mode", profile.name, args.mode)
    logger.info("Run log: %s", run_paths.run_log)

    if args.mode == "live" and not args.yes:
        print(f"Live mode will control target profile: {profile.name}")
        print("Type RUN to continue:")
        confirmation = input("> ").strip()
        if confirmation != "RUN":
            logger.warning("Live mode cancelled by operator")
            print("Cancelled.")
            return 1

    try:
        result = Engine(
            profile=profile,
            mode=args.mode,
            logger=logger,
            artifact_dir=run_paths.artifact_dir,
            profile_dir=args.profile.parent,
        ).run()
    except LiveModeUnavailable as error:
        logger.error("%s", error)
        print(str(error), file=sys.stderr)
        return 3

    logger.info("Profile finished with result: %s", result)
    print(f"Finished: {result}")
    print(f"Log: {run_paths.run_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
