from __future__ import annotations

import logging
from dataclasses import dataclass, field
from collections.abc import Callable
from pathlib import Path

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    WindowsWindowAdapter,
    current_process_integrity_rid,
    process_integrity_rid,
)
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import (
    Action,
    Profile,
    ProfileValidationError,
    validate_profile,
)


@dataclass(frozen=True)
class ReadinessReport:
    profile_id: str
    valid: bool
    live_available: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    target_status: str = "not_checked"
    resolution_status: str = "not_checked"
    compatibility_status: str = "not_applicable"

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "valid": self.valid,
            "live_available": self.live_available,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "target_status": self.target_status,
            "resolution_status": self.resolution_status,
            "compatibility_status": self.compatibility_status,
        }


def evaluate_readiness(
    profile_id: str,
    profile_path: Path,
    *,
    last_dry_run_success: bool,
    check_target: bool = True,
    window_adapter: WindowsWindowAdapter | None = None,
    background_input_blocker: Callable[[Profile, TargetWindow], str | None] | None = None,
) -> ReadinessReport:
    blockers: list[str] = []
    warnings: list[str] = []
    target_status = "not_checked"
    resolution_status = "not_checked"
    compatibility_status = "not_applicable"

    try:
        profile = load_profile(profile_path)
        validate_profile(profile, profile_path.parent)
    except (ProfileLoadError, ProfileValidationError) as error:
        return ReadinessReport(
            profile_id=profile_id,
            valid=False,
            live_available=False,
            blockers=[str(error)],
        )

    blockers.extend(_live_capability_blockers(profile))
    if profile.profile_pack is not None:
        if profile.profile_pack.compatibility_complete:
            compatibility_status = "passed"
        else:
            compatibility_status = "incomplete"
            missing = ", ".join(profile.profile_pack.missing_compatibility_checks)
            blockers.append(
                "profile pack compatibility checklist is incomplete: " + missing
            )
    if not last_dry_run_success:
        blockers.append("live mode requires a successful dry-run from the dashboard")

    if check_target:
        adapter = window_adapter or WindowsWindowAdapter(logging.getLogger(__name__))
        try:
            target = adapter.find_target(profile)
            if target is None:
                target_status = "missing"
                blockers.append("target window is not running")
            else:
                target_status = "matched"
                resolution_status = _resolution_status(profile, target.width, target.height)
                if resolution_status == "failed":
                    blockers.append(
                        "target window resolution mismatch: "
                        f"actual={target.width}x{target.height} "
                        f"expected={profile.resolution.width}x{profile.resolution.height}"
                    )
                checker = background_input_blocker
                if checker is None and window_adapter is None:
                    checker = _background_input_privilege_blocker
                if checker is not None:
                    blocker = checker(profile, target)
                    if blocker:
                        blockers.append(blocker)
        except LiveAdaptersUnavailable as error:
            target_status = "unavailable"
            blockers.append(str(error))

    return ReadinessReport(
        profile_id=profile_id,
        valid=True,
        live_available=not blockers,
        blockers=blockers,
        warnings=warnings,
        target_status=target_status,
        resolution_status=resolution_status,
        compatibility_status=compatibility_status,
    )


def _live_capability_blockers(profile: Profile) -> list[str]:
    blockers: list[str] = []
    if profile.resolution.policy == "attempt_resize":
        blockers.append("window resizing is not implemented for live mode")
    if _uses_text_anchors(profile):
        blockers.append("OCR adapter is optional and not configured by default")
    return blockers


def _resolution_status(profile: Profile, width: int, height: int) -> str:
    if profile.resolution.policy == "ignore":
        return "ignored"
    if width == profile.resolution.width and height == profile.resolution.height:
        return "passed"
    return "failed"


def _uses_text_anchors(profile: Profile) -> bool:
    for state in profile.states.values():
        anchors = (
            state.required_anchors + state.optional_anchors + state.forbidden_anchors
        )
        if any(anchor.type == "text" for anchor in anchors):
            return True
    for interruption in profile.interruptions:
        if any(anchor.type == "text" for anchor in interruption.required_anchors):
            return True
    return False


def uses_pointer_actions(actions: list[Action]) -> bool:
    return any(action.type in {"click_point", "click_template"} for action in actions)


def _background_input_privilege_blocker(
    profile: Profile,
    target: TargetWindow,
) -> str | None:
    if profile.target.input_mode != "background_window_messages":
        return None
    if target.process_id is None:
        return None
    if not _uses_live_input(profile):
        return None

    try:
        runner_integrity = current_process_integrity_rid()
        target_integrity = process_integrity_rid(target.process_id)
    except (LiveAdaptersUnavailable, OSError):
        return None

    if runner_integrity < target_integrity:
        return (
            "background input requires the runner to use the same privilege level "
            "as the target window"
        )
    return None


def _uses_live_input(profile: Profile) -> bool:
    for state in profile.states.values():
        if any(
            action.type
            in {"click_point", "click_template", "press_key", "hold_key"}
            for action in state.actions
        ):
            return True
    for interruption in profile.interruptions:
        if any(
            action.type
            in {"click_point", "click_template", "press_key", "hold_key"}
            for action in interruption.recovery_actions
        ):
            return True
    return False
