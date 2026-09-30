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
    var list = Host.scanPlugins()
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
  }

  function manifestFor(pluginId) {
    return installedPlugins[String(pluginId || "")] || null
  }

  function entryPointUrl(manifest, kind) {
    return Host.entryPointUrl(manifest, kind)
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

  function isEnabled(id) {
    var cfg = shellConfig || builtinShellConfig
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
    var next = Util.normalizeLayout(cfg.bar ? cfg.bar.layout : null)
    // Only rebuild the bar when the set/order of widgets changed; a settings-
    // only change is pushed into the live widgets instead, the way the
    // upstream bar's applySettingsDelta keeps a clicked clock from being torn
    // down and recreated mid-click.
    if (layoutSignature(next) !== layoutSignature(layout)) layout = next
    else bar.applyLayoutSettings(next)
    applyMacStyle(cfg.mac)
    if (cfg.bar && typeof cfg.bar.position === "string") bar.position = cfg.bar.position
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

  // ------------------------------------------------------------ summons

  function summon(pluginId, payloadJson) { return bar.summonBarWidget(pluginId) }
  function hide(pluginId) { return bar.hideBarWidget(pluginId) }
  function toggle(pluginId, payloadJson) {
    return bar.isBarWidgetOpen(pluginId) ? bar.hideBarWidget(pluginId) : bar.summonBarWidget(pluginId)
  }

  Bar {
    id: bar
    shell: shell
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
    function quit(): void { Qt.quit() }
    function debugWindows(): string {
      var screens = []
      for (var i = 0; i < Quickshell.screens.length; i++) {
        var sc = Quickshell.screens[i]
        screens.push(sc.name + " " + sc.width + "x" + sc.height + "@" + sc.x + "," + sc.y + " dpr=" + sc.devicePixelRatio)
      }
      return JSON.stringify({
        bar: { x: bar.x, y: bar.y, width: bar.width, height: bar.height, visible: bar.visible, active: bar.active,
               screen: bar.screen ? bar.screen.name : null, slots: bar.moduleSlots.length,
               widgets: bar.moduleWidgets("omarchy.clock").length },
        clockOpen: bar.isBarWidgetOpen("omarchy.clock"),
        screens: screens
      }, null, 2)
    }
  }

  // Socket requests arrive from Python; the registry answers exactly what a
  // `qs ipc call` would.
  Connections {
    target: ipcServer
    function onRequested(requestId, target, method, args) {
      var result = IpcRegistry.call(String(target), String(method), args)
      ipcServer.reply(requestId, result.ran === true, result.ran ? String(result.output || "") : "")
    }
  }

  Component.onCompleted: {
    Style.fontFamily = Host.defaultFontFamily
    rescanPlugins()
    loadConfig()
    console.log("omarchy-shell-mac: " + Object.keys(installedPlugins).length + " plugin(s), config from " + configSource)
  }
}
