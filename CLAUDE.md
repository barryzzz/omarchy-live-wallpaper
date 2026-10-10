# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`omarchy-live-wallpaper` rotates the Omarchy desktop background on a schedule,
picking from the current theme's backgrounds and/or Bing's daily image. "Live"
means *the image changes on a timer* — it is **not** a video/animated wallpaper
engine. Omarchy renders the desktop through the `omarchy.background` shell
plugin, which shows one still image; this tool just repoints that symlink.

Python 3.11+ (needs `tomllib`), no PyPI dependencies, no build step.

## Commands

```bash
python3 -m unittest discover -s tests          # all tests (~55)
python3 -m unittest tests.test_rotate -v       # one module
python3 -m unittest tests.test_rotate.AlternationTest.test_local_pool_advances_across_alternations
python3 -m unittest discover -s tests -k single_image
./install.sh                                   # copy package, install timer + hook, offer bar widget
./uninstall.sh
```

Run from a repo checkout without installing:

```bash
./bin/live-wallpaper status
./bin/live-wallpaper next --dry-run --json
```

There is no linter/formatter configured. `bin/live-wallpaper` **prefers the
installed copy** under `~/.local/share/omarchy-live-wallpaper` when it exists —
so after `install.sh`, editing the repo does not change what the CLI runs.
Test against a checkout explicitly, or reinstall.

## Architecture

The rotation decision lives in Python, not in systemd. The timer fires every
15 minutes and runs `live-wallpaper next`; the CLI then decides whether
`interval_hours` has elapsed. Consequences worth remembering:

- Editing `interval_hours` takes effect immediately — no `daemon-reload`.
- Intervals under ~15 min are rounded up to the next timer tick.
- `plan()` is pure: it never touches the wallpaper. Only `cmd_next` applies.

### Flow

```
systemd timer (15min)  ──▶  cli.cmd_next
                              ├─ rotate.plan(config, state)   → Plan(action=apply|skip-interval|skip-empty|skip-single)
                              ├─ rotate.materialize(candidate) → download Bing image if needed
                              ├─ apply.set_background(path)   → `omarchy theme bg set <path>`
                              └─ state.save(state)            → atomic write
```

`Plan.action` values are load-bearing: `skip-*` are normal, non-error outcomes
(exit 0), not failures. `skip-empty` is the only one that exits 1.

### Module map

| Module | Role |
| --- | --- |
| `live_wallpaper/paths.py` | All filesystem locations. XDG, resolved **on every call** — this is what makes tests able to redirect the whole layout via env vars. Add paths here, never inline. |
| `live_wallpaper/config.py` | TOML load + coercion. Bad values are **clamped with a warning**, never fatal. |
| `live_wallpaper/config_store.py` | Reads/writes the user's config file in place, preserving comments. Backs `config get\|set\|unset\|toggle`. |
| `live_wallpaper/state.py` | `last_switch`, `last_source`, `last_image`, per-source `positions`. Written atomically (tmpfile + `os.replace`). |
| `live_wallpaper/rotate.py` | Pool building, source alternation, interval check, single-image rule. The core logic. |
| `live_wallpaper/apply.py` | Shells out to `omarchy theme bg set` and `omarchy-notification-send`. |
| `live_wallpaper/sources/` | `Candidate` dataclass + `Source` base; `local.py` (theme dirs), `bing.py` (HPImageArchive). |
| `live_wallpaper/install.py` | Copies units + hook, `systemctl --user` enable. |

### Two invariants that are easy to break

1. **Alternation picks the source first, then advances within that source's own
   list** (`rotate._choose`). Do not "simplify" this to picking from the merged
   pool — that keeps landing on `local[0]` and the rest of a theme's images are
   never shown. This is why `State.positions` is a per-source dict rather than a
   single `last_image`. Covered by
   `AlternationTest.test_local_pool_advances_across_alternations`.
2. **A `Candidate.path` may not exist.** Bing candidates are metadata-only
   (`fetch=True`, `url` on the candidate) and are downloaded by
   `materialize()` only once selected. The URL rides on the candidate so
   downloading never triggers a second metadata request.

### The countdown runs on the wall clock

There is no in-memory countdown and no catch-up loop: `schedule_due_at()` is
`countdown_base + interval`, computed from the state file. Time powered off
therefore counts, so a machine shut down for three days on a 24h interval
switches once on boot rather than replaying three switches.

The countdown is measured from `State.countdown_base` — the *slot* the last
switch belonged to — not from `State.last_switch`, the moment it actually
happened. The timer only fires every 15 minutes, so a switch normally lands a
few minutes late; measuring from the moment would add that lateness to every
later switch and slide a "daily" wallpaper through the afternoon.
`rotate.schedule_anchor()` computes the slot. Old state files have no
`countdown_base` and fall back to `last_switch`.

A switch that is already due reads as `overdue — switching on next tick` in
`status`, never as a negative countdown. See `tests/test_schedule.py`.

### Degradation rules (deliberate, don't "fix")

- Invalid config → clamp + warn, keep rotating.
- Unreadable/corrupt state file → fresh state, don't crash the timer.
- Bing unreachable → empty Bing pool, rotation continues on local; if the
  selected Bing candidate fails to download, `cmd_next` falls back to local.
- Only one image and it's already showing → `skip-single`, no symlink rewrite,
  no notification.

## Tests

`tests/helpers.py` provides `XdgTestCase` (redirects `HOME` + all four
`XDG_*` into a temp dir, restores in `tearDown`), `write_config()`,
`make_images()`, and the `BING_RESPONSE` fixture. Every test that touches
paths should subclass it — never write to the real `~/.config`.

Network is never touched: Bing tests patch `bing_mod.urllib.request.urlopen`
with a `_FakeResponse`. New Bing behavior needs a fixture, not a live call.

## Omarchy integration points

- **Timer**: `systemd/omarchy-live-wallpaper.{service,timer}` → `~/.config/systemd/user/`.
- **Theme hook**: `hooks/omarchy-live-wallpaper.sh` → `~/.config/omarchy/hooks/theme-set.d/`.
  Runs `next --force --quiet` on `omarchy theme set`. It deliberately does
  **not** reset the interval.
- **Bar widget**: `plugin/` is a Quickshell plugin (`bar-widget` kind).
  `BarWidget.qml` is an icon button; `Panel.qml` is a click-popup. The plugin id
  in `manifest.json` is the single source of truth — `install.sh` and
  `uninstall.sh` read it from there, so renaming means editing only that file
  (plus the `moduleName` strings in the QML).

  The QML holds **no rotation state**. All mutations shell out to
  `live-wallpaper.sh` → the CLI, and status is re-read via
  `live-wallpaper status --json`. Keep it that way: the scheduled rotation must
  stay correct when the shell isn't running.

  Panel conventions, worth matching when editing it:

  - Build on the shell's kit (`PanelHero`, `PanelSectionHeader`,
    `PanelSeparator`, `ButtonGroup`, `Toggle`, `Button` from `qs.Ui`) rather
    than hand-rolling rows — they pick up theme control tokens for free.
    Read `$OMARCHY_PATH/shell/Ui/` and model on
    `$OMARCHY_PATH/shell/plugins/panels/clock/`.
  - The panel renders its own countdown from `next_due_at` (epoch seconds)
    instead of re-running the CLI each second. QML bindings do **not**
    re-evaluate on `Date.now()`, so the ticking `Timer` bumps a `tick`
    property the binding depends on. Removing that dependency freezes the
    countdown.
  - `qmllint -I "$OMARCHY_PATH/shell"` reports "not found" for every `qs.*`
    type and an inheritance cycle for `Panel` — both are tool limitations, not
    errors. Compare against a built-in panel before chasing a warning.
