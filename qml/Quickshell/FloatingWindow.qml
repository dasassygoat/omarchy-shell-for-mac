import QtQuick
import Quickshell

// Quickshell's FloatingWindow: an ordinary titled window.
QsWindow {
  id: root

  // The item plugins draw into (see QsWindow.qsSurface). Declared here so
  // QML resolves `contentItem` to it rather than to QQuickWindow's root.
  readonly property Item contentItem: root.qsSurface
  property string appId: ""
  width: Math.max(1, Math.round(implicitWidth))
  height: Math.max(1, Math.round(implicitHeight))
}
