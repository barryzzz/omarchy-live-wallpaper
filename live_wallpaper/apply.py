# SPDX-License-Identifier: MIT
"""Handing a chosen wallpaper to Omarchy, and telling the user about it."""

from __future__ import annotations

import shutil
import subprocess

from .sources.base import Candidate

OMARCHY_BG_SET = ("omarchy", "theme", "bg", "set")
OMARCHY_NOTIFY = "omarchy-notification-send"


class ApplyError(RuntimeError):
    """Omarchy refused or was unavailable."""


def omarchy_available() -> bool:
    return shutil.which("omarchy") is not None


def set_background(path: str) -> None:
    """Point Omarchy's background symlink at `path`.

    `omarchy theme bg set` also notifies the running shell over IPC, so the
    change is visible immediately rather than at the next poll.
    """
    if not omarchy_available():
        raise ApplyError("`omarchy` not found on PATH; is this an Omarchy system?")
    try:
        result = subprocess.run(
            [*OMARCHY_BG_SET, path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ApplyError(f"failed to run omarchy: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ApplyError(f"omarchy theme bg set failed ({result.returncode}): {detail}")


def notify(candidate: Candidate, path: str) -> None:
    """Best-effort desktop notification. Never raises."""
    if shutil.which(OMARCHY_NOTIFY) is None:
        return
    headline = "壁纸已切换" if _looks_cjk(candidate.title) else "Wallpaper changed"
    source_label = {"local": "本地", "bing": "Bing"}.get(candidate.source, candidate.source)
    body = f"{source_label}: {candidate.title}" if candidate.title else source_label
    try:
        subprocess.Popen(
            [
                OMARCHY_NOTIFY,
                "--app-name",
                "live-wallpaper",
                "-u",
                "low",
                "-t",
                "2500",
                "--image",
                path,
                headline,
                body,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def _looks_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text or "")
