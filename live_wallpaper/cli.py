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


def _dry_run_note(config: Config, now: float) -> dict[str, Any]:
    state = load_state()
    remaining = 0.0
    if state.last_switch is not None:
        remaining = max(0.0, config.interval_seconds() - (now - state.last_switch))
    return {
        "current": rotate.current_path(),
        "last_switch": state.last_switch,
        "last_source": state.last_source,
        "next_due_in": _fmt_remaining(remaining),
        "due": remaining <= 0,
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

    state.last_switch = now
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
    print(f"next due     {payload['next_due_in']}")
    print(f"interval     {config.interval_hours}h")
    print(f"source       {config.source}")
    if config.source in ("bing", "both"):
        print(f"bing         market={config.bing_market} archive={config.bing_archive_days}")
    print(f"config       {payload['config_file']}")
    return 0


def _ago(timestamp: float | None, now: float) -> str:
    if timestamp is None:
        return "never"
    return _fmt_remaining(now - timestamp) + " ago"


def cmd_config(args: argparse.Namespace, config: Config) -> int:
    target = paths.config_file()
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

    p_status = sub.add_parser("status", help="show current wallpaper and next switch")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_config = sub.add_parser("config", help="show the effective configuration")
    p_config.add_argument("--json", action="store_true")
    p_config.set_defaults(func=cmd_config)

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
