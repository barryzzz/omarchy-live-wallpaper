#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install omarchy-live-wallpaper for the current user.
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

share_dir="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-live-wallpaper"
bin_dir="${HOME}/.local/bin"
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-live-wallpaper"

echo "==> Installing omarchy-live-wallpaper"

mkdir -p "$share_dir" "$bin_dir"

# Package + entry point
cp -R "$repo_root/live_wallpaper" "$share_dir/"
cp "$repo_root/bin/live-wallpaper" "$bin_dir/live-wallpaper"
chmod +x "$bin_dir/live-wallpaper"

# Default config, without clobbering an existing one
if [[ ! -f "$config_dir/config.toml" ]]; then
  mkdir -p "$config_dir"
  cp "$repo_root/config/default.toml" "$config_dir/config.toml"
  echo "    wrote $config_dir/config.toml"
else
  echo "    kept  $config_dir/config.toml"
fi

# systemd timer + theme hook
if ! python3 - "$repo_root" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from live_wallpaper.install import install
sys.exit(install())
PY
then
  echo "error: could not install the systemd timer/hook" >&2
  exit 1
fi

# Optional bar widget
if [[ -d "$repo_root/plugin" ]] && command -v omarchy >/dev/null 2>&1; then
  echo
  read -r -p "==> Install the bar widget? [y/N] " answer
  if [[ $answer =~ ^[Yy]$ ]]; then
    plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/lishoulin.live-wallpaper"
    mkdir -p "$plugin_dir"
    cp "$repo_root/plugin/manifest.json" "$plugin_dir/"
    cp "$repo_root/plugin/BarWidget.qml" "$plugin_dir/"
    cp "$repo_root/plugin/live-wallpaper.sh" "$plugin_dir/"
    chmod +x "$plugin_dir/live-wallpaper.sh"
    omarchy plugin validate "$plugin_dir"
    omarchy-shell shell rescanPlugins
    omarchy plugin enable lishoulin.live-wallpaper --section right
    echo "    bar widget enabled"
  else
    echo "    skipped (install later with: omarchy plugin enable lishoulin.live-wallpaper)"
  fi
fi

echo
echo "==> Done. Check status with:"
echo "      live-wallpaper status"
echo "    Rotate now with:"
echo "      live-wallpaper next --force"
