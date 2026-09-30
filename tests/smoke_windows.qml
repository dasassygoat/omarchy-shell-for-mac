import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons
import qs.Ui
ShellRoot {
  PanelWindow {
    id: bar
    anchors { top: true; left: true; right: true }
    implicitHeight: 26
    color: "black"
    visible: true
    WlrLayershell.layer: WlrLayer.Top
    Rectangle { id: btn; x: 100; width: 40; height: 20; color: "gray" }
    Component.onCompleted: console.log("PanelWindow bar:", x, y, width, height, "| itemPosition", JSON.stringify(itemPosition(btn)), "| btn.QsWindow.window === bar", btn.QsWindow.window === bar, "| layer", layer, "| acceptsFocus", acceptsFocus)
  }
  OverlayWindow {
    id: ov
    shown: false
    Component.onCompleted: console.log("OverlayWindow parked:", width, height, "mask empty ->", inputTransparent, "| layer", layer)
  }
  PanelWindow {
    id: osd
    anchors { top: true; bottom: true; left: true; right: true }
    mask: Region {}
    visible: true
    color: "transparent"
    Component.onCompleted: console.log("fullscreen PanelWindow:", x, y, width, height, "inputTransparent", inputTransparent)
  }
  PanelWindow {
    id: centered
    implicitWidth: 300; implicitHeight: 200
    mask: Region { x: 10; y: 10; width: 50; height: 50 }
    visible: true
    Component.onCompleted: console.log("centered PanelWindow:", x, y, width, height, "inputTransparent", inputTransparent)
  }
  PopupCard {
    id: card
    anchorItem: btn
    bar: QtObject { property string position: "top"; property var activePopout: null; function requestPopout(o) {} function releasePopout(o) {} }
    contentWidth: 200; contentHeight: 80
    open: true
    Text { text: "hi" }
  }
  Timer { interval: 300; running: true; onTriggered: { console.log("PopupCard window at", card.x, card.y, card.width, card.height, "visible", card.visible, "(expect x = 100+20-100 = 20, y = 26 + gapsOut)"); ov.shown = true; Qt.callLater(function() { console.log("overlay shown:", ov.x, ov.y, ov.width, ov.height, "transparent", ov.inputTransparent, "layer", ov.layer); Qt.quit() }) } }
}
