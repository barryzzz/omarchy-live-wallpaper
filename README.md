# omarchy-live-wallpaper

Automatic wallpaper rotation for [Omarchy](https://omarchy.org/): switches the
desktop background on a schedule, from the current theme's backgrounds and/or
Bing's daily image.

> **What "live" means here.** Omarchy renders the desktop through the
> `omarchy.background` shell plugin, which displays a single still image. This
> tool rotates that image on a timer. It is *not* a video/animated wallpaper
> engine — if you want moving wallpapers you need a compositor-level renderer
> such as `swww` or `mpvpaper`, which Omarchy does not ship with.

## Install

```bash
./install.sh
```

That copies the package to `~/.local/share/omarchy-live-wallpaper`, puts
`live-wallpaper` on `~/.local/bin`, installs and enables a systemd user timer,
and registers a `theme-set` hook. It offers to install the bar widget too
(answer `y`, or enable it later yourself).

Requirements: Python 3.11+ (for `tomllib`) and `systemd --user`. No PyPI
dependencies.

```bash
./uninstall.sh   # removes the timer, hook, and installed files
```

## Usage

```bash
live-wallpaper status              # current wallpaper, next switch, config in effect
live-wallpaper next                # rotate if the interval has elapsed (what the timer runs)
live-wallpaper next --force        # rotate now, ignoring the interval
live-wallpaper next --dry-run      # show the decision without changing anything
live-wallpaper pool                # list the images in the rotation pool
live-wallpaper config              # show effective config and its file path
```

Status output:

```
current      /home/…/backgrounds/1-quattro.jpg
last switch  2h 14m ago
last source  local
next due     21h 45m
interval     24.0h
source       both
```

## Configuration

`~/.config/omarchy-live-wallpaper/config.toml` (installed from
`config/default.toml`). Every key is optional.

```toml
interval_hours    = 24      # hours between switches; fractions allowed (0.5 = 30m)
source            = "both"  # "local" | "bing" | "both"
bing_market       = "zh-CN"
bing_archive_days = 1       # days of Bing archive in the pool (max 16)
bing_resolution   = "UHD"   # UHD | 1920x1080 | 1366x768 | 1024x768
notify            = true
```

Invalid values are clamped and reported as warnings rather than failing, so a
typo never stops the rotation.

### Sources

- **local** — the current theme's backgrounds, the same directories
  `omarchy theme bg next` scans:
  `~/.local/state/omarchy/current/theme/backgrounds/` and
  `~/.config/omarchy/backgrounds/<theme>/`. Because one is theme-scoped,
  changing the theme changes the pool automatically.
- **bing** — Bing's daily image, downloaded on selection and cached under
  `~/.cache/omarchy-live-wallpaper/bing/`. Re-selecting a day never
  re-downloads.
- **both** — alternate: local, then Bing, then the next local image, and so on.
  Each source advances through its own list independently.

`bing_archive_days = 1` (the default) keeps only today's image, which pairs
with the 24-hour interval to give one fresh wallpaper per day. Raise it if you
set a short interval and want more images to rotate through.

### Single wallpaper

When only one image is available and it is already displayed, nothing happens:
the symlink is not rewritten and no notification is sent. This keeps a
one-image setup from churning on every timer tick. The first run still applies
it, and a different wallpaper showing on the desktop is always replaced.

## How scheduling works

A systemd user timer fires **every 15 minutes** and runs
`live-wallpaper next`. The CLI then decides whether `interval_hours` has
elapsed since the last switch. Two consequences:

- Changing `interval_hours` takes effect immediately — no `daemon-reload`, no
  unit edit.
- Intervals shorter than 15 minutes are rounded up to the next timer tick, so
  the effective minimum is ~15 minutes.

### Powered off or suspended

The countdown runs on the **wall clock**, not on timer ticks, so it keeps going
while the machine is down. Shut down for three days on a 24-hour interval and
the switch is due the moment you boot — one switch, not a backlog of three.
`OnBootSec=2min` covers that first switch.

While a switch is overdue the status reads `overdue — switching on next tick`
rather than reporting a negative countdown.

To stop the schedule sliding later over time, the countdown is measured from
the *slot* the last switch belonged to rather than from the moment it
happened. The timer only fires every 15 minutes, so a switch normally lands a
few minutes after it came due; measuring from that moment would add those few
minutes to every later switch, and a "daily" wallpaper would drift through the
afternoon within a month. On the grid it stays put.

```bash
systemctl --user list-timers omarchy-live-wallpaper.timer
journalctl --user -u omarchy-live-wallpaper.service
```

## Theme changes

`hooks/omarchy-live-wallpaper.sh` is installed into
`~/.config/omarchy/hooks/theme-set.d/`. On `omarchy theme set <theme>` it
re-picks from the new theme's backgrounds and applies one immediately. The
switch interval is deliberately **not** reset, so changing themes does not
shorten the wait until the next scheduled change.

## Bar widget (optional)

An icon-only button in the bar. Left click opens a popup panel right below the
icon: a status hero, a live countdown to the next switch (ticking once a
second), a switch-now button, and the settings — image source (local / Bing
daily / alternate), switch interval, and notifications. Middle click rotates
immediately.

Everything is built on the shell's own control kit, so it follows your theme.
The panel holds no rotation state: every change is a `live-wallpaper config`
call, and status is re-read afterwards.

The time until the next switch lives inside the panel, not in the bar.

```bash
omarchy plugin enable io.github.barryzzz.live-wallpaper --section right
```

## Development

```bash
python3 -m unittest discover -s tests
```

Tests run against a redirected XDG layout and never touch the network; Bing
parsing is covered by fixtures.

## Layout

```
live_wallpaper/
├── cli.py              # commands
├── config.py           # TOML loading, defaults, clamping
├── state.py            # rotation state (atomic writes)
├── rotate.py           # pool building, source alternation, interval decision
├── apply.py            # hand the image to omarchy, notify
├── install.py          # systemd units + hook
└── sources/{local,bing}.py
```

## License

MIT
