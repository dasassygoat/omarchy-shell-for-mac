import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

// Test widget: a bar button whose popup is the pristine upstream PopupCard.
BarWidget {
  id: root
  moduleName: "mac.popupcard-probe"

  readonly property bool opened: popup.open
  function open() { popup.open = true }
  function close() { popup.open = false }
  function toggle() { popup.open = !popup.open }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "popup"
    tooltipText: "PopupCard probe"
    onPressed: root.toggle()
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    contentWidth: popup.fittedContentWidth(Style.space(240))
    contentHeight: popup.fittedContentHeight(label.implicitHeight)

    Text {
      id: label
      text: "PopupCard on macOS\nanchored under the bar button"
      color: Color.popups.text
      font.family: Style.font.family
      font.pixelSize: Style.font.body
    }
  }

  ShellIpc {
    target: "mac.popupcard-probe"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function state(): string { return root.opened ? "open" : "closed" }
  }
}
