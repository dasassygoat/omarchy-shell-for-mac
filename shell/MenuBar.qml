import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import OmarchyMac
import "."

// Bar host that puts every bar widget into the native macOS menu bar as its
// own status item (see MenuBarItem). Presents the same surface to widgets as
// Bar.qml (the PluginBarApi contract); the differences are physical: one row
// ordered right-to-left by macOS, the menu bar's height and text colour, and
// no hover, so tooltips become the item's native tooltip.
QtObject {
  id: root

  property var shell: null
  property var manifest: null

  // ---- presentation state read by widgets (PluginBarApi contract) ----
  property string position: "top"
  readonly property bool menuBar: true
  readonly property bool vertical: false
  readonly property int barSize: Math.round(MenuBarItems.thickness())
  property string fontFamily: Style.font.family
  property color menuBarForeground: root.shell && root.shell.macMenuBarForeground !== ""
    ? root.shell.macMenuBarForeground
    : (MenuBarItems.dark ? "#f2f2f2" : "#1c1c1c")
  property color foreground: menuBarForeground
  property color barForeground: menuBarForeground
  property color background: "transparent"
  property color urgent: Color.bar.active
  property bool transparent: true
  property bool foregroundAnimationEnabled: true
  property bool centerSectionRevealHeld: false
  property bool centerHoverRevealSuppressed: false
  property var activePopout: null
  property var clickTargets: []
  property var moduleSlots: []
  readonly property var layoutConfig: shell ? shell.layout : ({ left: [], center: [], right: [] })
  readonly property var foreignPopoutMarker: ({ foreign: true })

  // macOS places a new status item at the left end of the status area, so
  // the layout is instantiated back to front to read left-to-right.
  readonly property var orderedEntries: {
    var out = []
    var sections = ["left", "center", "right"]
    for (var s = 0; s < sections.length; s++) {
      var arr = layoutConfig[sections[s]] || []
      for (var i = 0; i < arr.length; i++) out.push({ region: sections[s], entry: arr[i] })
    }
    return out.reverse()
  }

  property list<QtObject> resources: [
    Instantiator {
      model: root.orderedEntries
      delegate: MenuBarItem { bar: root }
    }
  ]

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

  // ---- popout coordination ----
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

  function setCenterHoverRevealSuppressed(value) { centerHoverRevealSuppressed = !!value }
  function setIndicatorItemHovered(value) {}

  // ---- layout helpers ----
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

  function panelSlots() {
    var slots = []
    for (var j = 0; j < moduleSlots.length; j++) {
      var slot = moduleSlots[j]
      var item = slot ? slot.activeItem : null
      if (!item || typeof item.open !== "function" || typeof item.close !== "function" || item.opened === undefined) continue
      slots.push(slot)
    }
    return slots
  }

  function switchPanelFrom(owner, direction) {
    if (!owner) return false
    var slots = panelSlots()
    var currentIndex = -1
    for (var i = 0; i < slots.length; i++) if (slots[i].activeItem === owner) { currentIndex = i; break }
    if (currentIndex < 0 || slots.length < 2) return false
    var step = direction < 0 ? -1 : 1
    var nextSlot = slots[(currentIndex + step + slots.length) % slots.length]
    if (!nextSlot || !nextSlot.activeItem || nextSlot.activeItem === owner) return false
    nextSlot.activeItem.open()
    return true
  }

  function moduleWidgets(pluginId) {
    var id = String(pluginId || "")
    var items = []
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

  function run(command) { Util.execDetached(String(command || "")) }

  // ---- tooltips: no hover on a rendered image, so the text goes to the
  //      status item's native tooltip instead ----
  function itemHandleFor(target) {
    var window = target && target.Window ? target.Window.window : null
    return window && window.handle !== undefined ? window.handle : 0
  }

  function showTooltip(target, text) {
    var handle = itemHandleFor(target)
    if (handle > 0 && text) MenuBarItems.setToolTip(handle, String(text))
  }

  function hideTooltip(target) {}
  function clearTooltip() {}
}
