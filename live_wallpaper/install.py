# SPDX-License-Identifier: MIT
"""Install and uninstall the systemd timer, theme hook, and bar plugin."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import paths

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = "omarchy-live-wallpaper.service"
TIMER_NAME = "omarchy-live-wallpaper.timer"
HOOK_NAME = "omarchy-live-wallpaper.sh"


def _run(command: list[str], quiet: bool = False) -> bool:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        print(f"error: cannot run {command[0]}: {exc}")
        return False
    if result.returncode != 0 and not quiet:
        detail = (result.stderr or result.stdout or "").strip()
        print(f"error: {' '.join(command)} failed: {detail}")
    return result.returncode == 0


def _install_units(quiet: bool) -> bool:
    target = paths.systemd_user_dir()
    target.mkdir(parents=True, exist_ok=True)
    for name in (SERVICE_NAME, TIMER_NAME):
        source = REPO_ROOT / "systemd" / name
        if not source.is_file():
            print(f"error: missing unit {source}")
            return False
        shutil.copy2(source, target / name)
    ok = _run(["systemctl", "--user", "daemon-reload"], quiet)
    ok &= _run(["systemctl", "--user", "enable", "--now", TIMER_NAME], quiet)
    return ok


def _install_hook(quiet: bool) -> bool:
    hook_dir = paths.omarchy_hooks_dir() / "theme-set.d"
    hook_dir.mkdir(parents=True, exist_ok=True)
    source = REPO_ROOT / "hooks" / HOOK_NAME
    if not source.is_file():
        print(f"error: missing hook {source}")
        return False
    destination = hook_dir / HOOK_NAME
    shutil.copy2(source, destination)
    destination.chmod(0o755)
    return True


def install(quiet: bool = False) -> int:
    if shutil.which("systemctl") is None:
        print("error: systemctl not found; cannot install the timer")
        return 1

    ok = _install_units(quiet)
    ok &= _install_hook(quiet)

    if not ok:
        return 1
    if not quiet:
        print("installed: systemd timer + theme-set hook")
        print(f"  units  {paths.systemd_user_dir()}")
        print(f"  hook   {paths.omarchy_hooks_dir() / 'theme-set.d' / HOOK_NAME}")
        print("check with: systemctl --user list-timers omarchy-live-wallpaper.timer")
    return 0


def uninstall() -> int:
    _run(["systemctl", "--user", "disable", "--now", TIMER_NAME], quiet=True)
    for name in (SERVICE_NAME, TIMER_NAME):
        unit = paths.systemd_user_dir() / name
        try:
            unit.unlink()
        except FileNotFoundError:
            pass
    hook = paths.omarchy_hooks_dir() / "theme-set.d" / HOOK_NAME
    try:
        hook.unlink()
    except FileNotFoundError:
        pass
    _run(["systemctl", "--user", "daemon-reload"], quiet=True)
    print("removed: systemd timer + theme-set hook (wallpapers and cache kept)")
    return 0
