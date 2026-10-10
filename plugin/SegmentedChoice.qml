// SPDX-License-Identifier: MIT
// A single row of chips that fills its parent width instead of overflowing
// it. The kit's ButtonGroup is a Row with no wrapping and no width
// constraint, so a long set of options ("15 分钟 / 1 小时 / 6 小时 / 12 小时
// / 24 小时") simply runs past the panel's right edge. This control computes
// each chip's width from the space actually available, so the whole set is
// always inside the panel.
//
// States reuse the same Style tokens as Button, so it stays in theme.

import QtQuick
import qs.Commons

Row {
    id: root

    property var options: []            // [{ value, label }]
    property string value: ""
    property color foreground: Color.foreground
    property color accent: Color.accent
    property string fontFamily: Style.font.family
    property real fontSize: Style.font.caption
    property int chipHeight: Style.spacing.controlHeight

    signal changed(string value)

    function optionValue(o) {
        return (o && typeof o === "object") ? String(o.value) : String(o)
    }
    function optionLabel(o) {
        return (o && typeof o === "object" && o.label !== undefined) ? String(o.label) : String(o)
    }

    // Equal-width chips. Whatever space is left after the inter-chip gaps is
    // split evenly, so the row always ends exactly at the parent's right
    // edge and never beyond it.
    readonly property real chipWidth: {
        var n = options.length
        if (n <= 0) return 0
        return Math.max(Style.space(34), Math.floor((width - spacing * (n - 1)) / n))
    }

    spacing: Style.spacing.xs

    Repeater {
        model: root.options

        delegate: Rectangle {
            id: chip
            required property var modelData

            readonly property string chipValue: root.optionValue(modelData)
            readonly property bool selected: chipValue === String(root.value)

            width: root.chipWidth
            height: root.chipHeight
            radius: Style.cornerRadius
            clip: true

            color: hover.containsMouse ? Style.hoverFillFor(root.foreground, root.accent)
                : (selected ? Style.selectedFillFor(root.foreground, root.accent) : "transparent")

            border.width: Style.spacing.hairline
            border.color: selected
                ? Style.selectedStateColor(root.foreground, root.accent)
                : Style.normalBorderFor(root.foreground, root.accent)

            Behavior on color { ColorAnimation { duration: 80 } }

            Text {
                anchors.centerIn: parent
                textFormat: Text.PlainText
                text: root.optionLabel(chip.modelData)
                color: chip.selected ? Style.selectedStateColor(root.foreground, root.accent) : root.foreground
                font.family: root.fontFamily
                font.pixelSize: root.fontSize
                font.bold: chip.selected
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }

            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.changed(chip.chipValue)
            }
        }
    }
}
