#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Runs from ~/.config/omarchy/hooks/theme-set.d/ after `omarchy theme set`.
#
# A theme change swaps out the local background pool, so the rotation has to
# re-pick from the new theme. The switch interval is deliberately NOT reset --
# changing themes should not shorten the time until the next scheduled change.
#
# $1 = theme slug (passed by `omarchy-hook theme-set`)
set -euo pipefail

command -v live-wallpaper >/dev/null 2>&1 || exit 0

# Refresh the pool and apply one image from the new theme immediately.
live-wallpaper next --force --quiet
