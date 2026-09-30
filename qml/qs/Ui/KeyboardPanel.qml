import QtQuick
import Quickshell
import qs.Commons
import OmarchyMac

// macOS replacement for Omarchy's KeyboardPanel (upstream/pristine/Ui/
// KeyboardPanel.qml). Upstream is a full-screen Wayland layer-shell surface
// that draws a card at `cardOrigin` and uses the rest of the surface to catch
// outside clicks. macOS has no layer shell, so the card is its own frameless
// window placed under the anchor, and losing window activation is what
// dismisses it.
//
// The API a plugin sees is unchanged: anchorItem, owner, bar, open, margin,
// padding, contentWidth/Height, borderSpec, centerOnBar, gap, focusTarget,
// popoutSwitching/popoutSwitchClosing, the default contentItem, and
// fittedContentWidth/Height + cappedContentHeight.
Window {
  id: root

  required property Item anchorItem
  required property QtObject bar
  property var owner: null
  property int margin: Style.gapsOut
  property int padding: Style.spacing.popupPadding
  property int contentWidth: Style.space(280)
  property int contentHeight: Style.space(200)
  property var borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(2)))
  property bool centerOnBar: false
  property bool open: false
  property int gap: Style.gapsOut
  property bool popoutSwitching: false
  property bool popoutSwitchClosing: false
  property bool focusPrimed: false
  property Item focusTarget: null

  // Named panelContent rather than contentItem: on a QtQuick Window the
  // latter is the window's own root item and must not be shadowed.
  default property alias panelContent: contentHolder.children

  readonly property var coordinatorKey: owner || root
  readonly property var anchorWindow: anchorItem ? anchorItem.Window.window : null
  readonly property string barPos: bar ? bar.position : "top"

  function close() {
    if (owner && "close" in owner) owner.close()
    else root.open = false
  }

  // --- geometry ------------------------------------------------------------

  readonly property real screenX: Screen.virtualX
  readonly property real screenY: Screen.virtualY
  readonly property real screenW: Screen.width
  readonly property real screenH: Screen.height
  readonly property real barW: anchorWindow ? anchorWindow.width : screenW
  readonly property real barH: anchorWindow ? anchorWindow.height : 0
  readonly property real availableCardWidth: screenW > 0
    ? Math.max(120, screenW - ((barPos === "left" || barPos === "right") ? barW + gap + margin : margin * 2))
    : 0
  readonly property real availableCardHeight: screenH > 0
    ? Math.max(120, screenH - ((barPos === "top" || barPos === "bottom") ? barH + gap + margin : margin * 2))
    : 0
  readonly property real verticalContentInset: padding * 2 + Border.top(borderSpec) + Border.bottom(borderSpec)

  function fittedContentWidth(width, cap) {
    var desired = Math.max(1, Number(width) || 1)
    var maxWidth = root.availableCardWidth > 0 ? root.availableCardWidth : desired
    if (cap !== undefined && Number(cap) > 0) maxWidth = Math.min(maxWidth, Number(cap))
    return Math.round(Math.min(desired, maxWidth))
  }

  function fittedContentHeight(implicitHeight, cap) {
    var desired = Math.max(root.verticalContentInset, (Number(implicitHeight) || 0) + root.verticalContentInset)
    var maxHeight = root.availableCardHeight > 0 ? root.availableCardHeight : desired
    if (cap !== undefined && Number(cap) > 0) maxHeight = Math.min(maxHeight, Number(cap))
    return Math.round(Math.min(desired, maxHeight))
  }

  function cappedContentHeight(height) {
    var desired = Math.max(root.padding * 2, Number(height) || root.padding * 2)
    var maxHeight = root.availableCardHeight > 0 ? root.availableCardHeight : desired
    return Math.round(Math.min(desired, maxHeight))
  }

  // Anchor position in global (screen) coordinates. The extra reads make the
  // binding re-evaluate when the bar or the anchor moves.
  readonly property point anchorScreenPos: {
    if (!anchorItem || !anchorWindow) return Qt.point(0, 0)
    anchorWindow.x; anchorWindow.y; anchorItem.x; anchorItem.y; anchorItem.width; anchorItem.height
    return anchorItem.mapToGlobal(0, 0)
  }
  readonly property real anchorW: anchorItem ? anchorItem.width : 0
  readonly property real anchorH: anchorItem ? anchorItem.height : 0

  readonly property point cardOrigin: {
    if (!anchorItem || !bar) return Qt.point(screenX + margin, screenY + margin)
    var x = 0, y = 0
    var barX = anchorWindow ? anchorWindow.x : screenX
    var barY = anchorWindow ? anchorWindow.y : screenY
    if (centerOnBar && (barPos === "top" || barPos === "bottom")) {
      x = screenX + screenW / 2 - contentWidth / 2
      y = barPos === "bottom" ? barY - contentHeight - gap : barY + barH + gap
    } else if (centerOnBar) {
      x = barPos === "left" ? barX + barW + gap : barX - contentWidth - gap
      y = screenY + screenH / 2 - contentHeight / 2
    } else if (barPos === "bottom") {
      x = anchorScreenPos.x + anchorW / 2 - contentWidth / 2
      y = barY - contentHeight - gap
    } else if (barPos === "left") {
      x = barX + barW + gap
      y = anchorScreenPos.y + anchorH / 2 - contentHeight / 2
    } else if (barPos === "right") {
      x = barX - contentWidth - gap
      y = anchorScreenPos.y + anchorH / 2 - contentHeight / 2
    } else {
      x = anchorScreenPos.x + anchorW / 2 - contentWidth / 2
      y = barY + barH + gap
    }
    x = Math.max(screenX + margin, Math.min(x, screenX + screenW - contentWidth - margin))
    y = Math.max(screenY + margin, Math.min(y, screenY + screenH - contentHeight - margin))
    return Qt.point(Math.round(x), Math.round(y))
  }

  // --- window --------------------------------------------------------------

  flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
  color: "transparent"
  x: cardOrigin.x
  y: cardOrigin.y
  width: Math.max(1, contentWidth)
  height: Math.max(1, contentHeight)
  visible: open || card.opacity > 0 || popoutSwitching

  onVisibleChanged: {
    if (debugFocus) console.log("KeyboardPanel visible=" + visible + " active=" + active)
    if (visible) MacWindow.configurePanel(root)
  }

  // Clicking anywhere outside the card hands activation to another app or
  // window; that is the macOS equivalent of the layer-shell dismissal area.
  onActiveChanged: {
    if (debugFocus) console.log("KeyboardPanel[" + (owner ? owner.moduleName : "?") + "] active=" + active + " open=" + open + " visible=" + visible)
    if (!active && open && !popoutSwitching) dismissTimer.restart()
  }
  readonly property bool debugFocus: Quickshell.env("OMARCHY_MAC_DEBUG_FOCUS") === "1"

  Timer {
    id: dismissTimer
    interval: 30
    onTriggered: if (root.open && !root.active && !root.popoutSwitching) root.close()
  }

  // --- popout coordination (same-bar single-popout model) -----------------

  onOpenChanged: {
    if (open) {
      focusPrimed = false
      MacWindow.activate(root)
      focusPrimeTimer.restart()
      if (focusTarget) Qt.callLater(function() {
        if (root.open && root.focusTarget) root.focusTarget.forceActiveFocus()
      })
    } else {
      focusPrimeTimer.stop()
      focusPrimed = false
    }
    if (!bar) return
    if (open) {
      popoutSwitchClosing = false
      popoutSwitching = bar.activePopout && bar.activePopout !== coordinatorKey
      bar.requestPopout(coordinatorKey)
      if (popoutSwitching) popoutSwitchTimer.restart()
    } else {
      popoutSwitchClosing = !!(owner && owner.popoutSwitchClosing)
      popoutSwitching = false
      if (bar.activePopout === coordinatorKey) bar.releasePopout(coordinatorKey)
      if (popoutSwitchClosing) closeSwitchTimer.restart()
    }
  }

  Timer {
    id: focusPrimeTimer
    interval: 75
    onTriggered: if (root.open) root.focusPrimed = true
  }

  Timer {
    id: popoutSwitchTimer
    interval: 150
    onTriggered: root.popoutSwitching = false
  }

  Timer {
    id: closeSwitchTimer
    interval: 1
    onTriggered: root.popoutSwitchClosing = false
  }

  // --- card ----------------------------------------------------------------

  BorderSurface {
    id: card
    anchors.fill: parent
    color: Color.popups.background
    borderSpec: root.borderSpec
    padding: root.padding
    radius: Style.cornerRadius
    opacity: root.open || root.popoutSwitching ? 1.0 : 0

    Behavior on opacity {
      enabled: !root.popoutSwitching && !root.popoutSwitchClosing
      NumberAnimation { duration: Style.duration(140); easing.type: Easing.OutCubic }
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.AllButtons
    }

    Item {
      id: contentHolder
      anchors.fill: parent
      anchors.topMargin: card.contentTopInset
      anchors.rightMargin: card.contentRightInset
      anchors.bottomMargin: card.contentBottomInset
      anchors.leftMargin: card.contentLeftInset
      opacity: root.popoutSwitching ? (root.open ? 1.0 : 0) : 1.0

      Behavior on opacity {
        enabled: root.popoutSwitching
        NumberAnimation { duration: Style.duration(140); easing.type: Easing.OutCubic }
      }
    }
  }
}
