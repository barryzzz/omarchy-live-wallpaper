// SPDX-License-Identifier: MIT
// Bar widget: an image icon plus the time until the next switch. Left click
// rotates immediately (`--force`), right click opens the config file.
//
// All rotation state lives in the CLI, not here -- the scheduled changes are
// driven by a systemd timer, so this widget is a view plus a manual trigger
// and stays correct even when the shell is not running.

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "lishoulin.live-wallpaper"

  property string sourceLabel: ""
  property string nextDue: ""
  property bool available: false

  // Nerd Font picture glyph; the bar's monospace stack (JetBrainsMono NF)
  // renders it, same as the network/audio widgets' icons.
  readonly property string scriptPath: {
    var url = String(Qt.resolvedUrl("live-wallpaper.sh"))
    return decodeURIComponent(url.replace(/^file:\/\//, ""))
  }

  readonly property string displayText: root.available && root.nextDue !== ""
    ? root.nextDue
    : ""

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function rotate() {
    if (rotateProc.running) return
    rotateProc.command = [root.scriptPath, "next", "--force"]
    rotateProc.running = true
  }

  function openConfig() {
    Quickshell.execDetached([
      "xdg-open",
      Quickshell.env("HOME") + "/.config/omarchy-live-wallpaper/config.toml"
    ])
  }

  function command(args) {
    return [root.scriptPath].concat(args)
  }

  function applyStatus(raw) {
    var text = String(raw || "").trim()
    if (!text) return
    var data
    try {
      data = JSON.parse(text)
    } catch (e) {
      root.available = false
      return
    }
    root.available = true
    var source = data.source === "both" ? "auto"
      : data.source === "bing" ? "Bing"
      : data.source === "local" ? "local"
      : ""
    root.sourceLabel = source
    root.nextDue = data.next_due_in === "now" ? "due" : (data.next_due_in || "")
  }

  // Stay visible once the icon is up even if a later status poll fails --
  // blinking out would look like a bug. The tooltip carries the state.
  visible: true
  implicitWidth: row.implicitWidth
  implicitHeight: button.implicitHeight

  Component.onCompleted: root.refresh()

  Process {
    id: statusProc
    command: root.command(["status", "--json"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyStatus(text)
    }
  }

  Process {
    id: rotateProc
    command: [root.scriptPath, "next", "--force"]
    running: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.refresh()
    }
  }

  Timer {
    interval: 60000
    repeat: true
    running: true
    onTriggered: root.refresh()
  }

  Row {
    id: row
    anchors.verticalCenter: parent.verticalCenter

    BarIconButton {
      id: button
      bar: root.bar
      iconComponent: Component {
        WallpaperIcon {
          color: button.active && button.useActiveColor ? button.activeColor : button.foreground
        }
      }
      active: rotateProc.running
      tooltipText: root.available
        ? "Live wallpaper (" + root.sourceLabel + ") · next in " + root.nextDue
          + "\nLeft: switch now · Right: edit config"
        : "Live wallpaper CLI not installed"
      onPressed: function(buttonCode) {
        if (buttonCode === Qt.LeftButton) root.rotate()
        else if (buttonCode === Qt.RightButton) root.openConfig()
        else if (buttonCode === Qt.MiddleButton) root.refresh()
      }
    }

    Text {
      anchors.verticalCenter: parent.verticalCenter
      visible: root.displayText !== ""
      text: root.displayText
      color: button.foreground
      font.family: button.bar ? button.bar.fontFamily : Style.fontFamily
      font.pixelSize: button.fontSize
    }
  }
}
