#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Remove the timer, hook, and installed files. Downloaded wallpapers and the
# user config are kept.
set -euo pipefail

echo "==> Uninstalling omarchy-live-wallpaper"

python3 - "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from live_wallpaper.install import uninstall
sys.exit(uninstall())
PY

rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-live-wallpaper"
rm -f "${HOME}/.local/bin/live-wallpaper"

plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/lishoulin.live-wallpaper"
if [[ -d "$plugin_dir" ]] && command -v omarchy >/dev/null 2>&1; then
  omarchy plugin disable lishoulin.live-wallpaper >/dev/null 2>&1 || true
  rm -rf "$plugin_dir"
  echo "    removed bar widget"
fi

echo "==> Done. Config kept at ${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-live-wallpaper/config.toml"
