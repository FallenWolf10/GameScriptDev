from __future__ import annotations

import importlib.util
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from game_script_dev.dashboard.profile_catalog import ProfileCatalog
from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import validate_profile


@dataclass(frozen=True)
class StartupCheckReport:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)


def run_startup_checks(workspace: Path, log_root: Path) -> StartupCheckReport:
    checks: dict[str, bool] = {}
    messages: list[str] = []

    checks["python_version"] = sys.version_info >= (3, 11)
    if not checks["python_version"]:
        messages.append("Python 3.11 or newer is required")

    required_modules = ["yaml", "PIL", "numpy"]
    missing_modules = [
        module for module in required_modules if importlib.util.find_spec(module) is None
    ]
    checks["runtime_dependencies"] = not missing_modules
    if missing_modules:
        messages.append("missing runtime dependencies: " + ", ".join(missing_modules))

    try:
        log_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=log_root, delete=True):
            pass
        checks["writable_logs"] = True
    except OSError as error:
        checks["writable_logs"] = False
        messages.append(f"log folder is not writable: {error}")

    profiles = ProfileCatalog(workspace / "profiles").list_profiles()
    checks["profile_discovery"] = bool(profiles)
    if not profiles:
        messages.append("no profiles discovered")

    valid_profiles = [profile for profile in profiles if profile.valid]
    checks["profile_validation"] = bool(valid_profiles)
    if not valid_profiles:
        messages.append("no valid profiles discovered")

    demo_profile = workspace / "profiles" / "demo" / "local_target" / "profile.yaml"
    checks["demo_profile"] = _profile_valid(demo_profile)
    if not checks["demo_profile"]:
        messages.append("local demo target profile is missing or invalid")

    checks["live_adapter_boundary"] = _live_adapter_importable()
    if not checks["live_adapter_boundary"]:
        messages.append("live adapter module is not importable")

    return StartupCheckReport(
        ok=all(checks.values()),
        checks=checks,
        messages=messages,
    )


def _profile_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        profile = load_profile(path)
        validate_profile(profile, path.parent)
    except Exception:
        return False
    return True


def _live_adapter_importable() -> bool:
    try:
        import game_script_dev.adapters.live  # noqa: F401
    except Exception:
        return False
    return True
