# SPDX-License-Identifier: MIT
"""Rotation state: what we last applied, and when.

Kept small and durable. Written atomically so an interrupted run never leaves
a half-written file behind -- a corrupt state file would otherwise reset the
rotation on every tick.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import paths

STATE_VERSION = 1


@dataclass
class State:
    last_switch: float | None = None   # epoch seconds
    last_source: str | None = None     # "local" | "bing"
    last_image: str | None = None      # absolute path as string

    # Last key served from each source. Alternation jumps between sources, so
    # a single "last image" cannot express where each source's own list left
    # off -- without this, every return to a source restarts at its first
    # image and the rest are never shown.
    positions: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.positions is None:
            self.positions = {}
            if self.last_source and self.last_image:
                self.positions[self.last_source] = self.last_image

    def remember(self, source: str, key: str) -> None:
        self.last_source = source
        self.last_image = key
        self.positions[source] = key

    def position(self, source: str) -> str | None:
        return self.positions.get(source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "last_switch": self.last_switch,
            "last_source": self.last_source,
            "last_image": self.last_image,
            "positions": dict(self.positions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "State":
        if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
            return cls()
        last_switch = data.get("last_switch")
        try:
            last_switch = float(last_switch) if last_switch is not None else None
        except (TypeError, ValueError):
            last_switch = None
        image = data.get("last_image")
        positions = data.get("positions")
        if not isinstance(positions, dict):
            positions = {}
        else:
            positions = {str(k): str(v) for k, v in positions.items() if v}
        return cls(
            last_switch=last_switch,
            last_source=data.get("last_source") or None,
            last_image=str(image) if image else None,
            positions=positions,
        )


def load(path: Path | None = None) -> State:
    target = paths.state_file() if path is None else Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            return State.from_dict(json.load(handle))
    except FileNotFoundError:
        return State()
    except (OSError, json.JSONDecodeError):
        # Unreadable or corrupt: start fresh rather than crashing the timer.
        return State()


def save(state: State, path: Path | None = None) -> Path:
    target = paths.state_file() if path is None else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target
