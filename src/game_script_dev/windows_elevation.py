from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path


class WindowsElevationError(Exception):
    """Raised when a Windows administrator relaunch cannot be started."""


def is_windows() -> bool:
    return hasattr(ctypes, "WinDLL")


def is_running_as_admin() -> bool:
    if not is_windows():
        return False
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    return bool(shell32.IsUserAnAdmin())


def relaunch_module_as_admin(
    module: str,
    argv: list[str],
    *,
    cwd: Path,
) -> None:
    if not is_windows():
        raise WindowsElevationError("administrator relaunch is only available on Windows")

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    command = _powershell_command(module, argv, cwd)
    arguments = subprocess.list2cmdline(
        ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    )
    result = shell32.ShellExecuteW(
        None,
        "runas",
        "powershell.exe",
        arguments,
        str(cwd),
        1,
    )
    if result <= 32:
        raise WindowsElevationError(
            f"Windows administrator relaunch failed with ShellExecuteW code {result}"
        )


def _powershell_command(module: str, argv: list[str], cwd: Path) -> str:
    workspace_src = cwd / "src"
    commands = [f"Set-Location -LiteralPath {_quote_powershell_string(str(cwd))}"]
    if workspace_src.is_dir():
        commands.append(
            "$env:PYTHONPATH = "
            f"{_quote_powershell_string(str(workspace_src))} + "
            "[IO.Path]::PathSeparator + $env:PYTHONPATH"
        )
    python_parts = [
        _quote_powershell_string(sys.executable),
        _quote_powershell_string("-m"),
        _quote_powershell_string(module),
        *[_quote_powershell_string(arg) for arg in argv],
    ]
    commands.append("& " + " ".join(python_parts))
    commands.append("exit $LASTEXITCODE")
    return "; ".join(commands)


def _quote_powershell_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
