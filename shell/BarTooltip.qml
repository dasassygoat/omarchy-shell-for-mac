import QtQuick
import qs.Commons
import qs.Ui
import OmarchyMac

// Tooltip surface for bar buttons. Upstream draws these in a layer-shell
// popup; here it is a small always-on-top window placed under the target.
Window {
  id: root

  property var bar: null
  property Item target: null
  property string text: ""
  property bool shown: false

  readonly property var borderSpec: Border.surfaceSpec("tooltip", "border", Color.tooltip.border, Style.normalBorderWidth)
  readonly property point anchorPos: {
    if (!target || !target.mapToGlobal) return Qt.point(0, 0)
    var w = target.Window.window
    w && w.x; w && w.y; target.x; target.width  // reactive deps
    return target.mapToGlobal(0, 0)
  }

  flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
  color: "transparent"
  visible: shown && text !== "" && !!target
  width: Math.ceil(card.implicitWidth)
  height: Math.ceil(card.implicitHeight)
  x: Math.round(anchorPos.x + (target ? target.width / 2 : 0) - width / 2)
  y: Math.round(anchorPos.y + (target ? target.height : 0) + Style.gapsOut)

  onVisibleChanged: if (visible) MacWindow.configureTooltip(root)

  BorderSurface {
    id: card
    anchors.fill: parent
    color: Color.tooltip.background
    borderSpec: root.borderSpec
    radius: Style.cornerRadius
    implicitWidth: label.implicitWidth + Border.left(borderSpec) + Border.right(borderSpec) + Style.spacing.controlPaddingX * 2
    implicitHeight: label.implicitHeight + Border.top(borderSpec) + Border.bottom(borderSpec) + Style.spacing.controlPaddingY * 2

    Text {
      id: label
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: root.text
      color: Color.tooltip.text
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.bodySmall
    }
  }
}
