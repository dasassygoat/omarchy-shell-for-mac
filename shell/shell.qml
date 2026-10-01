import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import OmarchyMac
import "."

// macOS host root. Plays the part of Omarchy's shell.qml for the pieces a
// plugin can observe: plugin discovery from manifest.json, shell.json as the
// single source of layout + per-widget settings, updateEntryInline() write-
// back, the "shell" IPC target, and the bar that mounts bar-widget plugins.
ShellRoot {
  id: shell

  readonly property string home: Quickshell.env("HOME")
  readonly property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string userConfigPath: Host.userConfigPath
  readonly property string defaultsPath: Host.defaultConfigPath

  property var shellConfig: null
  property var layout: ({ left: [], center: [], right: [] })
  property var installedPlugins: ({})
  property string configSource: ""

  readonly property var builtinShellConfig: ({
    version: 1,
    bar: { position: "top", layout: { left: [], center: [{ id: "omarchy.clock" }], right: [] } },
    plugins: [],
    disabledPlugins: []
  })

  // ------------------------------------------------------------ plugins

  function rescanPlugins() {
    var list = JSON.parse(Host.scanPluginsJson())
    var map = {}
    for (var i = 0; i < list.length; i++) {
      var m = list[i]
      var id = String(m.id || "")
      if (map[id]) {
        console.warn("plugin id " + id + " claimed twice; keeping " + map[id].__sourceDir + ", ignoring " + m.__sourceDir)
        continue
      }
      map[id] = m
    }
    installedPlugins = map
    syncPanelEntries()
    syncServices()
  }

  function manifestFor(pluginId) {
    return installedPlugins[String(pluginId || "")] || null
  }

  readonly property var entryPointKeys: ({ "bar-widget": "barWidget", panel: "panel", overlay: "overlay", menu: "menu", service: "service", bar: "bar" })

  function entryPointUrl(manifest, kind) {
    if (!Util.isPlainObject(manifest) || !Util.isPlainObject(manifest.entryPoints)) return ""
    var ep = manifest.entryPoints[entryPointKeys[kind] || kind]
    if (!ep) return ""
    return Host.entryPointUrl(String(manifest.__sourceDir || ""), String(ep))
  }

  function listPluginsJson() {
    var out = []
    for (var id in installedPlugins) {
      var m = installedPlugins[id]
      out.push({
        id: id, name: m.name, version: m.version, kinds: m.kinds,
        firstParty: m.__isFirstParty === true, path: m.__sourceDir,
        enabled: isEnabled(id)
      })
    }
    return JSON.stringify(out, null, 2)
  }

  // Upstream rules: first-party plugins that are not bar options are on unless
  // listed in disabledPlugins[]; everything else is on when shell.json
  // references it (a bar layout entry or a plugins[] entry).
  function isEnabled(id) {
    var cfg = shellConfig || builtinShellConfig
    var m = installedPlugins[id]
    var kinds = m && Array.isArray(m.kinds) ? m.kinds : []
    var widgetOnly = kinds.length > 0 && kinds.every(function(k) { return k === "bar-widget" })
    // First-party infrastructure (panels, overlays, menus, services) is on
    // unless disabled; a first-party bar widget is on only while it is in
    // the bar layout, like any other widget.
    if (m && m.__isFirstParty === true && !widgetOnly && kinds.indexOf("bar") === -1) {
      var disabled = Array.isArray(cfg.disabledPlugins) ? cfg.disabledPlugins : []
      return disabled.indexOf(id) === -1
    }
    var sections = ["left", "center", "right"]
    for (var s = 0; s < sections.length; s++) {
      var arr = layout[sections[s]] || []
      for (var i = 0; i < arr.length; i++) if (arr[i].id === id) return true
    }
    var plugins = Array.isArray(cfg.plugins) ? cfg.plugins : []
    for (var p = 0; p < plugins.length; p++) {
      var entry = plugins[p]
      if ((typeof entry === "string" ? entry : entry && entry.id) === id) return true
    }
    return false
  }

  // ------------------------------------------------------------- config

  function parseConfig(text, label) {
    if (!text) return null
    try {
      var parsed = JSON.parse(text)
      if (Util.isPlainObject(parsed) && parsed.version === 1) return parsed
      console.warn(label + " missing version: 1, ignoring")
    } catch (e) {
      console.warn(label + " parse failed: " + e)
    }
    return null
  }

  function loadConfig() {
    var cfg = null
    var source = ""
    if (Host.fileExists(userConfigPath)) {
      cfg = parseConfig(Host.readTextFile(userConfigPath), "user shell.json")
      if (cfg) source = userConfigPath
    }
    if (!cfg) {
      cfg = parseConfig(Host.readTextFile(defaultsPath), "default shell.json")
      if (cfg) source = defaultsPath
    }
    if (!cfg) {
      cfg = Util.cloneJson(builtinShellConfig)
      source = "builtin"
    }
    applyConfig(cfg, source)
  }

  function layoutSignature(l) {
    var ids = []
    var sections = ["left", "center", "right"]
    for (var s = 0; s < sections.length; s++) {
      var arr = l[sections[s]] || []
      for (var i = 0; i < arr.length; i++) ids.push(sections[s] + ":" + arr[i].id)
    }
    return ids.join("|")
  }

  function applyConfig(cfg, source) {
    shellConfig = cfg
    configSource = source
    var mac = Util.isPlainObject(cfg.mac) ? cfg.mac : {}
    macMenuBarForeground = typeof mac.menubarForeground === "string" ? mac.menubarForeground : ""
    macMenuBarFontSize = isFinite(Number(mac.menubarFontSize)) ? Number(mac.menubarFontSize) : 0
    ensureBar(String(mac.bar || "strip"))
    var next = Util.normalizeLayout(cfg.bar ? cfg.bar.layout : null)
    // Only rebuild the bar when the set/order of widgets changed; a settings-
    // only change is pushed into the live widgets instead, the way the
    // upstream bar's applySettingsDelta keeps a clicked clock from being torn
    // down and recreated mid-click.
    if (layoutSignature(next) !== layoutSignature(layout)) layout = next
    else bar.applyLayoutSettings(next)
    applyMacStyle(cfg.mac)
    if (cfg.bar && typeof cfg.bar.position === "string" && barMode === "strip") bar.position = cfg.bar.position
    syncPanelEntries()
    syncServices()
  }

  // Hyprland supplies rounding and gaps on Linux; on the Mac they come from
  // an optional `mac` block in shell.json.
  function applyMacStyle(mac) {
    var m = Util.isPlainObject(mac) ? mac : {}
    if (isFinite(Number(m.cornerRadius))) Style.cornerRadius = Math.max(0, Math.round(Number(m.cornerRadius)))
    if (isFinite(Number(m.gapsOut))) Style.gapsOut = Math.max(0, Math.round(Number(m.gapsOut)))
    if (typeof m.font === "string" && m.font.length > 0) Style.fontFamily = m.font
  }

  function persistShellConfig(copy) {
    var text = JSON.stringify(copy, null, 2) + "\n"
    if (!Host.writeTextFile(userConfigPath, text)) {
      console.warn("shell.json write failed: " + userConfigPath)
      return
    }
    lastWrittenText = text
    applyConfig(copy, userConfigPath)
  }
  property string lastWrittenText: ""

  // ------------------------------------------------ enable / disable / move
  // Port of upstream services/PluginRegistry.qml setEnabled/moveBarEntry
  // without the clone bookkeeping (omarchy plugin clone is not vendored).

  property string lastEnableError: ""

  function ensureConfigShape(config) {
    if (!Util.isPlainObject(config.bar)) config.bar = {}
    if (!Util.isPlainObject(config.bar.layout)) config.bar.layout = {}
    var sections = ["left", "center", "right"]
    for (var i = 0; i < sections.length; i++)
      if (!Array.isArray(config.bar.layout[sections[i]])) config.bar.layout[sections[i]] = []
    if (!Array.isArray(config.plugins)) config.plugins = []
    if (!Array.isArray(config.disabledPlugins)) config.disabledPlugins = []
  }

  function barEntryId(entry) {
    return Util.canonicalWidgetId(String(Util.isPlainObject(entry) ? entry.id : entry || ""))
  }

  function findBarLocation(config, id, section) {
    var key = Util.canonicalWidgetId(String(id))
    var sections = ["left", "center", "right"]
    for (var s = 0; s < sections.length; s++) {
      if (section && sections[s] !== section) continue
      var entries = config.bar.layout[sections[s]]
      for (var i = 0; i < entries.length; i++)
        if (barEntryId(entries[i]) === key) return { found: true, kind: "bar", section: sections[s], index: i }
    }
    return { found: false }
  }

  function findEntryLocation(config, id) {
    var key = Util.canonicalWidgetId(String(id))
    var barLocation = findBarLocation(config, key, "")
    if (barLocation.found) return barLocation
    for (var j = 0; j < config.plugins.length; j++) {
      var entry = config.plugins[j]
      if ((typeof entry === "string" ? entry : entry && entry.id) === key) return { found: true, kind: "plugin", index: j }
    }
    return { found: false }
  }

  function defaultBarWidgetSection(manifest) {
    var metadata = manifest && Util.isPlainObject(manifest.barWidget) ? manifest.barWidget : null
    var section = metadata ? String(metadata.defaultSection || "") : ""
    return ["left", "center", "right"].indexOf(section) !== -1 ? section : "center"
  }

  function barTarget(config, placement, fallbackSection) {
    var target = placement || {}
    var section = ["left", "center", "right"].indexOf(String(target.section || "")) !== -1
      ? String(target.section) : fallbackSection
    var relativeId = String(target.before || target.after || "")
    if (relativeId) {
      var relative = findBarLocation(config, relativeId, section && target.section ? section : "")
      if (!relative.found) return { error: "could not find target widget " + relativeId }
      return { section: relative.section, index: relative.index + (target.after ? 1 : 0) }
    }
    if (target.index !== undefined && target.index !== null) {
      var requested = Math.max(0, Math.floor(Number(target.index)))
      return { section: section, index: Math.min(requested, config.bar.layout[section].length) }
    }
    var anchors = { left: "omarchy.workspaces", center: "omarchy.weather", right: "omarchy.tray" }
    var anchor = findBarLocation(config, anchors[section], section)
    return { section: section, index: anchor.found ? anchor.index + 1 : config.bar.layout[section].length }
  }

  function moveBarEntry(config, id, placement) {
    var key = Util.canonicalWidgetId(String(id))
    var source = findBarLocation(config, key, String(placement.fromSection || ""))
    if (!source.found) return "could not find widget " + key
    var entry = config.bar.layout[source.section][source.index]
    config.bar.layout[source.section].splice(source.index, 1)
    var target = barTarget(config, placement, source.section)
    if (target.error) {
      config.bar.layout[source.section].splice(source.index, 0, entry)
      return target.error
    }
    config.bar.layout[target.section].splice(target.index, 0, entry)
    return ""
  }

  function setEnabled(id, value, placement) {
    var key = Util.canonicalWidgetId(String(id))
    lastEnableError = ""
    var manifest = installedPlugins[key]
    if (!manifest) {
      if (value) { lastEnableError = "unknown"; return false }
    }
    var kinds = manifest && Array.isArray(manifest.kinds) ? manifest.kinds : []
    if (kinds.indexOf("bar") !== -1) {
      lastEnableError = "bar plugins (full bar replacements) are not supported by the mac host yet"
      return false
    }
    var isBarWidget = kinds.indexOf("bar-widget") !== -1
    var isFirstParty = !!(manifest && manifest.__isFirstParty)
    var config = JSON.parse(JSON.stringify(shellConfig || builtinShellConfig))
    ensureConfigShape(config)

    if (value && placement && (placement.before || placement.after)) {
      var relativeId = String(placement.before || placement.after)
      if (!findBarLocation(config, relativeId, String(placement.section || "")).found) {
        lastEnableError = "could not find target widget " + relativeId
        return false
      }
    }

    var location = findEntryLocation(config, key)
    if (value) {
      config.disabledPlugins = config.disabledPlugins.filter(function(d) { return d !== key })
      var entry = { id: key }
      var insertedWithPlacement = false
      if (!location.found && isBarWidget) {
        var target = barTarget(config, placement || {}, defaultBarWidgetSection(manifest))
        if (target.error) { lastEnableError = target.error; return false }
        config.bar.layout[target.section].splice(target.index, 0, entry)
        insertedWithPlacement = true
      } else if (!location.found && !isFirstParty) {
        config.plugins.push(entry)
      }
      if (isBarWidget && !insertedWithPlacement && placement && Object.keys(placement).length) {
        var moveError = moveBarEntry(config, key, placement)
        if (moveError) { lastEnableError = moveError; return false }
      }
    } else {
      if (location.kind === "bar") config.bar.layout[location.section].splice(location.index, 1)
      else if (location.kind === "plugin") config.plugins.splice(location.index, 1)
      if (isFirstParty && !isBarWidget && config.disabledPlugins.indexOf(key) === -1) config.disabledPlugins.push(key)
    }
    persistShellConfig(config)
    return true
  }

  function moveBarWidget(id, placement) {
    var config = JSON.parse(JSON.stringify(shellConfig || builtinShellConfig))
    ensureConfigShape(config)
    var error = moveBarEntry(config, id, placement || {})
    if (error) return error
    persistShellConfig(config)
    return ""
  }

  // Verbatim contract from upstream shell.qml: a widget hands back its whole
  // inline layout entry and the shell rewrites just that entry.
  function updateEntryInline(moduleName, settings) {
    var stripped = Util.canonicalWidgetId(moduleName)
    var copy = JSON.parse(JSON.stringify(shellConfig || builtinShellConfig))
    if (!Util.isPlainObject(copy.bar)) copy.bar = { layout: { left: [], center: [], right: [] } }
    if (!Util.isPlainObject(copy.bar.layout)) copy.bar.layout = { left: [], center: [], right: [] }
    if (!Array.isArray(copy.plugins)) copy.plugins = []

    var sections = ["left", "center", "right"]
    var foundInLayout = false
    var dirty = false
    for (var s = 0; s < sections.length; s++) {
      var arr = copy.bar.layout[sections[s]] || []
      for (var i = 0; i < arr.length; i++) {
        if (arr[i] && Util.canonicalWidgetId(arr[i].id) === stripped) {
          var next = { id: stripped }
          for (var k in settings) if (k !== "id") next[k] = settings[k]
          if (JSON.stringify(arr[i]) !== JSON.stringify(next)) {
            arr[i] = next
            dirty = true
          }
          foundInLayout = true
        }
      }
    }
    if (!foundInLayout) {
      for (var j = 0; j < copy.plugins.length; j++) {
        if (copy.plugins[j] && copy.plugins[j].id === stripped) {
          var pnext = { id: stripped }
          for (var pk in settings) if (pk !== "id") pnext[pk] = settings[pk]
          if (JSON.stringify(copy.plugins[j]) !== JSON.stringify(pnext)) {
            copy.plugins[j] = pnext
            dirty = true
          }
        }
      }
    }
    if (!dirty) return false
    persistShellConfig(copy)
    return true
  }

  // External edits to ~/.config/omarchy/shell.json take effect live.
  FileView {
    path: shell.userConfigPath
    watchChanges: true
    preload: false
    printErrors: false
    onFileChanged: {
      var text = Host.readTextFile(shell.userConfigPath)
      if (text === shell.lastWrittenText) return
      shell.loadConfig()
    }
  }

  // ------------------------------------------------- panels, overlays, menus

  // Mirrors upstream shell.qml: a plugin of kind panel/overlay/menu gets a
  // Loader that is active while the plugin is summoned (or always, for
  // keepLoaded plugins). summon() queues the payload until the Loader has an
  // item, then hands it to the plugin's open(payloadJson); hide() calls
  // close() and, unless keepLoaded, unloads it.
  property var openPanelIds: ({})
  property var pendingPayloads: ({})
  property var panelLoaders: ({})
  property var panelEntries: []
  property string panelEntriesSignature: ""

  function isBarWidgetPanelPlugin(pluginId) {
    var m = installedPlugins[String(pluginId || "")]
    if (!m || !Array.isArray(m.kinds)) return false
    if (m.kinds.indexOf("bar-widget") === -1) return false
    var loaderKinds = ["panel", "overlay", "menu"]
    for (var i = 0; i < loaderKinds.length; i++) if (m.kinds.indexOf(loaderKinds[i]) !== -1) return false
    return true
  }

  function summon(pluginId, payloadJson) {
    var id = String(pluginId || "")
    if (!installedPlugins[id]) {
      console.warn("summon: unknown plugin", id)
      return false
    }
    if (!isEnabled(id)) {
      console.warn("summon: plugin not enabled, not summoning:", id)
      return false
    }
    if (isBarWidgetPanelPlugin(id)) {
      var summoned = bar.summonBarWidget(id)
      if (!summoned) console.warn("summon: no live bar widget for:", id)
      return summoned === true
    }
    var next = ({})
    for (var k in openPanelIds) next[k] = openPanelIds[k]
    next[id] = true
    openPanelIds = next

    var pending = ({})
    for (var p in pendingPayloads) pending[p] = pendingPayloads[p].slice()
    var queue = pending[id] || []
    queue.push(payloadJson || "")
    pending[id] = queue
    pendingPayloads = pending

    deliverIfLoaded(id)
    return true
  }

  function hide(pluginId) {
    var id = String(pluginId || "")
    if (isBarWidgetPanelPlugin(id)) {
      var hidden = bar.hideBarWidget(id)
      if (!hidden) console.warn("hide: no live bar widget for:", id)
      return hidden === true
    }
    invokeIfLoaded(id, "close")
    if (!openPanelIds[id]) return true
    var next = ({})
    for (var k in openPanelIds) if (k !== id) next[k] = openPanelIds[k]
    openPanelIds = next
    return true
  }

  function isPluginOpen(pluginId) {
    var id = String(pluginId || "")
    if (isBarWidgetPanelPlugin(id)) return bar.isBarWidgetOpen(id)
    var loader = panelLoaders[id]
    if (loader && loader.item && loader.item.opened !== undefined) return loader.item.opened === true
    return openPanelIds[id] === true
  }

  function toggle(pluginId, payloadJson) {
    var id = String(pluginId || "")
    return isPluginOpen(id) ? hide(id) : summon(id, payloadJson)
  }

  function registerPanelLoader(pluginId, loader) {
    var next = ({})
    for (var k in panelLoaders) next[k] = panelLoaders[k]
    next[pluginId] = loader
    panelLoaders = next
    deliverIfLoaded(pluginId)
  }

  function unregisterPanelLoader(pluginId) {
    if (!panelLoaders[pluginId]) return
    var next = ({})
    for (var k in panelLoaders) if (k !== pluginId) next[k] = panelLoaders[k]
    panelLoaders = next
  }

  function deliverIfLoaded(pluginId) {
    var loader = panelLoaders[pluginId]
    if (!loader || !loader.item) return
    var queue = pendingPayloads[pluginId]
    if (!Array.isArray(queue) || queue.length === 0) return
    var pending = ({})
    for (var p in pendingPayloads) if (p !== pluginId) pending[p] = pendingPayloads[p]
    pendingPayloads = pending
    if (typeof loader.item.open === "function") {
      for (var i = 0; i < queue.length; i++) loader.item.open(queue[i])
    } else {
      console.warn("summon: plugin " + pluginId + " has no open() function")
    }
  }

  function invokeIfLoaded(pluginId, method) {
    var loader = panelLoaders[pluginId]
    if (!loader || !loader.item) return false
    if (typeof loader.item[method] !== "function") return false
    loader.item[method]()
    return true
  }

  function computePanelEntries() {
    var out = []
    var panelKinds = ["panel", "overlay", "menu"]
    for (var id in installedPlugins) {
      var m = installedPlugins[id]
      if (!m || !Array.isArray(m.kinds)) continue
      var kind = ""
      for (var i = 0; i < panelKinds.length; i++) {
        if (m.kinds.indexOf(panelKinds[i]) !== -1) { kind = panelKinds[i]; break }
      }
      if (!kind) continue
      if (!isEnabled(id)) continue
      out.push({ pluginId: id, entryKind: kind, keepLoaded: m.keepLoaded === true, sourceUrl: String(entryPointUrl(m, kind) || "") })
    }
    return out
  }

  // Only reassign the array (and so rebuild the Loaders) when the set of
  // entries actually changes; a shell.json settings write must not tear down
  // an open overlay.
  function syncPanelEntries() {
    var entries = computePanelEntries()
    var sig = entries.map(function(e) { return e.pluginId + "|" + e.entryKind + "|" + e.keepLoaded + "|" + e.sourceUrl }).join("\n")
    if (sig === panelEntriesSignature) return
    panelEntriesSignature = sig
    panelEntries = entries
  }

  Instantiator {
    id: panelInstantiator
    model: shell.panelEntries
    active: true

    delegate: QtObject {
      id: panelEntry
      required property var modelData
      readonly property string pluginId: modelData.pluginId
      readonly property string entryKind: modelData.entryKind
      readonly property bool keepLoaded: modelData.keepLoaded
      readonly property string sourceUrl: modelData.sourceUrl
      readonly property var manifest: shell.installedPlugins[pluginId]

      property Loader panelLoader: Loader {
        source: panelEntry.sourceUrl
        active: panelEntry.sourceUrl !== "" && (panelEntry.keepLoaded || shell.openPanelIds[panelEntry.pluginId] === true)
        asynchronous: true
        onLoaded: {
          if (!item) return
          if ("omarchyPath" in item) item.omarchyPath = shell.omarchyPath
          if ("shell" in item) item.shell = shell
          if ("manifest" in item) item.manifest = panelEntry.manifest
          if ("service" in item) item.service = shell.serviceFor(panelEntry.pluginId)
          shell.registerPanelLoader(panelEntry.pluginId, this)
        }
        onStatusChanged: {
          if (status === Loader.Error) {
            console.warn("panel plugin " + panelEntry.pluginId + " failed to load from " + panelEntry.sourceUrl)
            shell.hide(panelEntry.pluginId)
          }
        }
        Component.onDestruction: shell.unregisterPanelLoader(panelEntry.pluginId)
      }
    }
  }

  // ---------------------------------------------------------------- services

  // Headless singletons (kind "service"), created once per enabled plugin.
  property var services: ({})
  property QtObject serviceHost: QtObject {}

  function serviceFor(pluginId) {
    return services[String(pluginId || "")] || null
  }

  function ensureService(id) {
    if (services[id]) return services[id]
    var m = installedPlugins[id]
    if (!m || !Array.isArray(m.kinds) || m.kinds.indexOf("service") === -1) return null
    var url = entryPointUrl(m, "service")
    if (!url) return null
    var comp = Qt.createComponent(url, Component.PreferSynchronous)
    if (comp.status !== Component.Ready) {
      console.warn("service plugin load failed for " + id + ": " + comp.errorString())
      return null
    }
    var inst = comp.createObject(serviceHost)
    if (!inst) {
      console.warn("service plugin createObject returned null for", id)
      return null
    }
    if ("omarchyPath" in inst) inst.omarchyPath = shell.omarchyPath
    if ("shell" in inst) inst.shell = shell
    if ("manifest" in inst) inst.manifest = m
    var next = ({})
    for (var k in services) next[k] = services[k]
    next[id] = inst
    services = next
    return inst
  }

  function syncServices() {
    for (var id in installedPlugins) {
      var m = installedPlugins[id]
      if (!m || !Array.isArray(m.kinds) || m.kinds.indexOf("service") === -1) continue
      if (!isEnabled(id)) continue
      ensureService(id)
    }
    var next = ({})
    var changed = false
    for (var existing in services) {
      var still = installedPlugins[existing]
      if (still && Array.isArray(still.kinds) && still.kinds.indexOf("service") !== -1 && isEnabled(existing)) {
        next[existing] = services[existing]
        continue
      }
      if (services[existing] && typeof services[existing].destroy === "function") services[existing].destroy()
      changed = true
    }
    if (changed) services = next
  }

  // The bar host: a strip along the top edge (Bar.qml) or native menu bar
  // items (MenuBar.qml), chosen by `mac.bar` in shell.json.
  property var bar: null
  property string barMode: ""
  property string macMenuBarForeground: ""
  property real macMenuBarFontSize: 0

  Component { id: stripBarComponent; Bar {} }
  Component { id: menuBarComponent; MenuBar {} }

  function ensureBar(mode) {
    mode = mode === "menubar" ? "menubar" : "strip"
    if (mode === "menubar" && !MenuBarItems.available) {
      console.warn("mac.bar = menubar needs pyobjc; falling back to the strip bar")
      mode = "strip"
    }
    if (bar && barMode === mode) return
    if (bar) bar.destroy()
    barMode = mode
    bar = (mode === "menubar" ? menuBarComponent : stripBarComponent).createObject(shell, { shell: shell })
  }

  ShellIpc {
    target: "shell"

    function ping(): string { return "pong" }
    function listPlugins(): string { return shell.listPluginsJson() }
    function rescanPlugins(): void { shell.rescanPlugins() }
    function reloadConfig(): void { shell.loadConfig() }
    function configJson(): string { return JSON.stringify(shell.shellConfig, null, 2) }
    function configSource(): string { return shell.configSource }
    function summon(id: string, payloadJson: string): string { return shell.summon(id, payloadJson) ? "ok" : "no panel widget for " + id }
    function hide(id: string): void { shell.hide(id) }
    function toggle(id: string, payloadJson: string): void { shell.toggle(id, payloadJson) }
    function isOpen(id: string): string { return shell.isPluginOpen(id) ? "open" : "closed" }
    function setPluginEnabled(id: string, enabled: string): string {
      return shell.setEnabled(id, String(enabled) === "true", {}) ? "ok" : (shell.lastEnableError || "unknown")
    }
    function enablePlugin(id: string, placementJson: string): string {
      try {
        var placement = JSON.parse(placementJson || "{}")
        return shell.setEnabled(id, true, placement) ? "ok" : (shell.lastEnableError || "unknown")
      } catch (e) {
        return "invalid placement: " + e
      }
    }
    function moveBarWidget(id: string, placementJson: string): string {
      try {
        var error = shell.moveBarWidget(id, JSON.parse(placementJson || "{}"))
        return error ? error : "ok"
      } catch (e) {
        return "invalid placement: " + e
      }
    }
    function putBarWidget(id: string, placementJson: string): string {
      var cfg = shell.shellConfig || shell.builtinShellConfig
      shell.ensureConfigShape(cfg)
      if (shell.findBarLocation(cfg, id, "").found) return "ok"
      return enablePlugin(id, placementJson)
    }
    function listServices(): string { return JSON.stringify(Object.keys(shell.services)) }
    function quit(): void { Qt.quit() }
    function nativeWindows(): string { return Host.windowsJson() }
    function forceRender(): void { Host.forceRenderAll() }
    function debugWindows(): string {
      var screens = []
      for (var i = 0; i < Quickshell.screens.length; i++) {
        var sc = Quickshell.screens[i]
        screens.push(sc.name + " " + sc.width + "x" + sc.height + "@" + sc.x + "," + sc.y + " dpr=" + sc.devicePixelRatio)
      }
      return JSON.stringify({
        barMode: shell.barMode,
        bar: shell.barMode === "strip"
          ? { x: bar.x, y: bar.y, width: bar.width, height: bar.height, visible: bar.visible, active: bar.active,
              screen: bar.screen ? bar.screen.name : null, slots: bar.moduleSlots.length }
          : { slots: bar.moduleSlots.length, barSize: bar.barSize, dark: MenuBarItems.dark },
        clockOpen: bar.isBarWidgetOpen("omarchy.clock"),
        panelEntries: shell.panelEntries.map(function(e) { return e.pluginId + ":" + e.entryKind + (e.keepLoaded ? ":keep" : "") }),
        instantiated: panelInstantiator.count,
        openPanels: Object.keys(shell.openPanelIds),
        loadedPanels: Object.keys(shell.panelLoaders),
        services: Object.keys(shell.services),
        screens: screens
      }, null, 2)
    }
  }

  // Plain IpcHandlers (not ShellIpc) never register with IpcRegistry, but
  // `qs ipc call` reaches them on Linux, so the socket does here too, with
  // the registry's own rules: enabled, exact target, a declared function,
  // matching argument count.
  function callPlainIpcHandler(target, method, args) {
    var handlers = Host.ipcHandlers()
    for (var i = 0; i < handlers.length; i++) {
      var handler = handlers[i]
      if (!handler || !handler.enabled || handler.target !== target) continue
      if (IpcRegistry.declaredFunctions(handler).indexOf(method) === -1) continue
      if (handler[method].length !== args.length) continue
      try {
        var out = handler[method].apply(handler, args)
        return { ran: true, output: out === undefined || out === null ? "" : String(out) }
      } catch (error) {
        console.warn("ipc " + target + " " + method + " failed: " + error)
        return { ran: true, output: "" }
      }
    }
    return { ran: false }
  }

  // Socket requests arrive from Python; the registry answers exactly what a
  // `qs ipc call` would.
  Connections {
    target: ipcServer
    function onRequested(requestId, target, method, args) {
      var result = IpcRegistry.call(String(target), String(method), args)
      if (result.ran !== true) result = shell.callPlainIpcHandler(String(target), String(method), args)
      ipcServer.reply(requestId, result.ran === true, result.ran ? String(result.output || "") : "")
    }
  }

  Component.onCompleted: {
    Style.fontFamily = Host.defaultFontFamily
    ensureBar("strip")
    rescanPlugins()
    loadConfig()
    console.log("omarchy-shell-mac: " + Object.keys(installedPlugins).length + " plugin(s), config from " + configSource)
  }
}
