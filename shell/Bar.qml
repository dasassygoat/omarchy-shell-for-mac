import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import OmarchyMac
import "."

// The macOS bar. Presents the same surface a bar widget sees on Linux — the
// properties and functions of upstream Bar.qml / PluginBarApi.qml that
// widgets and their panels call — on top of a frameless always-on-top window
// pinned to the top edge of the primary screen.
Window {
  id: root

  property var shell: null
  property var manifest: null

  // ---- presentation state read by widgets (PluginBarApi contract) ----
  property string position: "top"
  readonly property bool vertical: position === "left" || position === "right"
  readonly property int barSize: vertical ? Style.bar.sizeVertical : Style.bar.sizeHorizontal
  property string fontFamily: Style.font.family
  property color foreground: Color.bar.text
  property color barForeground: Color.bar.text
  property color background: Color.bar.background
  property color urgent: Color.bar.active
  property bool transparent: false
  property bool foregroundAnimationEnabled: true
  property bool centerSectionRevealHeld: false
  property bool centerHoverRevealSuppressed: false
  property var activePopout: null
  property var clickTargets: []
  property var moduleSlots: []
  readonly property var layoutConfig: shell ? shell.layout : ({ left: [], center: [], right: [] })
  readonly property var foreignPopoutMarker: ({ foreign: true })

  // ---- window ----
  flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
  color: root.background
  x: Screen.virtualX
  y: Screen.virtualY
  width: Screen.width
  height: barSize
  visible: true
  title: "omarchy-shell-mac bar"

  Component.onCompleted: MacWindow.configureBar(root)

  // ---- click targets / slots ----
  function registerClickTarget(target) {
    if (!target || clickTargets.indexOf(target) !== -1) return
    var next = clickTargets.slice()
    next.push(target)
    clickTargets = next
  }

  function unregisterClickTarget(target) {
    clickTargets = clickTargets.filter(function(item) { return item !== target })
  }

  function registerModuleSlot(slot) {
    if (!slot || moduleSlots.indexOf(slot) !== -1) return
    var next = moduleSlots.slice()
    next.push(slot)
    moduleSlots = next
  }

  function unregisterModuleSlot(slot) {
    moduleSlots = moduleSlots.filter(function(item) { return item !== slot })
  }

  function targetBelongsToWindow(target, window) {
    return !!target && !!window && target.Window && target.Window.window === window
  }

  // ---- popout coordination (one open panel per bar) ----
  function requestPopout(owner) {
    if (activePopout === owner) return
    if (activePopout) {
      if ("closeForPopoutSwitch" in activePopout) activePopout.closeForPopoutSwitch()
      else if ("close" in activePopout) activePopout.close()
    }
    activePopout = owner
  }

  function releasePopout(owner) {
    if (activePopout === owner) activePopout = null
  }

  function setCenterHoverRevealSuppressed(value) {
    centerHoverRevealSuppressed = !!value
  }

  function setIndicatorItemHovered(value) {}

  // ---- layout helpers (BarModel equivalents) ----
  function entryId(entry) {
    if (typeof entry === "string") return Util.canonicalWidgetId(entry)
    return Util.isPlainObject(entry) ? Util.canonicalWidgetId(entry.id) : ""
  }

  function entrySettings(entry) {
    if (!Util.isPlainObject(entry)) return { id: entryId(entry) }
    var copy = Util.cloneJson(entry)
    copy.id = entryId(entry)
    return copy
  }

  function layoutEntries(region) {
    var entries = layoutConfig ? layoutConfig[region] : null
    return Array.isArray(entries) ? entries : []
  }

  function applyLayoutSettings(nextLayout) {
    var sections = ["left", "center", "right"]
    for (var s = 0; s < sections.length; s++) {
      var arr = nextLayout[sections[s]] || []
      for (var i = 0; i < arr.length; i++) {
        var id = entryId(arr[i])
        for (var j = 0; j < moduleSlots.length; j++) {
          var slot = moduleSlots[j]
          if (slot && slot.region === sections[s] && slot.moduleName === id) slot.applySettings(arr[i])
        }
      }
    }
  }

  function panelNavigationSlots(region) {
    var entries = layoutEntries(region)
    var slots = []
    for (var i = 0; i < entries.length; i++) {
      var id = entryId(entries[i])
      for (var j = 0; j < moduleSlots.length; j++) {
        var slot = moduleSlots[j]
        if (!slot || slot.region !== region || slot.moduleName !== id) continue
        var item = slot.activeItem
        if (!item || item.visible !== true || slot.visible !== true || slot.width <= 0 || slot.height <= 0) continue
        if (typeof item.open !== "function" || typeof item.close !== "function" || item.opened === undefined) continue
        slots.push(slot)
        break
      }
    }
    return slots
  }

  function switchPanelFrom(owner, direction) {
    if (!owner) return false
    var currentSlot = null
    for (var i = 0; i < moduleSlots.length; i++) {
      if (moduleSlots[i] && moduleSlots[i].activeItem === owner) { currentSlot = moduleSlots[i]; break }
    }
    if (!currentSlot) return false
    var slots = panelNavigationSlots(currentSlot.region)
    if (slots.length < 2) return false
    var currentIndex = slots.indexOf(currentSlot)
    if (currentIndex < 0) return false
    var step = direction < 0 ? -1 : 1
    var nextSlot = slots[(currentIndex + step + slots.length) % slots.length]
    if (!nextSlot || !nextSlot.activeItem || nextSlot.activeItem === owner) return false
    nextSlot.activeItem.open()
    return true
  }

  function moduleWidgets(pluginId) {
    var id = String(pluginId || "")
    var items = []
    if (!id) return items
    for (var i = 0; i < moduleSlots.length; i++) {
      var slot = moduleSlots[i]
      if (slot && slot.activeItem && slot.moduleName === id) items.push(slot.activeItem)
    }
    return items
  }

  function findPanelWidget(pluginId) {
    var id = String(pluginId || "")
    for (var i = 0; i < moduleSlots.length; i++) {
      var slot = moduleSlots[i]
      if (!slot || !slot.activeItem || slot.moduleName !== id) continue
      var item = slot.activeItem
      if (typeof item.open !== "function" || typeof item.close !== "function" || item.opened === undefined) continue
      return item
    }
    return null
  }

  function summonBarWidget(pluginId) {
    var item = findPanelWidget(pluginId)
    if (!item) return false
    item.open()
    return true
  }

  function hideBarWidget(pluginId) {
    var item = findPanelWidget(pluginId)
    if (!item) return false
    item.close()
    return true
  }

  function isBarWidgetOpen(pluginId) {
    var item = findPanelWidget(pluginId)
    return !!item && item.opened === true
  }

  function run(command) {
    Util.execDetached(String(command || ""))
  }

  // ---- tooltips ----
  property var tooltipTarget: null
  property var pendingTooltipTarget: null
  property string tooltipText: ""
  property string pendingTooltipText: ""
  property bool tooltipShown: false
  property int tooltipRequest: 0

  function targetTooltipHovered(target) {
    return !!target && target.tooltipHovered === true
  }

  function clearTooltip() {
    tooltipTimer.stop()
    tooltipShown = false
    tooltipTarget = null
    tooltipText = ""
    pendingTooltipTarget = null
    pendingTooltipText = ""
  }

  function showTooltip(target, text) {
    clearTooltip()
    if (!targetTooltipHovered(target) || !text) {
      tooltipRequest += 1
      return
    }
    var request = tooltipRequest + 1
    tooltipRequest = request
    pendingTooltipTarget = target
    pendingTooltipText = text
    Qt.callLater(function() {
      if (request !== tooltipRequest) return
      if (!targetTooltipHovered(pendingTooltipTarget)) { clearTooltip(); return }
      tooltipTarget = pendingTooltipTarget
      tooltipText = pendingTooltipText
      pendingTooltipTarget = null
      pendingTooltipText = ""
      tooltipTimer.restart()
    })
  }

  function hideTooltip(target) {
    if (tooltipTarget !== target && pendingTooltipTarget !== target) return
    tooltipRequest += 1
    clearTooltip()
  }

  Timer {
    id: tooltipTimer
    interval: 400
    onTriggered: {
      if (root.targetTooltipHovered(root.tooltipTarget)) root.tooltipShown = true
      else root.clearTooltip()
    }
  }

  BarTooltip {
    bar: root
    target: root.tooltipTarget
    text: root.tooltipText
    shown: root.tooltipShown
  }

  // ---- sections ----
  Item {
    anchors.fill: parent

    Row {
      id: leftRow
      anchors.left: parent.left
      anchors.leftMargin: Style.space(4)
      anchors.verticalCenter: parent.verticalCenter
      spacing: 0
      Repeater {
        model: root.layoutConfig.left
        BarSlot { bar: root; region: "left" }
      }
    }

    Row {
      id: centerRow
      anchors.centerIn: parent
      spacing: 0
      Repeater {
        model: root.layoutConfig.center
        BarSlot { bar: root; region: "center" }
      }
    }

    Row {
      id: rightRow
      anchors.right: parent.right
      anchors.rightMargin: Style.space(4)
      anchors.verticalCenter: parent.verticalCenter
      spacing: 0
      Repeater {
        model: root.layoutConfig.right
        BarSlot { bar: root; region: "right" }
      }
    }
  }
}
