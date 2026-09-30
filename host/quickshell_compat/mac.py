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

from PySide6.QtCore import Property, QObject, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QmlElement, QmlSingleton

QML_IMPORT_NAME = "OmarchyMac"
QML_IMPORT_MAJOR_VERSION = 1

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUNDLED_PLUGINS_DIR = os.path.join(PROJECT_ROOT, "plugins")
USER_PLUGINS_DIR = os.path.expanduser("~/.config/omarchy/plugins")
USER_CONFIG_PATH = os.path.expanduser("~/.config/omarchy/shell.json")
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

    @Slot(result="QVariantList")
    def scanPlugins(self):
        return scan_plugins([BUNDLED_PLUGINS_DIR, USER_PLUGINS_DIR])

    @Slot("QVariant", str, result=str)
    def entryPointUrl(self, manifest, kind):
        if not isinstance(manifest, dict):
            return ""
        entry = manifest.get("entryPoints") or {}
        ep = entry.get(KIND_TO_ENTRY.get(kind, kind))
        directory = manifest.get("__sourceDir") or ""
        if not ep or not directory:
            return ""
        resolved = os.path.normpath(os.path.join(directory, ep))
        if not resolved.startswith(os.path.normpath(directory) + os.sep):
            _warn(f"entry point escapes plugin dir: {resolved}")
            return ""
        return "file://" + resolved

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

CAN_JOIN_ALL_SPACES = 1 << 0
TRANSIENT = 1 << 3
STATIONARY = 1 << 4
IGNORES_CYCLE = 1 << 6
FULL_SCREEN_AUXILIARY = 1 << 8


def _nswindow_for(qwindow):
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


@QmlElement
@QmlSingleton
class MacWindow(QObject):
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

    @Slot(QObject)
    def activate(self, window):
        try:
            from AppKit import NSApplication
        except ImportError:
            return
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        window.requestActivate()


def hide_from_dock():
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    except ImportError:
        _warn("pyobjc is not installed; the host will show a Dock icon")
        return
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
