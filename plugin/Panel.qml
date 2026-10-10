// SPDX-License-Identifier: MIT
// Click popup below the bar icon: a status hero, then the settings. Built on
// the shell's own kit (PanelHero / PanelSectionHeader / PanelSeparator /
// ButtonGroup / Toggle) so it picks up the theme's control tokens instead of
// hand-rolling them.
//
// All state lives in the CLI, not here -- the scheduled rotation is driven by
// a systemd timer, so this panel is a view plus a manual trigger and stays
// correct even when the shell is not running. Every mutation goes through
// `live-wallpaper config ...`, and status is re-read after each one.

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

    // Guarded so the panel renders before the bar is injected (the bar-widget
    // contract instantiates it bare).
    //
    // `bar.foreground`, not `bar.barForeground`: the latter is the
    // transparent-bar variant, which on a transparent bar is animated and can
    // invert against the panel's own background -- text on it turns into mush.
    // Every built-in panel binds `bar.foreground` for the same reason.
    readonly property color contentForeground: bar ? bar.foreground : Color.foreground
    readonly property string contentFontFamily: bar && bar.fontFamily ? bar.fontFamily : Style.font.family

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

    // Drives the countdown's re-evaluation. `Date.now()` is not observable,
    // so a binding on it alone would never re-run -- this ticks once a second
    // while the panel is open and gives the binding something to depend on.
    property int tick: 0

    Timer {
        interval: 1000
        running: root.opened
        repeat: true
        onTriggered: root.tick++
    }

    readonly property real secondsUntilSwitch: {
        // Referenced so the countdown re-evaluates on each tick.
        var unused = root.tick
        if (!root.status || root.status.next_due_at === null || root.status.next_due_at === undefined)
            return -1
        var at = Number(root.status.next_due_at)
        if (!isFinite(at)) return -1
        return at - Date.now() / 1000
    }

    readonly property bool neverSwitched: {
        if (!root.status) return true
        return root.status.last_switch === null || root.status.last_switch === undefined
    }

    function countdownLabel() {
        if (!root.status) return "读取中…"
        if (root.neverSwitched) return "尚未切换"
        if (root.secondsUntilSwitch < 0) return "已到期，等待切换"
        var total = Math.max(0, Math.floor(root.secondsUntilSwitch))
        var hours = Math.floor(total / 3600)
        var minutes = Math.floor((total % 3600) / 60)
        var seconds = total % 60
        if (hours > 0) return "下次切换 " + hours + " 小时 " + minutes + " 分"
        if (minutes > 0) return "下次切换 " + minutes + " 分 " + seconds + " 秒"
        return "下次切换 " + seconds + " 秒"
    }

    // Right-aligned summary on the hero's title row: what is in the pool and
    // how often it turns over.
    function configPill() {
        if (!root.status || !root.status.config) return ""
        var c = root.status.config
        return sourceLabel(c.source) + " · " + intervalLabel(c.interval_hours)
    }

    function metaLine() {
        if (!root.status || !root.status.config) return ""
        return "图片来源与切换间隔"
    }

    // Chips carry short numeric labels ("15m", "6h") -- the full "15 分钟"
    // wording is what overflowed the panel; the section header already says
    // these are the switch intervals. The hero pill and the detailed label
    // still use the full wording below.
    readonly property var intervalChoices: [
        { value: "0.25", label: "15m" },
        { value: "1", label: "1h" },
        { value: "6", label: "6h" },
        { value: "12", label: "12h" },
        { value: "24", label: "24h" }
    ]

    readonly property var intervalFullChoices: [
        { value: "0.25", label: "15 分钟" },
        { value: "1", label: "1 小时" },
        { value: "6", label: "6 小时" },
        { value: "12", label: "12 小时" },
        { value: "24", label: "24 小时" }
    ]

    readonly property var sourceChoices: [
        { value: "local", label: "本地主题" },
        { value: "bing", label: "Bing 每日" },
        { value: "both", label: "交替" }
    ]

    function intervalLabel(value) {
        for (var i = 0; i < intervalFullChoices.length; i++)
            // The config carries a number; the CLI writes it bare, so compare
            // numerically rather than as strings.
            if (Number(intervalFullChoices[i].value) === Number(value)) return intervalFullChoices[i].label
        return Number(value) + " 小时"
    }

    function sourceLabel(value) {
        for (var i = 0; i < sourceChoices.length; i++)
            if (sourceChoices[i].value === String(value)) return sourceChoices[i].label
        return String(value || "")
    }

    function currentConfigValue(key) {
        if (!root.status || !root.status.config) return ""
        var v = root.status.config[key]
        return v === null || v === undefined ? "" : String(v)
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

                // ---- Hero: what is showing and when it changes ----
                Item {
                    width: parent.width
                    implicitHeight: hero.implicitHeight + Style.space(28)

                    PanelHero {
                        id: hero
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Style.space(4)
                        anchors.rightMargin: Style.space(4)
                        anchors.verticalCenter: parent.verticalCenter

                        iconComponent: Component {
                            WallpaperIcon {
                                color: root.contentForeground
                                width: Style.space(26)
                                height: Style.space(26)
                            }
                        }
                        iconSize: Style.space(26)

                        title: "Live Wallpaper"
                        meta: root.metaLine()
                        detail: root.configPill()

                        foreground: root.contentForeground
                        fontFamily: root.contentFontFamily
                    }
                }

                // ---- Countdown. Ticks on its own so the panel does not have
                //      to re-run the CLI to stay honest. ----
                Item {
                    width: parent.width
                    implicitHeight: countdownText.implicitHeight + Style.space(18)

                    Text {
                        id: countdownText
                        textFormat: Text.PlainText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Style.space(20)
                        anchors.rightMargin: Style.space(20)
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.countdownLabel()
                        // Overdue is called out by the wording, not by a
                        // different colour: the theme's accent is not
                        // guaranteed to contrast with the panel background,
                        // and a low-contrast accent here is unreadable.
                        color: root.contentForeground
                        opacity: (root.secondsUntilSwitch < 0 && !root.neverSwitched) ? 1 : 0.85
                        font.family: root.contentFontFamily
                        font.pixelSize: Style.font.body
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }

                PanelSeparator { foreground: root.contentForeground }

                // ---- Actions ----
                Item {
                    width: parent.width
                    implicitHeight: switchButton.implicitHeight + Style.space(20)

                    Button {
                        id: switchButton
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Style.space(18)
                        anchors.rightMargin: Style.space(18)
                        anchors.verticalCenter: parent.verticalCenter

                        text: "立即切换壁纸"
                        iconText: ""
                        bordered: true
                        focusable: true
                        foreground: root.contentForeground
                        fontFamily: root.contentFontFamily
                        enabled: !root.busy
                        onClicked: {
                            root.run(["next", "--force", "--quiet"])
                            root.close()
                        }
                    }
                }

                PanelSeparator { foreground: root.contentForeground }

                // ---- Source ----
                Column {
                    width: parent.width
                    spacing: Style.space(8)
                    topPadding: Style.space(6)
                    bottomPadding: Style.space(6)

                    PanelSectionHeader {
                        text: "图片来源"
                        foreground: root.contentForeground
                        fontFamily: root.contentFontFamily
                        leftPadding: Style.space(20)
                    }

                    Item {
                        width: parent.width
                        implicitHeight: sourceGroup.implicitHeight

                        SegmentedChoice {
                            id: sourceGroup
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: Style.space(18)
                            anchors.rightMargin: Style.space(18)

                            options: root.sourceChoices
                            value: root.currentConfigValue("source")
                            foreground: root.contentForeground
                            fontFamily: root.contentFontFamily
                            onChanged: function(v) { root.run(["config", "set", "source", v]) }
                        }
                    }
                }

                PanelSeparator { foreground: root.contentForeground }

                // ---- Interval ----
                Column {
                    width: parent.width
                    spacing: Style.space(8)
                    topPadding: Style.space(6)
                    bottomPadding: Style.space(6)

                    PanelSectionHeader {
                        text: "切换间隔"
                        foreground: root.contentForeground
                        fontFamily: root.contentFontFamily
                        leftPadding: Style.space(20)
                    }

                    Item {
                        width: parent.width
                        implicitHeight: intervalGroup.implicitHeight

                        SegmentedChoice {
                            id: intervalGroup
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: Style.space(18)
                            anchors.rightMargin: Style.space(18)

                            options: root.intervalChoices
                            value: root.currentConfigValue("interval_hours")
                            foreground: root.contentForeground
                            fontFamily: root.contentFontFamily
                            onChanged: function(v) { root.run(["config", "set", "interval_hours", v]) }
                        }
                    }
                }

                PanelSeparator { foreground: root.contentForeground }

                // ---- Notifications ----
                Item {
                    width: parent.width
                    implicitHeight: notifyToggle.implicitHeight + Style.space(12)

                    Toggle {
                        id: notifyToggle
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Style.space(18)
                        anchors.rightMargin: Style.space(18)
                        anchors.verticalCenter: parent.verticalCenter

                        label: "切换通知"
                        checked: root.currentConfigValue("notify") === "true"
                        foreground: root.contentForeground
                        fontFamily: root.contentFontFamily
                        onClicked: root.run(["config", "toggle", "notify"])
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
