# SPDX-License-Identifier: MIT
"""Filesystem locations the tool reads and writes.

Everything is XDG-based and resolved on each call, so tests can redirect the
whole layout by setting XDG_* / HOME in the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "omarchy-live-wallpaper"


def _home() -> Path:
    home = os.environ.get("HOME")
    return Path(home) if home else Path(os.path.expanduser("~"))


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", _home() / ".config"))


def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", _home() / ".local/state"))


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", _home() / ".cache"))


def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", _home() / ".local/share"))


# --- This application -------------------------------------------------------

def app_config_dir() -> Path:
    return config_dir() / APP_NAME


def config_file() -> Path:
    return app_config_dir() / "config.toml"


def app_state_dir() -> Path:
    return state_dir() / APP_NAME


def state_file() -> Path:
    return app_state_dir() / "state.json"


def bing_cache_dir() -> Path:
    """Downloaded Bing images. Re-downloadable, so this is a cache."""
    return cache_dir() / APP_NAME / "bing"


# --- Omarchy (read-mostly) --------------------------------------------------

def omarchy_state_dir() -> Path:
    return state_dir() / "omarchy"


def current_background_link() -> Path:
    """Symlink owned by `omarchy theme bg set`; the shell renders whatever
    this points at."""
    return omarchy_state_dir() / "current" / "background"


def theme_name_file() -> Path:
    return omarchy_state_dir() / "current" / "theme.name"


def theme_backgrounds_dir() -> Path:
    return omarchy_state_dir() / "current" / "theme" / "backgrounds"


def user_backgrounds_dir(theme_name: str) -> Path:
    return config_dir() / "omarchy" / "backgrounds" / theme_name


def omarchy_hooks_dir() -> Path:
    return config_dir() / "omarchy" / "hooks"


def systemd_user_dir() -> Path:
    return config_dir() / "systemd" / "user"
