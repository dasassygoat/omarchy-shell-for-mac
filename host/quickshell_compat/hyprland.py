"""`import Quickshell.Hyprland` — inert stand-ins.

There is no Hyprland on macOS. Omarchy's shared `Style` singleton subscribes
to `Hyprland.rawEvent` and a few files reference `HyprlandFocusGrab`, so the
names must resolve; they simply never fire.
"""

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import QmlElement, QmlSingleton

QML_IMPORT_NAME = "Quickshell.Hyprland"
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
@QmlSingleton
class Hyprland(QObject):
    rawEvent = Signal(QObject)
    focusedMonitorChanged = Signal()
    focusedWorkspaceChanged = Signal()
    workspacesChanged = Signal()
    monitorsChanged = Signal()

    def _none(self):
        return None

    def _empty(self):
        return []

    focusedMonitor = Property(QObject, _none, notify=focusedMonitorChanged)
    focusedWorkspace = Property(QObject, _none, notify=focusedWorkspaceChanged)
    workspaces = Property("QVariantList", _empty, notify=workspacesChanged)
    monitors = Property("QVariantList", _empty, notify=monitorsChanged)

    @Slot(str)
    def dispatch(self, _request):
        pass

    @Slot()
    def refreshMonitors(self):
        pass

    @Slot()
    def refreshWorkspaces(self):
        pass

    @Slot()
    def refreshToplevels(self):
        pass


@QmlElement
class HyprlandFocusGrab(QObject):
    windowsChanged = Signal()
    activeChanged = Signal()
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self._active = False

    def _getWindows(self):
        return list(self._windows)

    def _setWindows(self, value):
        self._windows = list(value or [])
        self.windowsChanged.emit()

    def _getActive(self):
        return self._active

    def _setActive(self, value):
        self._active = bool(value)
        self.activeChanged.emit()

    windows = Property("QVariantList", _getWindows, _setWindows, notify=windowsChanged)
    active = Property(bool, _getActive, _setActive, notify=activeChanged)
