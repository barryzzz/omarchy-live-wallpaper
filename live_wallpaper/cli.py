# SPDX-License-Identifier: MIT
"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from . import __version__, apply as apply_mod, paths, rotate
from .config import VALID_SOURCES, Config, load as load_config
from .state import load as load_state, save as save_state

PROG = "live-wallpaper"


# --- helpers ---------------------------------------------------------------

def _fmt_remaining(seconds: float) -> str:
    if seconds <= 0:
        return "now"
    hours, rem = divmod(int(seconds), 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{int(seconds)}s"


def _countdown(config: Config, state, now: float) -> tuple[float, bool]:
    """Seconds until the next switch, and whether it is already due.

    Measured from the slot the countdown is anchored to, so a machine that was
    off for longer than the interval reads as due rather than as a large
    negative number.
    """
    due_at = rotate.schedule_due_at(state, config.interval_seconds())
    if due_at is None:
        return 0.0, True
    return due_at - now, due_at <= now


def _dry_run_note(config: Config, now: float) -> dict[str, Any]:
    state = load_state()
    remaining, due = _countdown(config, state, now)
    return {
        "current": rotate.current_path(),
        "last_switch": state.last_switch,
        "last_source": state.last_source,
        "next_due_in": _fmt_remaining(remaining),
        # Epoch seconds, so the bar panel can tick its own countdown between
        # refreshes instead of showing a string that is already stale.
        "next_due_at": rotate.schedule_due_at(state, config.interval_seconds()),
        "due": due,
        "config": config.as_dict(),
        "config_file": str(paths.config_file()),
        "state_file": str(paths.state_file()),
    }


# --- commands --------------------------------------------------------------

def cmd_next(args: argparse.Namespace, config: Config) -> int:
    """Rotate now. Honours the interval unless --force."""
    warnings: list[str] = []
    state = load_state()
    now = time.time()

    if getattr(args, "source_pin", None):
        # next-local / next-bing: a one-shot single-source pick, without
        # touching the configured source or the alternation rhythm.
        pinned = Config(**{**config.as_dict(), "source": args.source_pin})
        plan = rotate.plan(pinned, state, now=now, force=True)
        if plan.action == "apply":
            # Record under the real config so alternation stays consistent.
            plan.warnings.append(f"pinned to {args.source_pin} for this switch")
    else:
        plan = rotate.plan(config, state, now=now, force=args.force)

    if args.dry_run:
        print(json.dumps({**plan.to_dict(), **_dry_run_note(config, now)}, indent=2))
        return 0

    if plan.action == "skip-empty":
        print(f"no wallpaper available ({plan.reason})", file=sys.stderr)
        return 1

    if plan.action in ("skip-interval", "skip-single"):
        # Normal timer outcome: not an error, just nothing to do.
        print(plan.reason)
        return 0

    candidate = plan.candidate
    assert candidate is not None

    path = rotate.materialize(candidate, config)
    if not path:
        # Bing download failed; fall back to a local image if we have one.
        fallback = _local_fallback(config, state, now)
        if fallback is None:
            print(f"could not prepare {candidate.source} wallpaper", file=sys.stderr)
            return 1
        candidate, path = fallback

    try:
        apply_mod.set_background(path)
    except apply_mod.ApplyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # The countdown is anchored to the slot this switch belongs to, not to
    # `now`, so the few minutes of lateness between a switch coming due and
    # the timer firing does not accumulate into drift. See rotate.schedule_anchor.
    state.record_switch(now, rotate.schedule_anchor(state.countdown_from(), now, config.interval_seconds()))
    state.remember(candidate.source, candidate.path)
    save_state(state)

    if config.notify and not args.quiet:
        apply_mod.notify(candidate, path)

    if args.json:
        print(json.dumps({**plan.to_dict(), "path": path}, indent=2))
    else:
        print(f"{candidate.source}: {path}")
    return 0


def _local_fallback(config: Config, state, now: float):
    """After a Bing failure, try any local image (ignoring the interval)."""
    from .sources import LocalSource

    local = LocalSource().candidates()
    if not local:
        return None
    local_config = Config(**{**config.as_dict(), "source": "local"})
    plan = rotate.plan(local_config, state, now=now, force=True)
    if plan.candidate is None:
        return None
    candidate = plan.candidate
    path = rotate.materialize(candidate, local_config)
    if not path:
        return None
    return candidate, path


def cmd_status(args: argparse.Namespace, config: Config) -> int:
    state = load_state()
    now = time.time()
    payload = _dry_run_note(config, now)
    payload["warnings"] = getattr(args, "_warnings", [])
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"current      {payload['current'] or '(none)'}")
    print(f"last switch  {_ago(state.last_switch, now)}")
    print(f"last source  {state.last_source or '(none)'}")
    print(f"next due     {_next_due_line(payload, state)}")
    print(f"interval     {config.interval_hours}h")
    print(f"source       {config.source}")
    if config.source in ("bing", "both"):
        print(f"bing         market={config.bing_market} archive={config.bing_archive_days}")
    print(f"config       {payload['config_file']}")
    return 0


def _next_due_line(payload: dict[str, Any], state) -> str:
    """The countdown has already run down while the machine was off, so say
    that rather than reporting a switch that is late as if it were pending."""
    if state.last_switch is None:
        return "on first run"
    if not payload["due"]:
        return payload["next_due_in"]
    return "overdue — switching on next tick"


def _ago(timestamp: float | None, now: float) -> str:
    if timestamp is None:
        return "never"
    return _fmt_remaining(now - timestamp) + " ago"


def cmd_config(args: argparse.Namespace, config: Config) -> int:
    target = paths.config_file()

    if getattr(args, "config_action", None):
        return _config_action(args, target)

    if args.json:
        print(json.dumps({"config": config.as_dict(), "file": str(target)}, indent=2))
        return 0
    print(f"config file  {target}{'' if target.is_file() else ' (not present; using defaults)'}")
    print()
    for key, value in config.as_dict().items():
        print(f"{key:16} {value}")
    print()
    print(f"valid source values: {', '.join(VALID_SOURCES)}")
    return 0


def _config_action(args: argparse.Namespace, target) -> int:
    """`config get|set|unset|toggle` -- what the menu actions call."""
    from .config_store import DESCRIPTIONS, read_raw, set_value

    action = args.config_action
    key = args.key

    if action == "get":
        raw = read_raw(target)
        current = raw.get(key, None)
        if current is None:
            from .config import DEFAULTS
            current = DEFAULTS.get(key)
        print(_format_value(current))
        return 0

    if action == "set":
        if not key:
            print("error: config set needs a key and value", file=sys.stderr)
            return 1
        # Coerce the value the way tomllib would read it back.
        try:
            import tomllib

            value = tomllib.loads(f"value = {args.value}")["value"]
        except (tomllib.TOMLDecodeError, KeyError):
            value = args.value  # keep as string
        try:
            set_value(target, key, value)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"{key} = {_format_value(value)}")
        return 0

    if action == "unset":
        if not target.is_file():
            return 0
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        import re

        kept = [
            line
            for line in lines
            if not (match := re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)) or match.group(1) != key
        ]
        target.write_text("".join(kept), encoding="utf-8")
        return 0

    if action == "toggle":
        raw = read_raw(target)
        from .config import DEFAULTS

        current = raw.get(key, DEFAULTS.get(key))
        if not isinstance(current, bool):
            print(f"error: {key} is not a boolean", file=sys.stderr)
            return 1
        set_value(target, key, not current)
        print(f"{key} = {_format_value(not current)}")
        return 0

    return 1


def _format_value(value) -> str:
    from .config_store import _format_value

    return _format_value(value)


def cmd_pool(args: argparse.Namespace, config: Config) -> int:
    """List the current rotation pool without applying anything."""
    pool = rotate.build_pool(config)
    if args.json:
        print(
            json.dumps(
                [{"source": c.source, "path": c.path, "title": c.title} for c in pool],
                indent=2,
            )
        )
    else:
        if not pool:
            print("(empty)")
        for index, candidate in enumerate(pool):
            print(f"{index:3}  {candidate.source:5}  {candidate.path}")
    return 0


def cmd_install(args: argparse.Namespace, config: Config) -> int:
    """Print the install steps; install.sh does the real work."""
    from .install import install

    return install(quiet=args.quiet)


def cmd_uninstall(args: argparse.Namespace, config: Config) -> int:
    from .install import uninstall

    return uninstall()


# --- entry -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Automatic wallpaper rotation for Omarchy.",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    parser.add_argument(
        "-c", "--config", metavar="FILE", help="use a different config file"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_next = sub.add_parser("next", help="rotate to the next wallpaper")
    p_next.add_argument("--force", action="store_true", help="ignore the interval")
    p_next.add_argument("--dry-run", action="store_true", help="show the decision, change nothing")
    p_next.add_argument("--json", action="store_true", help="machine-readable output")
    p_next.add_argument("--quiet", action="store_true", help="suppress the notification")
    p_next.set_defaults(func=cmd_next)

    for pinned, label in (("local", "next local-theme wallpaper"), ("bing", "next Bing wallpaper")):
        p_pin = sub.add_parser(f"next-{pinned}", help=label)
        p_pin.add_argument("--json", action="store_true")
        p_pin.add_argument("--quiet", action="store_true")
        p_pin.set_defaults(func=cmd_next, source_pin=pinned, force=True, dry_run=False)

    p_status = sub.add_parser("status", help="show current wallpaper and next switch")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    # `config` shows the effective configuration; `config get|set|unset|toggle
    # [key] [value]` mutates it -- the form the menu actions call.
    p_cfg = sub.add_parser("config", help="show config, or mutate it: config get|set|unset|toggle [key] [value]")
    p_cfg.add_argument("config_action", nargs="?", choices=[None, "get", "set", "unset", "toggle"])
    p_cfg.add_argument("key", nargs="?", default=None)
    p_cfg.add_argument("value", nargs="?", default=None)
    p_cfg.add_argument("--json", action="store_true")
    p_cfg.set_defaults(func=cmd_config)

    p_pool = sub.add_parser("pool", help="list wallpapers in the rotation pool")
    p_pool.add_argument("--json", action="store_true")
    p_pool.set_defaults(func=cmd_pool)

    p_install = sub.add_parser("install", help="install the systemd timer and hooks")
    p_install.add_argument("--quiet", action="store_true")
    p_install.set_defaults(func=cmd_install)

    p_uninstall = sub.add_parser("uninstall", help="remove the timer and hooks")
    p_uninstall.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    warnings: list[str] = []
    config = load_config(args.config, warnings)
    args._warnings = warnings
    for message in warnings:
        print(f"warning: {message}", file=sys.stderr)

    return args.func(args, config)


if __name__ == "__main__":
    sys.exit(main())
