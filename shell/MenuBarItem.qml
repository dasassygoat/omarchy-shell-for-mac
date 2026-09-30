import QtQuick
import Quickshell
import qs.Commons
import OmarchyMac
import "."

// One bar widget shown as a native menu bar item. The widget runs unmodified
// inside this hidden window; MenuBarItems renders the window into the status
// item's image and forwards clicks. The window's x/y track the item's real
// screen position (learned from clicks), so the widget's popups, which
// anchor through mapToGlobal, open right under the menu bar item.
Window {
  id: root

  required property var bar
  // The Instantiator row: { region, entry } (see MenuBar.orderedEntries).
  required property var modelData
  readonly property string region: modelData ? String(modelData.region || "") : ""
  readonly property var entry: modelData ? modelData.entry : null

  readonly property string pluginId: bar ? bar.entryId(entry) : ""
  readonly property var manifest: bar && bar.shell ? bar.shell.manifestFor(pluginId) : null
  readonly property string displayName: manifest && manifest.barWidget && manifest.barWidget.displayName
    ? manifest.barWidget.displayName : (manifest ? manifest.name : pluginId)
  property int handle: 0
  property bool originKnown: false

  visible: false
  color: "transparent"
  flags: Qt.FramelessWindowHint
  width: Math.max(1, Math.ceil(slot.implicitWidth))
  height: Math.max(1, Math.round(bar ? bar.barSize : 22))

  BarSlot {
    id: slot
    bar: root.bar
    region: root.region
    modelData: root.entry
  }

  function render() {
    if (root.handle > 0) MenuBarItems.render(root.handle)
  }

  // Forward a click to the widget's registered click target under the point,
  // the way upstream's dismissal surface relays clicks into the bar.
  function pressAt(px, py, button) {
    if (!root.bar) return
    var targets = root.bar.clickTargets
    var fallback = null
    for (var i = targets.length - 1; i >= 0; i--) {
      var target = targets[i]
      if (!target || !target.triggerPress || target.visible === false || !target.mapToItem) continue
      if (!root.bar.targetBelongsToWindow(target, root)) continue
      if (!fallback) fallback = target
      var pos = target.mapToItem(root.contentItem, 0, 0)
      if (px >= pos.x && px <= pos.x + target.width && py >= pos.y && py <= pos.y + target.height) {
        target.triggerPress(button)
        return
      }
    }
    if (fallback) fallback.triggerPress(button)
  }

  Timer {
    interval: 250
    repeat: true
    running: root.handle > 0
    onTriggered: root.render()
  }

  onWidthChanged: Qt.callLater(render)

  Connections {
    target: MenuBarItems
    function onOriginChanged(handle, x, y) {
      if (handle !== root.handle) return
      root.x = Math.round(x)
      root.y = Math.round(y)
      root.originKnown = true
    }
    function onPressed(handle, px, py, button) {
      if (handle !== root.handle) return
      root.pressAt(px, py, button)
    }
  }

  Component.onCompleted: {
    // Until a click reveals the real position, assume the right end of the
    // primary screen's menu bar so a keyboard-summoned popup lands nearby.
    var screens = Quickshell.screens
    if (screens && screens.length > 0) {
      root.x = screens[0].x + screens[0].width - root.width - 400
      root.y = screens[0].y
    }
    root.handle = MenuBarItems.create(root, root.pluginId, root.displayName)
    Qt.callLater(render)
  }

  Component.onDestruction: if (root.handle > 0) MenuBarItems.remove(root.handle)
}
