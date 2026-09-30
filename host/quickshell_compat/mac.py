"""`import OmarchyMac` — host-only services for the macOS shell.

`Host` answers the questions Omarchy's shell.qml normally answers with bash
helpers and OMARCHY_PATH: where plugins live, how to read/write config, which
monospace font to use. `MacWindow` applies the NSWindow settings that make a
Qt window behave like a layer-shell bar or popup (window level, all Spaces,
no shadow, no Dock activation).
"""

import json
import os
import sys

from PySide6.QtCore import Property, QObject, QRect, Slot
from PySide6.QtGui import QFontDatabase, QRegion
from PySide6.QtQml import QmlElement, QmlSingleton

QML_IMPORT_NAME = "OmarchyMac"
QML_IMPORT_MAJOR_VERSION = 1

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUNDLED_PLUGINS_DIR = os.path.join(PROJECT_ROOT, "plugins")
USER_PLUGINS_DIR = os.path.expanduser("~/.config/omarchy/plugins")
USER_CONFIG_PATH = os.path.abspath(os.environ.get("OMARCHY_MAC_CONFIG") or os.path.expanduser("~/.config/omarchy/shell.json"))
# Extra third-party plugin roots, colon separated (used by the test suite).
EXTRA_PLUGIN_DIRS = [os.path.abspath(p) for p in os.environ.get("OMARCHY_MAC_PLUGIN_DIRS", "").split(":") if p]
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "shell.json")

PREFERRED_FONTS = (
    "JetBrainsMono Nerd Font",
    "JetBrainsMono Nerd Font Mono",
    "JetBrains Mono",
    "CaskaydiaCove Nerd Font",
    "Hack Nerd Font",
    "Menlo",
)


def _warn(message):
    sys.stderr.write(f"omarchy-shell-mac: {message}\n")


def _read_manifest(directory):
    path = os.path.join(directory, "manifest.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        _warn(f"plugin manifest unreadable: {path}: {exc}")
        return None
    if not isinstance(manifest, dict):
        return None
    manifest["__sourceDir"] = directory
    manifest["__manifestPath"] = path
    return manifest


def _validate(manifest):
    problems = []
    if manifest.get("schemaVersion") != 1:
        problems.append("schemaVersion must be 1")
    for key in ("id", "name", "version"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            problems.append(f"{key} is required")
    kinds = manifest.get("kinds")
    entry = manifest.get("entryPoints")
    if not isinstance(kinds, list) or not kinds:
        problems.append("kinds must be a non-empty list")
    if not isinstance(entry, dict):
        problems.append("entryPoints must be an object")
    else:
        for kind in kinds or []:
            key = KIND_TO_ENTRY.get(kind, kind)
            ep = entry.get(key)
            if not isinstance(ep, str) or not ep:
                problems.append(f"entryPoints.{key} missing for kind {kind}")
            elif ep.startswith("/") or ".." in ep.split("/"):
                problems.append(f"entryPoints.{key} must be a safe relative path")
            elif not os.path.isfile(os.path.join(manifest["__sourceDir"], ep)):
                problems.append(f"entryPoints.{key} does not exist")
    return problems


KIND_TO_ENTRY = {
    "bar-widget": "barWidget",
    "panel": "panel",
    "overlay": "overlay",
    "menu": "menu",
    "service": "service",
    "bar": "bar",
}


def scan_plugins(roots):
    """Return validated manifests found one level under each root directory."""
    found = []
    for index, root in enumerate(roots):
        root = os.path.abspath(root)
        first_party = index == 0
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.startswith("."):
                continue
            directory = os.path.join(root, name)
            if not os.path.isdir(directory):
                continue
            manifest = _read_manifest(directory)
            if manifest is None:
                continue
            problems = _validate(manifest)
            if problems:
                _warn(f"plugin {directory} skipped: " + "; ".join(problems))
                continue
            if not first_party and str(manifest.get("id", "")).startswith("omarchy."):
                _warn(f"plugin {directory} skipped: the omarchy.* id prefix is reserved")
                continue
            manifest["__isFirstParty"] = first_party
            found.append(manifest)
    return found


@QmlElement
@QmlSingleton
class Host(QObject):
    def _projectRoot(self):
        return PROJECT_ROOT

    def _bundledPluginsDir(self):
        return BUNDLED_PLUGINS_DIR

    def _userPluginsDir(self):
        return USER_PLUGINS_DIR

    def _userConfigPath(self):
        return USER_CONFIG_PATH

    def _defaultConfigPath(self):
        return DEFAULT_CONFIG_PATH

    def _defaultFontFamily(self):
        override = os.environ.get("OMARCHY_MAC_FONT", "").strip()
        if override:
            return override
        families = set(QFontDatabase.families())
        for name in PREFERRED_FONTS:
            if name in families:
                return name
        return "Menlo"

    projectRoot = Property(str, _projectRoot, constant=True)
    bundledPluginsDir = Property(str, _bundledPluginsDir, constant=True)
    userPluginsDir = Property(str, _userPluginsDir, constant=True)
    userConfigPath = Property(str, _userConfigPath, constant=True)
    defaultConfigPath = Property(str, _defaultConfigPath, constant=True)
    defaultFontFamily = Property(str, _defaultFontFamily, constant=True)

    @Slot(result=str)
    def scanPluginsJson(self):
        # JSON rather than a QVariantList: nested lists inside a QVariantMap
        # reach QML as sequence wrappers, not JS arrays, and upstream code
        # relies on Array.isArray(manifest.kinds).
        return json.dumps(scan_plugins([BUNDLED_PLUGINS_DIR, USER_PLUGINS_DIR, *EXTRA_PLUGIN_DIRS]))

    @Slot(str, str, result=str)
    def entryPointUrl(self, sourceDir, entryPoint):
        """file:// URL for a manifest entry point, refusing paths that escape
        the plugin directory. Takes strings so QML need not marshal the whole
        manifest object across."""
        directory = str(sourceDir or "")
        ep = str(entryPoint or "")
        if not ep or not directory:
            return ""
        resolved = os.path.normpath(os.path.join(directory, ep))
        if not resolved.startswith(os.path.normpath(directory) + os.sep):
            _warn(f"entry point escapes plugin dir: {resolved}")
            return ""
        return "file://" + resolved

    @Slot(result=str)
    def windowsJson(self):
        """Diagnostics: every top-level window with its Qt and NSWindow state."""
        from PySide6.QtGui import QGuiApplication

        out = []
        for w in QGuiApplication.allWindows():
            entry = {
                "type": type(w).__name__,
                "title": w.title(),
                "x": w.x(), "y": w.y(), "width": w.width(), "height": w.height(),
                "visible": w.isVisible(), "visibility": int(w.visibility().value),
                "flags": hex(int(w.flags().value)),
                "active": w.isActive(),
                "exposed": w.isExposed(),
            }
            entry["syncCount"] = getattr(w, "_syncCount", None)
            item = getattr(w, "_surface", None)
            if item is None and hasattr(w, "contentItem") and callable(w.contentItem):
                item = w.contentItem()
            if True:
                if item is not None:
                    entry["contentItem"] = {"visible": item.isVisible(), "width": item.width(), "height": item.height(), "children": len(item.childItems())}
            ns = _nswindow_for(w) if w.isVisible() else None
            if ns is not None:
                frame = ns.frame()
                entry["ns"] = {
                    "level": int(ns.level()), "isVisible": bool(ns.isVisible()),
                    "alpha": float(ns.alphaValue()), "frame": [frame.origin.x, frame.origin.y, frame.size.width, frame.size.height],
                    "ignoresMouse": bool(ns.ignoresMouseEvents()),
                    "onScreen": bool(ns.isOnActiveSpace()),
                }
            out.append(entry)
        return json.dumps(out, indent=2)

    @Slot()
    def forceRenderAll(self):
        from PySide6.QtGui import QGuiApplication

        for w in QGuiApplication.allWindows():
            if w.isVisible():
                w.requestUpdate()

    @Slot(str, result=bool)
    def fileExists(self, path):
        return os.path.isfile(os.path.expanduser(path))

    @Slot(str, result=str)
    def readTextFile(self, path):
        try:
            with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    @Slot(str, str, result=bool)
    def writeTextFile(self, path, text):
        path = os.path.expanduser(path)
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
            return True
        except OSError as exc:
            _warn(f"write failed: {path}: {exc}")
            return False


# --------------------------------------------------------------------------- #
# NSWindow glue
# --------------------------------------------------------------------------- #

NS_MAIN_MENU_LEVEL = 24
NS_STATUS_LEVEL = 25
NS_POPUP_MENU_LEVEL = 101
CG_DESKTOP_LEVEL = -2147483623
CG_DESKTOP_ICON_LEVEL = -2147483603

# WlrLayer.Background / Bottom / Top / Overlay → NSWindow level
LAYER_LEVELS = {
    0: CG_DESKTOP_LEVEL + 1,
    1: CG_DESKTOP_ICON_LEVEL + 1,
    2: NS_STATUS_LEVEL,
    3: NS_POPUP_MENU_LEVEL,
}

CAN_JOIN_ALL_SPACES = 1 << 0
TRANSIENT = 1 << 3
STATIONARY = 1 << 4
IGNORES_CYCLE = 1 << 6
FULL_SCREEN_AUXILIARY = 1 << 8


def _nswindow_for(qwindow):
    # winId() is only an NSView under the cocoa platform plugin; the offscreen
    # plugin used by tests hands back something else entirely.
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.platformName() != "cocoa" or qwindow is None:
        return None
    try:
        import objc  # pyobjc
    except ImportError:
        _warn("pyobjc is not installed; window levels will not be adjusted")
        return None
    wid = int(qwindow.winId())
    if wid == 0:
        return None
    view = objc.objc_object(c_void_p=wid)
    return view.window()


# Per-window behaviour AppKit only offers through an NSWindow subclass method.
# Qt's window classes (QNSWindow / QNSPanel) get constrainFrameRect:toScreen:
# installed once; it consults a set of window numbers and otherwise defers to
# AppKit, so layer-shell surfaces sit exactly where the shell puts them, menu
# bar and Dock included, while other windows keep the default behaviour.
#
# canBecomeKeyWindow is deliberately NOT overridden: Qt implements it on
# QNSWindow (frameless windows may become key unless flagged), and replacing
# it falls through to AppKit's "borderless windows never become key".
#
# Window flags are left alone after a window is shown: changing them makes
# Qt recreate the native window, after which Qt 6.11 leaves the QQuickWindow
# root item hidden for good.
_unconstrained = set()
_overrides_installed = False


def _install_native_overrides():
    global _overrides_installed
    if _overrides_installed:
        return
    _overrides_installed = True
    try:
        import objc
        from AppKit import NSWindow
    except ImportError:
        return
    for name in ("QNSWindow", "QNSPanel"):
        try:
            cls = objc.lookUpClass(name)
        except objc.nosuchclass_error:
            continue

        def make(cls):
            def constrainFrameRect_toScreen_(self, rect, screen):
                if int(self.windowNumber()) in _unconstrained:
                    return rect
                return objc.super(cls, self).constrainFrameRect_toScreen_(rect, screen)

            return [
                objc.selector(constrainFrameRect_toScreen_, selector=b"constrainFrameRect:toScreen:",
                              signature=NSWindow.constrainFrameRect_toScreen_.signature),
            ]

        try:
            objc.classAddMethods(cls, make(cls))
        except Exception as exc:  # noqa: BLE001
            _warn(f"could not install window overrides on {name}: {exc}")


@QmlElement
@QmlSingleton
class MacWindow(QObject):
    @Slot(QObject, bool)
    def setUnconstrained(self, window, value):
        """Let (or stop letting) a window sit anywhere on screen, menu bar and
        Dock included. Creates the native window if needed so it takes effect
        before the first show."""
        ns = _nswindow_for(window)
        if ns is None:
            return
        _install_native_overrides()
        number = int(ns.windowNumber())
        if value:
            _unconstrained.add(number)
        else:
            _unconstrained.discard(number)

    @Slot(QObject, bool)
    def setAcceptsFocus(self, window, value):
        """Best effort: a window that stops accepting focus gives up key
        status. Refusing focus outright would need the Qt flag, which cannot
        change after the window is shown (see above); surfaces that must never
        take focus are click-through anyway (empty mask), so this only matters
        for a clickable, non-focusable third-party panel."""
        ns = _nswindow_for(window)
        if ns is None:
            return
        if not value and ns.isKeyWindow():
            ns.resignKeyWindow()

    @Slot(QObject, bool)
    def setIgnoresMouse(self, window, value):
        """Click-through for the whole window (an empty layer-shell mask)."""
        ns = _nswindow_for(window)
        if ns is None:
            return
        ns.setIgnoresMouseEvents_(bool(value))

    @Slot(QObject, int, int, int, int)
    def placeWindow(self, window, x, y, width, height):
        """Re-assert geometry after the native window exists. AppKit may have
        moved a window constrained before it was registered; Qt's stored
        geometry then reflects that, so the bindings alone will not fix it."""
        if window is None:
            return
        window.setGeometry(int(x), int(y), max(1, int(width)), max(1, int(height)))

    @Slot(QObject)
    def configureBar(self, window):
        ns = _nswindow_for(window)
        if ns is None:
            return
        ns.setLevel_(NS_STATUS_LEVEL)
        ns.setCollectionBehavior_(CAN_JOIN_ALL_SPACES | STATIONARY | IGNORES_CYCLE | FULL_SCREEN_AUXILIARY)
        ns.setHasShadow_(False)
        ns.setHidesOnDeactivate_(False)

    @Slot(QObject)
    def configurePanel(self, window):
        ns = _nswindow_for(window)
        if ns is None:
            return
        ns.setLevel_(NS_POPUP_MENU_LEVEL)
        ns.setCollectionBehavior_(CAN_JOIN_ALL_SPACES | TRANSIENT | IGNORES_CYCLE | FULL_SCREEN_AUXILIARY)
        ns.setHasShadow_(False)
        ns.setHidesOnDeactivate_(False)

    @Slot(QObject)
    def configureTooltip(self, window):
        self.configurePanel(window)

    @Slot(QObject, int, bool)
    def configureLayer(self, window, layer, aboveWindows):
        """Place a PanelWindow at the NSWindow level matching its layer-shell layer."""
        ns = _nswindow_for(window)
        if ns is None:
            return
        level = LAYER_LEVELS.get(int(layer), NS_STATUS_LEVEL)
        if not aboveWindows and int(layer) >= 2:
            level = LAYER_LEVELS[1]
        ns.setLevel_(level)
        ns.setCollectionBehavior_(CAN_JOIN_ALL_SPACES | STATIONARY | IGNORES_CYCLE | FULL_SCREEN_AUXILIARY)
        ns.setHasShadow_(False)
        ns.setHidesOnDeactivate_(False)

    @Slot(QObject, "QVariantList", result=bool)
    def applyMask(self, window, rects):
        """Set the window's input mask from Region rectangles.

        Returns true when the resulting region is empty, in which case the
        caller makes the window transparent for input instead (Qt treats an
        empty mask as "no mask")."""
        region = QRegion()
        for entry in rects or []:
            try:
                rect = QRect(int(entry["x"]), int(entry["y"]), int(entry["width"]), int(entry["height"]))
            except (KeyError, TypeError, ValueError):
                continue
            op = int(entry.get("op", 0))
            piece = QRegion(rect)
            if op == 1:
                region = region.subtracted(piece)
            elif op == 2:
                region = region.intersected(piece)
            elif op == 3:
                region = region.xored(piece)
            else:
                region = region.united(piece)
        window.setMask(region)
        return region.isEmpty()

    @Slot(QObject)
    def clearMask(self, window):
        window.setMask(QRegion())

    @Slot(QObject)
    def activate(self, window):
        try:
            from AppKit import NSApplication
        except ImportError:
            return
        app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)
        ns = _nswindow_for(window)
        if ns is not None:
            ns.makeKeyAndOrderFront_(None)
        window.requestActivate()
        if os.environ.get("OMARCHY_MAC_DEBUG_FOCUS") == "1":
            def report():
                n = _nswindow_for(window)
                _warn(f"activate: visible={window.isVisible()} qtActive={window.isActive()} appActive={bool(app.isActive())} "
                      f"isKey={bool(n.isKeyWindow()) if n else None} canBecomeKey={bool(n.canBecomeKeyWindow()) if n else None} "
                      f"styleMask={hex(int(n.styleMask())) if n else None}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, report)


def hide_from_dock():
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    except ImportError:
        _warn("pyobjc is not installed; the host will show a Dock icon")
        return
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
