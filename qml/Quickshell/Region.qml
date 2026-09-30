import QtQuick
import Quickshell

// Input region for a window mask. A plain rectangle, or the geometry of
// `item` mapped into the window, combined with any child regions.
QtObject {
  id: region

  property real x: 0
  property real y: 0
  property real width: 0
  property real height: 0
  property Item item: null
  property int intersection: Intersection.Combine
  property int shape: RegionShape.Rect
  default property list<QtObject> regions

  signal changed()

  onXChanged: changed()
  onYChanged: changed()
  onWidthChanged: changed()
  onHeightChanged: changed()
  onItemChanged: changed()
  onIntersectionChanged: changed()
  onRegionsChanged: changed()
}
