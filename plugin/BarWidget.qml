// SPDX-License-Identifier: MIT
// Bar widget: landscape icon + countdown. Left click opens the wallpaper
// config menu (registered in omarchy-menu.jsonc), middle click rotates.
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

  readonly property string displayText: root.available && root.nextDue !== ""
    ? root.nextDue
    : ""

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function openMenu() {
    if (root.bar) root.bar.run("omarchy menu toggle wallpaper")
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
      tooltipText: root.available
        ? "Live wallpaper (" + root.sourceLabel + ") · next in " + root.nextDue
          + "\nLeft: menu · Middle: switch now"
        : "Live wallpaper CLI not installed"
      onPressed: function(buttonCode) {
        if (buttonCode === Qt.LeftButton) root.openMenu()
        else if (buttonCode === Qt.MiddleButton) {
          if (rotateProc.running) return
          rotateProc.command = [root.scriptPath, "next", "--force"]
          rotateProc.running = true
        }
      }
    }

    // The countdown rides on the same click surface: a MouseArea over the
    // whole row forwards to the button's handler, so clicking the text does
    // exactly what clicking the icon does.
    Item {
      width: countText.visible ? countText.implicitWidth : 0
      height: button.height
      anchors.verticalCenter: parent.verticalCenter

      Text {
        id: countText
        anchors.verticalCenter: parent.verticalCenter
        visible: root.displayText !== ""
        text: root.displayText
        color: button.foreground
        font.family: button.bar ? button.bar.fontFamily : Style.fontFamily
        font.pixelSize: button.fontSize
      }

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
          if (mouse.button === Qt.LeftButton) root.openMenu()
          else if (mouse.button === Qt.MiddleButton) {
            if (rotateProc.running) return
            rotateProc.command = [root.scriptPath, "next", "--force"]
            rotateProc.running = true
          }
        }
      }
    }
  }
}
