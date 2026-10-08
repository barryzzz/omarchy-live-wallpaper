# SPDX-License-Identifier: MIT
"""Configuration: defaults merged with the user's TOML file.

Unknown keys and out-of-range values never abort a rotation — they are
reported as warnings and clamped, because a bad config should degrade to
"still changing wallpapers", not to "silently stops".
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "interval_hours": 24.0,
    "source": "both",
    "bing_market": "zh-CN",
    "bing_archive_days": 1,
    "bing_resolution": "UHD",
    "notify": True,
}

VALID_SOURCES = ("local", "bing", "both")
VALID_RESOLUTIONS = ("UHD", "1920x1080", "1366x768", "1024x768")

MIN_INTERVAL_HOURS = 1 / 60  # one minute: the systemd timer cannot fire faster
MAX_INTERVAL_HOURS = 24 * 30
MIN_ARCHIVE_DAYS = 1
MAX_ARCHIVE_DAYS = 16


@dataclass(frozen=True)
class Config:
    interval_hours: float = DEFAULTS["interval_hours"]
    source: str = DEFAULTS["source"]
    bing_market: str = DEFAULTS["bing_market"]
    bing_archive_days: int = DEFAULTS["bing_archive_days"]
    bing_resolution: str = DEFAULTS["bing_resolution"]
    notify: bool = DEFAULTS["notify"]

    def interval_seconds(self) -> float:
        return self.interval_hours * 3600.0

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def default_config() -> Config:
    return Config()


def _warn(warnings: list[str], message: str) -> None:
    warnings.append(message)


def _coerce(raw: dict[str, Any], warnings: list[str]) -> Config:
    values: dict[str, Any] = {}

    known = {f.name for f in fields(Config)}
    for key in sorted(raw):
        if key not in known:
            _warn(warnings, f"unknown option '{key}' (ignored)")

    # interval_hours
    interval = raw.get("interval_hours", DEFAULTS["interval_hours"])
    try:
        interval = float(interval)
    except (TypeError, ValueError):
        _warn(warnings, f"interval_hours must be a number, got {interval!r}; using default")
        interval = DEFAULTS["interval_hours"]
    if interval < MIN_INTERVAL_HOURS:
        _warn(warnings, f"interval_hours {interval} is below the {MIN_INTERVAL_HOURS} minimum; clamping")
        interval = MIN_INTERVAL_HOURS
    elif interval > MAX_INTERVAL_HOURS:
        _warn(warnings, f"interval_hours {interval} exceeds the {MAX_INTERVAL_HOURS} maximum; clamping")
        interval = MAX_INTERVAL_HOURS
    values["interval_hours"] = interval

    # source
    source = raw.get("source", DEFAULTS["source"])
    source = str(source).strip().lower()
    if source not in VALID_SOURCES:
        _warn(warnings, f"source must be one of {', '.join(VALID_SOURCES)}, got {source!r}; using default")
        source = DEFAULTS["source"]
    values["source"] = source

    # bing_market
    market = raw.get("bing_market", DEFAULTS["bing_market"])
    market = str(market).strip()
    if not market:
        _warn(warnings, f"bing_market is empty; using default {DEFAULTS['bing_market']!r}")
        market = DEFAULTS["bing_market"]
    values["bing_market"] = market

    # bing_archive_days
    days = raw.get("bing_archive_days", DEFAULTS["bing_archive_days"])
    try:
        days = int(days)
    except (TypeError, ValueError):
        _warn(warnings, f"bing_archive_days must be an integer, got {days!r}; using default")
        days = DEFAULTS["bing_archive_days"]
    if days < MIN_ARCHIVE_DAYS or days > MAX_ARCHIVE_DAYS:
        _warn(
            warnings,
            f"bing_archive_days {days} outside {MIN_ARCHIVE_DAYS}..{MAX_ARCHIVE_DAYS}; clamping",
        )
        days = max(MIN_ARCHIVE_DAYS, min(MAX_ARCHIVE_DAYS, days))
    values["bing_archive_days"] = days

    # bing_resolution
    resolution = raw.get("bing_resolution", DEFAULTS["bing_resolution"])
    resolution = str(resolution).strip()
    if resolution not in VALID_RESOLUTIONS:
        _warn(
            warnings,
            f"bing_resolution must be one of {', '.join(VALID_RESOLUTIONS)}, "
            f"got {resolution!r}; using default",
        )
        resolution = DEFAULTS["bing_resolution"]
    values["bing_resolution"] = resolution

    # notify
    notify = raw.get("notify", DEFAULTS["notify"])
    if isinstance(notify, str):
        notify = notify.strip().lower() in ("1", "true", "yes", "on")
    else:
        notify = bool(notify)
    values["notify"] = notify

    return Config(**values)


def load(path: Path | None = None, warnings: list[str] | None = None) -> Config:
    """Load config from `path` (default: the user config file).

    Warnings are appended to `warnings` when given; a missing file is not an
    error -- it just means "all defaults".
    """
    sink: list[str] = [] if warnings is None else warnings
    target = paths.config_file() if path is None else Path(path)

    raw: dict[str, Any] = {}
    if target.is_file():
        try:
            with target.open("rb") as handle:
                raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            _warn(sink, f"{target} is not valid TOML ({exc}); using defaults")
            raw = {}
        except OSError as exc:
            _warn(sink, f"cannot read {target} ({exc}); using defaults")
            raw = {}

    if not isinstance(raw, dict):
        _warn(sink, f"{target} must contain a TOML table; using defaults")
        raw = {}

    return _coerce(raw, sink)
