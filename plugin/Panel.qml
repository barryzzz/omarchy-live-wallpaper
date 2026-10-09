// SPDX-License-Identifier: MIT
// Click popup below the bar icon: status line plus the config rows. Modeled
// on the network-speed plugin's panel: inherit the qs.Ui Panel base (IPC +
// PanelController lifecycle) and keep the content a plain Column. All
// mutations go through the CLI (live-wallpaper config set ...), so the panel
// is a thin view; state is re-read after every action.

import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
    id: root
    moduleName: "io.github.barryzzz.live-wallpaper"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null

    // Parsed status, refreshed whenever the panel opens or an action runs.
    property var status: null
    property bool busy: false

    // The base Panel's open() only flips the controller; re-read status each
    // time the panel opens so the rows reflect config changes made elsewhere.
    onOpenedChanged: if (opened) refresh()

    function switchPanel(direction) {
        if (root.bar && typeof root.bar.switchPanelFrom === "function")
            return root.bar.switchPanelFrom(root.hostWidget || root, direction)
        return false
    }

    function refresh() {
        if (!statusProc.running) statusProc.running = true
    }

    function applyStatus(raw) {
        var text = String(raw || "").trim()
        if (!text) return
        try {
            root.status = JSON.parse(text)
        } catch (e) {
            root.status = null
        }
    }

    // Run a CLI action, then re-read status so the view reflects it.
    function run(args) {
        if (actionProc.running) return
        root.busy = true
        actionProc.command = [root.scriptPath].concat(args)
        actionProc.running = true
    }

    readonly property string scriptPath: {
        var url = String(Qt.resolvedUrl("live-wallpaper.sh"))
        return decodeURIComponent(url.replace(/^file:\/\//, ""))
    }

    readonly property var intervalChoices: [
        { label: "15 分钟", value: "0.25" },
        { label: "1 小时", value: "1" },
        { label: "6 小时", value: "6" },
        { label: "12 小时", value: "12" },
        { label: "24 小时", value: "24" }
    ]

    readonly property var sourceChoices: [
        { label: "本地主题", value: "local" },
        { label: "Bing 每日", value: "bing" },
        { label: "交替", value: "both" }
    ]

    function sourceLabel(value) {
        for (var i = 0; i < sourceChoices.length; i++)
            if (sourceChoices[i].value === value) return sourceChoices[i].label
        return value || ""
    }

    function isActive(key, value) {
        if (!root.status) return false
        var current = root.status.config ? root.status.config[key] : undefined
        return String(current) === String(value)
    }

    KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(300))
        contentHeight: panel.fittedContentHeight(content.implicitHeight)

        PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onCloseRequested: root.close()
            onTabRequested: function(direction) { root.switchPanel(direction) }

            Column {
                id: content
                width: parent.width
                spacing: 0

                // ---- Header: current state ----
                Item {
                    width: parent.width
                    height: 56

                    Row {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        WallpaperIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 20
                            height: 20
                            color: Color.foreground
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2

                            Text {
                                text: root.status
                                    ? (root.status.next_due_in === "now" ? "即将切换" : "下次切换 " + root.status.next_due_in)
                                    : (root.busy ? "读取中…" : "Live Wallpaper")
                                color: Color.foreground
                                font.family: root.bar ? root.bar.fontFamily : Style.fontFamily
                                font.pixelSize: Style.font.body
                                font.bold: true
                            }

                            Text {
                                text: root.status
                                    ? "来源 " + root.sourceLabel(root.status.config ? root.status.config.source : "")
                                      + " · 间隔 " + (root.status.config ? root.status.config.interval_hours : "?") + " 小时"
                                    : ""
                                color: Color.foreground
                                opacity: 0.6
                                font.family: root.bar ? root.bar.fontFamily : Style.fontFamily
                                font.pixelSize: Style.font.caption
                            }
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: Color.foreground; opacity: 0.1 }

                // ---- Actions ----
                PanelRow {
                    width: parent.width
                    label: "立即切换壁纸"
                    glyph: "▶"
                    dimmed: root.busy
                    onClicked: { root.run(["next", "--force", "--quiet"]); root.close() }
                }

                Rectangle { width: parent.width; height: 1; color: Color.foreground; opacity: 0.1 }
                SectionLabel { width: parent.width; text: "图片来源" }
                Repeater {
                    model: root.sourceChoices
                    PanelRow {
                        width: parent.width
                        label: modelData.label
                        glyph: isActive("source", modelData.value) ? "✓" : ""
                        dimmed: root.busy
                        onClicked: root.run(["config", "set", "source", modelData.value])
                    }
                }

                Rectangle { width: parent.width; height: 1; color: Color.foreground; opacity: 0.1 }
                SectionLabel { width: parent.width; text: "切换间隔" }
                Repeater {
                    model: root.intervalChoices
                    PanelRow {
                        width: parent.width
                        label: modelData.label
                        glyph: isActive("interval_hours", modelData.value) ? "✓" : ""
                        dimmed: root.busy
                        onClicked: root.run(["config", "set", "interval_hours", modelData.value])
                    }
                }

                Rectangle { width: parent.width; height: 1; color: Color.foreground; opacity: 0.1 }
                PanelRow {
                    width: parent.width
                    label: "切换通知"
                    glyph: isActive("notify", true) || isActive("notify", "true") ? "✓" : ""
                    dimmed: root.busy
                    onClicked: root.run(["config", "toggle", "notify"])
                }

                Rectangle { width: parent.width; height: 1; color: Color.foreground; opacity: 0.1 }
                PanelRow {
                    width: parent.width
                    label: "编辑配置文件…"
                    glyph: "⌘"
                    onClicked: {
                        Quickshell.execDetached(["xdg-open",
                            Quickshell.env("HOME") + "/.config/omarchy-live-wallpaper/config.toml"])
                        root.close()
                    }
                }
            }
        }
    }

    Process {
        id: statusProc
        command: [root.scriptPath, "status", "--json"]
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                root.applyStatus(text)
                root.busy = false
            }
        }
    }

    Process {
        id: actionProc
        command: []
        running: false
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: root.refresh()
        }
    }
}
