"""`import Quickshell.Hyprland`.

There is no Hyprland on macOS. The `Hyprland` singleton is inert (Omarchy's
`Style` subscribes to `rawEvent`; it never fires). `HyprlandFocusGrab` is
real, though: upstream uses it for outside-click dismissal of popups, and on
macOS the equivalent signal is the application losing focus, or focus moving
to a window that is not in `windows`.
"""

import shiboken6
from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QJSValue, QmlElement, QmlSingleton

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


def _ptr(obj):
    try:
        return shiboken6.getCppPointer(obj)[0]
    except Exception:  # noqa: BLE001
        return id(obj)


@QmlElement
class HyprlandFocusGrab(QObject):
    """While `active`, clears itself (emitting `cleared`) as soon as keyboard
    focus leaves the listed `windows`. A short grace period after activation
    lets the popup window finish becoming key first."""

    windowsChanged = Signal()
    activeChanged = Signal()
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._windows = []
        self._active = False
        self._grace = QTimer(self)
        self._grace.setSingleShot(True)
        self._grace.setInterval(300)
        self._grace.timeout.connect(self._check)
        app = QGuiApplication.instance()
        if app is not None:
            app.focusWindowChanged.connect(self._check)
            app.applicationStateChanged.connect(self._check)

    def _owns(self, window):
        if window is None:
            return False
        target = _ptr(window)
        return any(w is not None and _ptr(w) == target for w in self._windows)

    def _check(self, *_):
        if not self._active or self._grace.isActive():
            return
        app = QGuiApplication.instance()
        if app is None:
            return
        focused = app.focusWindow()
        if app.applicationState() == Qt.ApplicationState.ApplicationActive and self._owns(focused):
            return
        self._active = False
        self.activeChanged.emit()
        self.cleared.emit()

    def _getWindows(self):
        return list(self._windows)

    def _setWindows(self, value):
        if isinstance(value, QJSValue):
            value = value.toVariant()
        self._windows = list(value or [])
        self.windowsChanged.emit()

    def _getActive(self):
        return self._active

    def _setActive(self, value):
        value = bool(value)
        if value == self._active:
            return
        self._active = value
        self.activeChanged.emit()
        if value:
            self._grace.start()
        else:
            self._grace.stop()

    windows = Property("QVariantList", _getWindows, _setWindows, notify=windowsChanged)
    active = Property(bool, _getActive, _setActive, notify=activeChanged)
