#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Resolver used by the bar widget. Kept separate from the QML so the widget
# works with either a repo checkout or an install under ~/.local/bin.
set -euo pipefail

if [[ -x "${HOME}/.local/bin/live-wallpaper" ]]; then
  exec "${HOME}/.local/bin/live-wallpaper" "$@"
fi

if command -v live-wallpaper >/dev/null 2>&1; then
  exec live-wallpaper "$@"
fi

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec "$repo_root/bin/live-wallpaper" "$@"
