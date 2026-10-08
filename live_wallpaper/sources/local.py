# SPDX-License-Identifier: MIT
"""Local source: the current Omarchy theme's background images.

Mirrors the directories `omarchy-theme-bg-next` scans, so the rotation pool
is exactly the set of images the stock switcher would cycle through. Because
one of those directories is theme-scoped, changing the theme changes the pool
with no extra work on our side.
"""

from __future__ import annotations

from pathlib import Path

from .. import paths
from .base import Candidate, Source

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")


def current_theme_name() -> str:
    try:
        return paths.theme_name_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _images_in(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    found = []
    for entry in directory.iterdir():
        try:
            if not entry.is_file():
                continue
        except OSError:
            continue  # broken symlink
        if entry.suffix.lower() in IMAGE_SUFFIXES:
            found.append(entry)
    return found


class LocalSource(Source):
    name = "local"

    def __init__(self, theme_name: str | None = None) -> None:
        self.theme_name = theme_name if theme_name is not None else current_theme_name()

    def search_dirs(self) -> list[Path]:
        dirs = []
        if self.theme_name:
            dirs.append(paths.user_backgrounds_dir(self.theme_name))
        dirs.append(paths.theme_backgrounds_dir())
        return dirs

    def candidates(self) -> list[Candidate]:
        seen: set[str] = set()
        result: list[Candidate] = []
        for directory in self.search_dirs():
            for path in _images_in(directory):
                try:
                    resolved = str(path.resolve())
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                result.append(
                    Candidate(
                        source=self.name,
                        path=resolved,
                        key=resolved,
                        title=path.name,
                    )
                )
        # Sort by path for a stable order, matching the stock switcher.
        result.sort(key=lambda c: c.path)
        return result
