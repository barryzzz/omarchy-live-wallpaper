# SPDX-License-Identifier: MIT
"""Wallpaper sources."""

from .base import Candidate, Source
from .bing import BingError, BingSource
from .local import LocalSource, current_theme_name

__all__ = [
    "BingError",
    "BingSource",
    "Candidate",
    "LocalSource",
    "Source",
    "current_theme_name",
]
