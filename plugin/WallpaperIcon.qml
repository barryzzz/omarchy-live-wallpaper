// SPDX-License-Identifier: MIT
// Landscape icon (sun over mountains) drawn as vectors, in the spirit of
// omarchy-days' CalendarIcon. Drawn rather than using a Nerd Font glyph:
// glyph coverage varies by installed font, and a missing glyph renders as
// blank space in the bar.

import QtQuick
import QtQuick.Shapes

Item {
    id: root

    property color color: "white"
    readonly property real iconSize: Math.min(width, height)

    Shape {
        x: (root.width - root.iconSize) / 2
        y: (root.height - root.iconSize) / 2
        width: 1024
        height: 1024
        preferredRendererType: Shape.CurveRenderer
        transform: Scale {
            xScale: root.iconSize / 1024
            yScale: root.iconSize / 1024
        }

        // Sun (circle, four cubic segments, center 700,388 r=128).
        ShapePath {
            fillColor: root.color
            strokeWidth: -1

            PathMove { x: 700; y: 260 }
            PathCubic { control1X: 771; control1Y: 260; control2X: 828; control2Y: 317; x: 828; y: 388 }
            PathCubic { control1X: 828; control1Y: 459; control2X: 771; control2Y: 516; x: 700; y: 516 }
            PathCubic { control1X: 629; control1Y: 516; control2X: 572; control2Y: 459; x: 572; y: 388 }
            PathCubic { control1X: 572; control1Y: 317; control2X: 629; control2Y: 260; x: 700; y: 260 }
        }

        // Mountains: one path, back ridge then front ridge, filled to baseline.
        ShapePath {
            fillColor: root.color
            fillRule: ShapePath.WindingFill
            strokeWidth: 0

            PathSvg {
                path: "M64 832 L64 768 L340 420 L520 650 L640 500 L960 768 L960 832 Z"
            }
        }
    }
}
