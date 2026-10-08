# SPDX-License-Identifier: MIT
"""Wallpaper source interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """A wallpaper choice that has not been materialised on disk yet.

    `path` may not exist: Bing entries are downloaded only once selected.
    """

    source: str          # "local" | "bing"
    path: str            # absolute path on disk (may not exist yet)
    key: str             # stable identity used for index tracking
    title: str = ""      # human-readable label for notifications
    fetch: bool = False  # True when `path` must be downloaded before use
    url: str = ""        # download URL for `fetch` candidates


class Source:
    """Base class for a wallpaper source."""

    name = "source"

    def candidates(self) -> list[Candidate]:
        raise NotImplementedError

    def prepare(self, candidate: Candidate) -> str | None:
        """Make `candidate.path` exist and return it, or None on failure."""
        return candidate.path if candidate.path else None
