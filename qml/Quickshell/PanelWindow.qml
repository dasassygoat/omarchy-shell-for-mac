import QtQuick
import Quickshell
import Quickshell.Wayland
import OmarchyMac

// Quickshell's PanelWindow on macOS.
//
// A layer-shell surface is described by which screen edges it anchors to,
// its margins, and its implicit size on the free axes; the compositor sizes
// and places it. Here the same description drives the geometry of a frameless
// NSWindow: anchored on both edges of an axis spans the screen, anchored on
// one edge sits at that edge, anchored on neither centers. The layer-shell
// layer picks the NSWindow level, keyboard focus picks whether the window can
// become key, and `mask` becomes the window's input mask.
//
// Not reproducible on macOS: exclusive zones (nothing can reserve screen
// space; the property is accepted and ignored) and covering the menu bar.
QsWindow {
  id: root

  // The item plugins draw into (see QsWindow.qsSurface). Declared here so
  // QML resolves `contentItem` to it rather than to QQuickWindow's root.
  readonly property Item contentItem: root.qsSurface

  readonly property PanelAnchors anchors: PanelAnchors {}
  readonly property PanelMargins margins: PanelMargins {}
  property int exclusiveZone: 0
  property int exclusionMode: ExclusionMode.Auto
  property bool aboveWindows: true
  property bool focusable: false

  // ---- screen + geometry ------------------------------------------------

  readonly property var effectiveScreen: {
    if (screen) return screen
    var list = Quickshell.screens
    return list && list.length > 0 ? list[0] : null
  }
  readonly property real screenX: effectiveScreen ? effectiveScreen.x : 0
  readonly property real screenY: effectiveScreen ? effectiveScreen.y : 0
  readonly property real screenW: effectiveScreen ? effectiveScreen.width : 0
  readonly property real screenH: effectiveScreen ? effectiveScreen.height : 0
  readonly property bool spansX: anchors.left && anchors.right
  readonly property bool spansY: anchors.top && anchors.bottom

  // Desired geometry lives in its own properties: AppKit can move a window
  // after Qt placed it, which overwrites x/y/width/height but leaves these
  // intact for placeWindow() to re-assert.
  readonly property int desiredWidth: spansX ? Math.max(1, Math.round(screenW - margins.left - margins.right)) : Math.max(1, Math.round(implicitWidth))
  readonly property int desiredHeight: spansY ? Math.max(1, Math.round(screenH - margins.top - margins.bottom)) : Math.max(1, Math.round(implicitHeight))
  readonly property int desiredX: anchors.left ? screenX + margins.left
    : anchors.right ? screenX + screenW - margins.right - desiredWidth
    : screenX + Math.round((screenW - desiredWidth) / 2)
  readonly property int desiredY: anchors.top ? screenY + margins.top
    : anchors.bottom ? screenY + screenH - margins.bottom - desiredHeight
    : screenY + Math.round((screenH - desiredHeight) / 2)

  width: desiredWidth
  height: desiredHeight
  x: desiredX
  y: desiredY

  function place() {
    if (root.visible) MacWindow.placeWindow(root, desiredX, desiredY, desiredWidth, desiredHeight)
  }
  // Deferred: re-asserting geometry from inside a desired* change handler
  // re-enters the x/y/width/height bindings and trips the binding-loop guard.
  onDesiredXChanged: Qt.callLater(place)
  onDesiredYChanged: Qt.callLater(place)
  onDesiredWidthChanged: Qt.callLater(place)
  onDesiredHeightChanged: Qt.callLater(place)

  // ---- layer, focus, input ---------------------------------------------

  readonly property int layer: root.WlrLayershell.layer
  readonly property int keyboardFocus: root.WlrLayershell.keyboardFocus
  readonly property bool acceptsFocus: focusable || keyboardFocus !== WlrKeyboardFocus.None
  property bool inputTransparent: false

  // Constant on purpose: focus and click-through are applied natively
  // (MacWindow.setAcceptsFocus / setIgnoresMouse). A flags change after the
  // window is shown makes Qt recreate it, and Qt 6.11 then never re-shows
  // the root item.
  flags: Qt.FramelessWindowHint

  function applyLayer() {
    if (!root.visible) return
    MacWindow.configureLayer(root, root.layer, root.aboveWindows)
  }

  function applyFocus() {
    if (root.visible) MacWindow.setAcceptsFocus(root, root.acceptsFocus)
  }

  function applyInput() {
    if (root.visible) MacWindow.setIgnoresMouse(root, root.inputTransparent)
  }

  function collectRegion(region, out) {
    if (!region) return
    var rect = null
    if (region.item && region.item.mapToItem && root.contentItem) {
      var p = region.item.mapToItem(root.contentItem, 0, 0)
      rect = { x: p.x, y: p.y, width: region.item.width, height: region.item.height }
    } else if (region.width > 0 && region.height > 0) {
      rect = { x: region.x, y: region.y, width: region.width, height: region.height }
    }
    if (rect) out.push({ x: rect.x, y: rect.y, width: rect.width, height: rect.height, op: region.intersection })
    var kids = region.regions
    if (kids) for (var i = 0; i < kids.length; i++) collectRegion(kids[i], out)
  }

  function applyMask() {
    if (mask === null || mask === undefined) {
      inputTransparent = false
      if (root.visible) MacWindow.clearMask(root)
      return
    }
    var rects = []
    collectRegion(mask, rects)
    if (!root.visible) {
      inputTransparent = rects.length === 0
      return
    }
    inputTransparent = MacWindow.applyMask(root, rects)
  }

  // Activation is deferred: the flags change that makes the window able to
  // take focus lands in the same event as the keyboardFocus change, and
  // AppKit refuses to make a window key until the new style mask applies.
  readonly property bool debugFocus: Quickshell.env("OMARCHY_MAC_DEBUG_FOCUS") === "1"

  // Computed inline rather than through `acceptsFocus`: inside a
  // keyboardFocus change handler that dependent binding has not updated yet.
  function wantsExclusiveFocus() {
    return root.visible && (root.focusable || root.keyboardFocus !== WlrKeyboardFocus.None)
      && root.keyboardFocus === WlrKeyboardFocus.Exclusive
  }

  function requestFocusIfExclusive() {
    if (debugFocus) console.log("PanelWindow focus check: visible=" + root.visible + " keyboardFocus=" + root.keyboardFocus + " wantsExclusive=" + wantsExclusiveFocus())
    if (!wantsExclusiveFocus()) return
    Qt.callLater(function() { if (root.wantsExclusiveFocus()) MacWindow.activate(root) })
    activateRetry.restart()
  }

  Timer {
    id: activateRetry
    interval: 80
    onTriggered: if (root.wantsExclusiveFocus() && !root.active) MacWindow.activate(root)
  }

  onMaskChanged: applyMask()
  onWidthChanged: applyMask()
  onHeightChanged: applyMask()
  onLayerChanged: applyLayer()
  onAboveWindowsChanged: applyLayer()
  onAcceptsFocusChanged: {
    applyFocus()
    requestFocusIfExclusive()
  }
  onInputTransparentChanged: applyInput()
  onKeyboardFocusChanged: requestFocusIfExclusive()
  onVisibleChanged: {
    if (!visible) return
    MacWindow.setUnconstrained(root, true)
    applyLayer()
    place()
    applyMask()
    applyFocus()
    applyInput()
    requestFocusIfExclusive()
  }

  Connections {
    target: root.mask ? root.mask : null
    function onChanged() { root.applyMask() }
  }

  Component.onCompleted: {
    // Register before the first show so AppKit never constrains the frame,
    // and so a non-focusable surface never becomes key on its first map.
    MacWindow.setUnconstrained(root, true)
    MacWindow.setAcceptsFocus(root, root.acceptsFocus)
    applyLayer()
    applyMask()
  }
}
