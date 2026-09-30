import QtQuick
import qs.Commons

// One layout entry in the bar. Loads the plugin's barWidget entry point and
// injects the three things the upstream bar injects: `bar`, `moduleName`,
// `settings`. Everything the widget then does — SystemClock, ShellIpc, its
// own Panel — is the plugin's own unmodified code.
Item {
  id: slot

  required property var bar
  required property string region
  // Filled by the Repeater: a delegate with required properties receives the
  // model row through `modelData` rather than a context property.
  required property var modelData
  readonly property var entry: modelData

  readonly property string moduleName: bar ? bar.entryId(entry) : ""
  readonly property var manifest: bar && bar.shell ? bar.shell.manifestFor(moduleName) : null
  readonly property string sourceUrl: manifest ? bar.shell.entryPointUrl(manifest, "barWidget") : ""
  readonly property var activeItem: loader.item

  visible: loader.status === Loader.Ready && !!loader.item
  implicitWidth: loader.item ? loader.item.implicitWidth : 0
  implicitHeight: loader.item ? loader.item.implicitHeight : 0
  width: implicitWidth
  height: implicitHeight

  function inject() {
    var target = loader.item
    if (!target) return
    if ("bar" in target) target.bar = slot.bar
    if ("moduleName" in target) target.moduleName = slot.moduleName
    if ("settings" in target) target.settings = slot.bar.entrySettings(slot.entry)
  }

  function applySettings(nextEntry) {
    var target = loader.item
    if (!target || !("settings" in target)) return
    var next = slot.bar.entrySettings(nextEntry)
    if (JSON.stringify(next) !== JSON.stringify(target.settings)) target.settings = next
  }

  Loader {
    id: loader
    source: slot.sourceUrl
    onLoaded: slot.inject()
    onStatusChanged: {
      if (status === Loader.Error) console.warn("bar: failed to load " + slot.moduleName + " from " + slot.sourceUrl)
    }
  }

  Component.onCompleted: {
    if (!sourceUrl) console.warn("bar: no bar-widget plugin installed for id \"" + moduleName + "\" (entry skipped)")
    bar.registerModuleSlot(slot)
  }
  Component.onDestruction: if (bar) bar.unregisterModuleSlot(slot)
}
