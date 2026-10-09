#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Remove the timer, hook, and installed files. Downloaded wallpapers and the
# user config are kept.
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

echo "==> Uninstalling omarchy-live-wallpaper"

python3 - "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from live_wallpaper.install import uninstall
sys.exit(uninstall())
PY

rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-live-wallpaper"
rm -f "${HOME}/.local/bin/live-wallpaper"

# Remove every installed copy of the bar widget: the current plugin id (from
# manifest.json) plus the pre-rename id, in case an older install is still
# around. ids that are not installed on disk are simply skipped.
plugin_ids=()
if [[ -f "$repo_root/plugin/manifest.json" ]]; then
  plugin_ids+=("$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' \
    "$repo_root/plugin/manifest.json")")
fi
plugin_ids+=("lishoulin.live-wallpaper")

for plugin_id in "${plugin_ids[@]}"; do
  plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$plugin_id"
  [[ -d "$plugin_dir" ]] || continue
  if command -v omarchy >/dev/null 2>&1; then
    omarchy plugin disable "$plugin_id" >/dev/null 2>&1 || true
  fi
  rm -rf "$plugin_dir"
  echo "    removed bar widget $plugin_id"
done

echo "==> Done. Config kept at ${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-live-wallpaper/config.toml"
