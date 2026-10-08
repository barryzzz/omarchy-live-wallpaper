# SPDX-License-Identifier: MIT
"""Reading and writing the user's config file.

The writer handles exactly the shape this tool writes: `key = value` lines
with optional comments and blank lines. Values are TOML strings, floats,
ints, or booleans. It rewrites the file instead of pretty-printing a whole
document, so comments the user added survive a `config set`.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from .config import VALID_RESOLUTIONS, VALID_SOURCES

_LINE = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<assign>\s*=\s*)(?P<value>[^#]*?)(?P<comment>\s*#.*)?$"
)

# Order the menu writes keys, so a fresh file reads the same as default.toml.
KEY_ORDER = [
    "interval_hours",
    "source",
    "bing_market",
    "bing_archive_days",
    "bing_resolution",
    "notify",
]

DESCRIPTIONS = {
    "interval_hours": "hours between switches",
    "source": "local | bing | both",
    "bing_market": "Bing region, e.g. zh-CN",
    "bing_archive_days": "days of Bing history in the pool",
    "bing_resolution": "Bing image size",
    "notify": "desktop notification on switch",
}


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def read_raw(path: Path) -> dict:
    """Minimal TOML subset reader matching what we write. Falls back to
    tomllib for anything else, so hand-edited files still work."""
    import tomllib

    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def set_value(path: Path, key: str, value) -> Path:
    """Set `key` to `value`, preserving comments on the edited line."""
    if key not in DESCRIPTIONS:
        raise ValueError(f"unknown config key '{key}'")

    if key == "source" and str(value) not in VALID_SOURCES:
        raise ValueError(f"source must be one of: {', '.join(VALID_SOURCES)}")
    if key == "bing_resolution" and str(value) not in VALID_RESOLUTIONS:
        raise ValueError(f"bing_resolution must be one of: {', '.join(VALID_RESOLUTIONS)}")

    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []

    replaced = False
    for i, line in enumerate(lines):
        match = _LINE.match(line.rstrip("\n"))
        if match and match.group("key") == key:
            indent, assign, comment = match.group("indent"), match.group("assign"), match.group("comment")
            lines[i] = f"{indent}{key}{assign}{_format_value(value)}{comment or ''}\n"
            replaced = True
            break

    if not replaced:
        # Insert in canonical order, before the first key that sorts after it.
        insert_at = len(lines)
        for i, line in enumerate(lines):
            match = _LINE.match(line.rstrip("\n"))
            if match and match.group("key") in KEY_ORDER:
                if KEY_ORDER.index(match.group("key")) > KEY_ORDER.index(key):
                    insert_at = i
                    break
        lines.insert(insert_at, f"{key} = {_format_value(value)}\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".cfg-", suffix=".tmp")
    import os

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
