import QtQuick
import Quickshell

// PopupWindow.anchor: where a popup attaches. `rect` is relative to `item`
// when set, otherwise to `window`. `edges` picks the point on that rect,
// `gravity` the direction the popup extends from it.
QtObject {
  property var window: null
  property Item item: null
  property rect rect: Qt.rect(0, 0, 0, 0)
  property int edges: Edges.None
  property int gravity: Edges.None
  property int adjustment: PopupAdjustment.Slide
  readonly property PanelMargins margins: PanelMargins {}

  // Emitted right before the popup is positioned, so the owner can update
  // `rect` from live item geometry.
  signal anchoring()
  signal updateRequested()

  function updateAnchor() { updateRequested() }
}
