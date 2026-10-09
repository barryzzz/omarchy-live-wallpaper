// SPDX-License-Identifier: MIT
// Bar widget: landscape icon only. Left click opens the config panel below
// the icon (Panel.qml); middle click rotates immediately.
//
// All rotation state lives in the CLI, not here -- the scheduled changes are
// driven by a systemd timer, so this widget is a view plus a manual trigger
// and stays correct even when the shell is not running.

import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "lishoulin.live-wallpaper"

  // Panel lifecycle, forwarded to the Loader-loaded Panel.qml. The bar's
  // findPanelWidget resolves summon/hide by open/close/opened on this root.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item
    ? panelLoader.item.popoutSwitchClosing === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }

  function injectPanel() {
    if (!panelLoader.item) return
    panelLoader.item.bar = root.bar
    panelLoader.item.anchorItem = button
    panelLoader.item.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    active: root.opened
    iconComponent: Component {
      WallpaperIcon {
        color: button.active && button.useActiveColor ? button.activeColor : button.foreground
      }
    }
    tooltipText: "Live wallpaper · 左键配置，中键切换"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
      else if (buttonCode === Qt.MiddleButton) root.middleProc.running = true
    }
  }

  // Middle-click rotation, kept out of Panel.qml so it works with the panel
  // closed. The panel refreshes itself when it next opens.
  Process {
    id: middleProc
    command: []
    running: false
    onRunningChanged: if (running) {
      command = [String(Qt.resolvedUrl("live-wallpaper.sh")).replace("file://", ""), "next", "--force", "--quiet"]
    }
    stdout: StdioCollector { waitForEnd: true }
  }
}
