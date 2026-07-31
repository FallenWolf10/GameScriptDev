from __future__ import annotations

import argparse
import sys
from pathlib import Path

from game_script_dev.authoring import check_profile_pack, scaffold_profile_pack
from game_script_dev.distillation import (
    DistillationError,
    distill_repository,
    format_distillation_report,
    validate_distillation_report_path,
    write_distillation_report,
)
from game_script_dev.engine import Engine, LiveModeUnavailable
from game_script_dev.logging_setup import create_run_logger
from game_script_dev.operator_package import run_startup_checks
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile
from game_script_dev.windows_elevation import (
    WindowsElevationError,
    is_running_as_admin,
    relaunch_module_as_admin,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="game-script-dev",
        description="Run a declarative game automation profile.",
    )
    subparsers = parser.add_subparsers(dest="command")

    scaffold = subparsers.add_parser("scaffold-pack")
    scaffold.add_argument("--output", required=True, type=Path)
    scaffold.add_argument("--game", required=True)
    scaffold.add_argument("--mode", required=True)

    check = subparsers.add_parser("check-pack")
    check.add_argument("--profile", required=True, type=Path)

    distill = subparsers.add_parser("distill-repository")
    distill.add_argument("--source-repository", required=True, type=Path)
    distill.add_argument("--workspace", required=True, type=Path)
    distill.add_argument("--destination", required=True, type=Path)
    distill.add_argument("--report", required=True, type=Path)
    distill.add_argument(
        "--apply",
        action="store_true",
        help="Write validated packs. Without this flag, only a report is produced.",
    )
    distill.add_argument(
        "--overwrite-report",
        action="store_true",
        help="Replace an existing report file; destination packs are never overwritten.",
    )

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--logs", type=Path, default=Path("logs"))

    parser.add_argument(
        "--profile",
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
        "--run-as-admin",
        action="store_true",
        help="On Windows, relaunch this command as administrator before running live mode.",
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

    if args.command == "scaffold-pack":
        created = scaffold_profile_pack(args.output, game=args.game, mode=args.mode)
        for path in created:
            print(path)
        return 0

    if args.command == "check-pack":
        result = check_profile_pack(args.profile.parent)
        for message in result.errors:
            print(f"ERROR: {message}")
        for message in result.warnings:
            print(f"WARNING: {message}")
        return 0 if result.ok else 1

    if args.command == "distill-repository":
        try:
            validate_distillation_report_path(
                args.workspace,
                args.destination,
                args.report,
                overwrite=args.overwrite_report,
            )
            report = distill_repository(
                args.source_repository,
                args.workspace,
                args.destination,
                apply=args.apply,
            )
            report_path = write_distillation_report(
                report,
                args.report,
                overwrite=args.overwrite_report,
            )
        except DistillationError as error:
            print(f"Distillation error: {error}", file=sys.stderr)
            return 2
        print(format_distillation_report(report))
        print(f"Report: {report_path}")
        return 0 if report.ok else 1

    if args.command == "doctor":
        report = run_startup_checks(args.workspace, args.logs)
        for name, passed in report.checks.items():
            status = "ok" if passed else "failed"
            print(f"{name}: {status}")
        for message in report.messages:
            print(message)
        return 0 if report.ok else 1

    if args.profile is None:
        parser.error("--profile is required unless a subcommand is used")

    try:
        profile = load_profile(args.profile)
        validate_profile(profile, args.profile.parent)
    except (ProfileLoadError, ProfileValidationError) as error:
        print(f"Profile error: {error}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Profile is valid: {profile.name}")
        return 0

    if args.mode == "live" and args.run_as_admin and not is_running_as_admin():
        relaunch_args = list(argv if argv is not None else sys.argv[1:])
        relaunch_args = [arg for arg in relaunch_args if arg != "--run-as-admin"]
        try:
            relaunch_module_as_admin(
                "game_script_dev",
                relaunch_args,
                cwd=Path.cwd(),
            )
        except WindowsElevationError as error:
            print(str(error), file=sys.stderr)
            return 4
        print("Started administrator live run in a new Windows process.")
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
