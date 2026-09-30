import QtQuick
import Quickshell
import OmarchyMac

// Quickshell's PopupWindow on macOS: a frameless window positioned from its
// `anchor`, raised to popup level and activated when shown so a
// HyprlandFocusGrab watching it can dismiss it on an outside click.
QsWindow {
  id: root

  // The item plugins draw into (see QsWindow.qsSurface). Declared here so
  // QML resolves `contentItem` to it rather than to QQuickWindow's root.
  readonly property Item contentItem: root.qsSurface

  readonly property PopupAnchor anchor: PopupAnchor {}
  property bool repositioning: false

  width: Math.max(1, Math.round(implicitWidth))
  height: Math.max(1, Math.round(implicitHeight))
  flags: Qt.FramelessWindowHint

  function screenContaining(px, py) {
    var screens = Quickshell.screens
    for (var i = 0; i < screens.length; i++) {
      var s = screens[i]
      if (px >= s.x && px < s.x + s.width && py >= s.y && py < s.y + s.height) return s
    }
    return screens.length > 0 ? screens[0] : null
  }

  function reposition() {
    var w = anchor.window
    if (!w || repositioning) return
    repositioning = true
    anchor.anchoring()
    var r = anchor.rect
    var baseX = w.x
    var baseY = w.y
    if (anchor.item && anchor.item.mapToItem && w.contentItem) {
      var p = anchor.item.mapToItem(w.contentItem, 0, 0)
      baseX += p.x
      baseY += p.y
    }
    var ax = baseX + r.x, ay = baseY + r.y, aw = r.width, ah = r.height
    var e = anchor.edges, g = anchor.gravity
    var px = (e & Edges.Left) ? ax : (e & Edges.Right) ? ax + aw : ax + aw / 2
    var py = (e & Edges.Top) ? ay : (e & Edges.Bottom) ? ay + ah : ay + ah / 2
    var nx = (g & Edges.Right) ? px + anchor.margins.left
      : (g & Edges.Left) ? px - width - anchor.margins.right
      : px - width / 2
    var ny = (g & Edges.Bottom) ? py + anchor.margins.top
      : (g & Edges.Top) ? py - height - anchor.margins.bottom
      : py - height / 2
    var s = screenContaining(px, py)
    if (s) {
      if (anchor.adjustment & PopupAdjustment.SlideX) nx = Math.max(s.x, Math.min(nx, s.x + s.width - width))
      if (anchor.adjustment & PopupAdjustment.SlideY) ny = Math.max(s.y, Math.min(ny, s.y + s.height - height))
    }
    root.x = Math.round(nx)
    root.y = Math.round(ny)
    repositioning = false
  }

  onVisibleChanged: {
    if (!visible) return
    reposition()
    MacWindow.configurePanel(root)
    if (!(flags & Qt.WindowDoesNotAcceptFocus)) MacWindow.activate(root)
  }
  onWidthChanged: if (visible) reposition()
  onHeightChanged: if (visible) reposition()

  Connections {
    target: root.anchor
    function onWindowChanged() { if (root.visible) root.reposition() }
    function onItemChanged() { if (root.visible) root.reposition() }
    function onRectChanged() { if (root.visible) root.reposition() }
    function onEdgesChanged() { if (root.visible) root.reposition() }
    function onGravityChanged() { if (root.visible) root.reposition() }
    function onAdjustmentChanged() { if (root.visible) root.reposition() }
    function onUpdateRequested() { if (root.visible) root.reposition() }
  }

  Connections {
    target: root.anchor.window ? root.anchor.window : null
    function onXChanged() { if (root.visible) root.reposition() }
    function onYChanged() { if (root.visible) root.reposition() }
    function onWidthChanged() { if (root.visible) root.reposition() }
    function onHeightChanged() { if (root.visible) root.reposition() }
  }
}
