# SPDX-License-Identifier: MIT
"""Rotation decisions: build the pool, pick the next image.

The scheduler (systemd timer) calls `plan()` repeatedly; `plan()` decides
whether it is time yet. Keeping the decision here rather than in the timer
means changing `interval_hours` takes effect immediately, with no unit edit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import paths
from .config import Config
from .sources import Candidate, LocalSource
from .sources.bing import BingSource
from .state import State

LOCAL = "local"
BING = "bing"


@dataclass
class Plan:
    """What `plan()` decided."""

    action: str                      # "apply" | "skip-interval" | "skip-empty" | "skip-single"
    candidate: Candidate | None = None
    applied_path: str | None = None  # filled in after a successful apply
    reason: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.action == "apply"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "source": self.candidate.source if self.candidate else None,
            "title": self.candidate.title if self.candidate else None,
            "path": self.applied_path,
            "warnings": list(self.warnings),
        }


def build_pool(config: Config) -> list[Candidate]:
    """Candidates to choose from, in the order sources should be tried."""
    local = LocalSource().candidates()
    bing = BingSource(
        market=config.bing_market,
        archive_days=config.bing_archive_days,
        resolution=config.bing_resolution,
    ).candidates()

    if config.source == LOCAL:
        return local
    if config.source == BING:
        return bing
    return local + bing  # "both": alternation happens in _choose


def _due(state: State, config: Config, now: float) -> bool:
    """Whether a switch is due. Measured from the slot, not the last switch,
    so time spent powered off counts and a few minutes of timer lateness does
    not push the schedule later."""
    base = state.countdown_from()
    if base is None:
        return True
    return (now - base) >= config.interval_seconds()


def _choose(
    pool: list[Candidate], config: Config, state: State
) -> Candidate | None:
    """Pick the next candidate, alternating sources when the pool spans two.

    Alternation picks the *source*, then advances within that source's own
    list. Choosing from the merged list instead would keep landing on the
    first entry of whichever source follows the current one, so a theme with
    eight local images would only ever show its first one.
    """
    if not pool:
        return None

    # Group by source, preserving each source's internal ordering.
    by_source: dict[str, list[Candidate]] = {}
    for candidate in pool:
        by_source.setdefault(candidate.source, []).append(candidate)

    current_source = state.last_source if state.last_source in by_source else None

    # Which source to serve next. In `both` mode that is the other one; in
    # single-source mode the config pins it regardless of what ran last.
    sources = [s for s in (LOCAL, BING) if s in by_source]
    if config.source in (LOCAL, BING) and config.source in by_source:
        target = config.source
    elif current_source and len(sources) > 1:
        others = [s for s in sources if s != current_source]
        target = others[0] if others else current_source
    else:
        target = current_source or sources[0]

    choices = by_source[target]

    # Advance within this source's own list, from where this source last left
    # off -- not from the globally last image, which belongs to the other
    # source and would resolve to -1 (restarting at the first entry).
    key = state.position(target)
    index = -1
    if key:
        for i, candidate in enumerate(choices):
            if candidate.key == key or candidate.path == key:
                index = i
                break

    return choices[(index + 1) % len(choices)]


def plan(
    config: Config,
    state: State,
    now: float | None = None,
    force: bool = False,
    offline_ok: bool = True,
) -> Plan:
    """Decide what to do on this tick. Does not touch the wallpaper."""
    timestamp = time.time() if now is None else now
    warnings: list[str] = []

    pool = build_pool(config)
    if not pool:
        return Plan(
            action="skip-empty",
            reason="no wallpapers available for the configured source",
            warnings=warnings,
        )

    if not force and not _due(state, config, timestamp):
        return Plan(action="skip-interval", reason="interval not elapsed", warnings=warnings)

    candidate = _choose(pool, config, state)
    if candidate is None:
        return Plan(action="skip-empty", reason="could not select a wallpaper", warnings=warnings)

    # Single-image rule: with nothing else to rotate to, do not churn the
    # symlink or spam notifications on every timer tick.
    if len(pool) == 1 and state.last_image in (candidate.key, candidate.path):
        return Plan(
            action="skip-single",
            reason="only one wallpaper available and it is already showing",
            warnings=warnings,
        )

    return Plan(action="apply", candidate=candidate, warnings=warnings)


def materialize(candidate: Candidate, config: Config) -> str | None:
    """Ensure the candidate exists on disk and return its path."""
    if candidate.source == BING:
        source = BingSource(
            market=config.bing_market,
            archive_days=config.bing_archive_days,
            resolution=config.bing_resolution,
        )
    else:
        source = LocalSource()
    return source.prepare(candidate)


def schedule_anchor(previous: float | None, now: float, interval_seconds: float) -> float:
    """The wall-clock slot to measure the next countdown from.

    The countdown runs on the wall clock, so it keeps ticking while the machine
    is off: shut down for three days on a 24h interval and the switch is due
    the moment you boot, with no backlog of three.

    Anchoring on the slot rather than on `now` is what stops the schedule from
    drifting. The timer only fires every 15 minutes, so an ordinary switch
    lands a few minutes after it came due; measuring from the actual moment
    would push every later switch later by the same few minutes, and a
    "daily" wallpaper would slowly slide through the afternoon. Measuring from
    the slot keeps switch times on the grid and absorbs the lateness instead.

    A gap long enough that the slot's own successor has already passed means
    the machine was off (or the timer was not running) for a whole interval.
    The missed slots collapse into the one switch being applied now, so the
    countdown restarts from `now` rather than from a slot so far behind that
    the next switch would be due immediately.
    """
    if previous is None or interval_seconds <= 0:
        return now
    elapsed = now - previous
    if elapsed < interval_seconds:
        return now  # switched ahead of schedule: this becomes the new grid
    slot = previous + int(elapsed // interval_seconds) * interval_seconds
    if slot + interval_seconds <= now:
        return now
    return slot


def schedule_due_at(state: State, interval_seconds: float) -> float | None:
    """When the next switch is due, or None when nothing has switched yet."""
    base = state.countdown_from()
    return None if base is None else base + interval_seconds


def current_path() -> str | None:
    """What the desktop is currently showing, per Omarchy's symlink."""
    link = paths.current_background_link()
    try:
        if link.is_symlink():
            return str(link.resolve())
        if link.is_file():
            return str(link)
    except OSError:
        return None
    return None
