// SPDX-License-Identifier: MIT
// Bar widget: shows the current wallpaper source and time until the next
// switch; clicking rotates immediately (`--force`).
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

  readonly property string scriptPath: {
    var url = String(Qt.resolvedUrl("live-wallpaper.sh"))
    return decodeURIComponent(url.replace(/^file:\/\//, ""))
  }

  readonly property string displayText: root.available
    ? (root.sourceLabel ? root.sourceLabel + " · " + root.nextDue : root.nextDue)
    : ""

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function rotate() {
    // Command is set inline rather than built in a function: Process.command
    // is mutated here, so a cached/shared array could carry over stale args.
    if (rotateProc.running) return
    rotateProc.command = [root.scriptPath, "next", "--force"]
    rotateProc.running = true
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

  visible: root.available && root.displayText !== ""
  implicitWidth: button.implicitWidth
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

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.displayText
    tooltipText: root.available
      ? "Live wallpaper · next in " + root.nextDue + " (click to switch now)"
      : "Live wallpaper CLI not installed"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.rotate()
      else if (buttonCode === Qt.MiddleButton) root.refresh()
    }
  }
}
