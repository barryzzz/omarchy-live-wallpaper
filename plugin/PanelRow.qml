// SPDX-License-Identifier: MIT
// One clickable row in the config panel.

import QtQuick
import qs.Commons
import qs.Ui

Item {
    id: row

    property string label: ""
    property string glyph: ""          // right-aligned ✓ or action hint
    property bool dimmed: false
    signal clicked()

    implicitHeight: 36
    implicitWidth: parent ? parent.width : 200

    readonly property color fg: (row.parent && row.parent.parent && row.parent.parent.foreground)
        ? row.parent.parent.foreground()
        : String(Color.foreground)

    Rectangle {
        anchors.fill: parent
        color: mouse.containsMouse ? fg : "transparent"
        opacity: mouse.containsMouse ? 0.08 : 1
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 8

        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - marker.width - 16
            text: row.label
            color: row.fg
            opacity: row.dimmed ? 0.5 : 1
            font.pixelSize: Style.font.body
            font.family: Style.fontFamily
            elide: Text.ElideRight
        }

        Text {
            id: marker
            anchors.verticalCenter: parent.verticalCenter
            text: row.glyph
            visible: row.glyph !== ""
            color: row.fg
            opacity: row.dimmed ? 0.5 : 0.85
            font.pixelSize: Style.font.body
            font.family: Style.fontFamily
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: row.clicked()
    }
}
