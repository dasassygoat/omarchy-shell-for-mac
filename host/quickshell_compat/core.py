"""`import Quickshell` — the root module.

Implements the small, portable slice of Quickshell that Omarchy's shared QML
and plugins actually touch: the `Quickshell` singleton (env, execDetached,
screens, iconPath, paths), `SystemClock`, and the plain container types
`ShellRoot`, `Scope`, `Singleton` and `Variants`.
"""

import os
import sys
from enum import IntEnum

from PySide6.QtCore import (
    ClassInfo,
    Property,
    QDateTime,
    QEnum,
    QObject,
    QProcess,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQml import ListProperty, QmlElement, QmlSingleton, QQmlComponent, QQmlEngine

QML_IMPORT_NAME = "Quickshell"
QML_IMPORT_MAJOR_VERSION = 1


def _warn(message):
    sys.stderr.write(f"quickshell-compat: {message}\n")


# --------------------------------------------------------------------------- #
# Containers
# --------------------------------------------------------------------------- #


class _Container(QObject):
    """QObject with a default `data` list property so QML can nest children."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []

    def _append(self, obj):
        if obj is None:
            return
        # QWindow subclasses (the bar, panels) can only be parented to other
        # windows; keeping a reference is enough to hold them alive.
        if not isinstance(obj, QWindow) and obj.parent() is None:
            obj.setParent(self)
        self._data.append(obj)

    def _count(self):
        return len(self._data)

    def _at(self, index):
        return self._data[index]

    def _clear(self):
        self._data.clear()

    data = ListProperty(QObject, _append, _count, _at, _clear)


@QmlElement
@ClassInfo(DefaultProperty="data")
class ShellRoot(_Container):
    pass


@QmlElement
@ClassInfo(DefaultProperty="data")
class Scope(_Container):
    pass


@QmlElement
@ClassInfo(DefaultProperty="data")
class Singleton(_Container):
    pass


@QmlElement
class Variants(QObject):
    """Instantiate `delegate` once per entry of `model`, exposing `modelData`."""

    modelChanged = Signal()
    delegateChanged = Signal()
    instancesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = []
        self._delegate = None
        self._instances = []

    def _getModel(self):
        return self._model

    def _setModel(self, value):
        self._model = list(value) if isinstance(value, (list, tuple)) else ([] if value is None else [value])
        self.modelChanged.emit()
        self._rebuild()

    def _getDelegate(self):
        return self._delegate

    def _setDelegate(self, value):
        self._delegate = value
        self.delegateChanged.emit()
        self._rebuild()

    def _getInstances(self):
        return list(self._instances)

    def _rebuild(self):
        for inst in self._instances:
            inst.deleteLater()
        self._instances = []
        if self._delegate is None:
            return
        ctx = QQmlEngine.contextForObject(self)
        for entry in self._model:
            obj = self._delegate.createWithInitialProperties({"modelData": entry}, ctx)
            if obj is None:
                _warn("Variants: " + self._delegate.errorString())
                continue
            obj.setParent(self)
            self._instances.append(obj)
        self.instancesChanged.emit()

    model = Property("QVariant", _getModel, _setModel, notify=modelChanged)
    delegate = Property(QQmlComponent, _getDelegate, _setDelegate, notify=delegateChanged)
    instances = Property("QVariantList", _getInstances, notify=instancesChanged)


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #


class ShellScreen(QObject):
    def __init__(self, screen, parent=None):
        super().__init__(parent)
        self._screen = screen

    def _name(self):
        return self._screen.name()

    def _model(self):
        return self._screen.model()

    def _width(self):
        return self._screen.geometry().width()

    def _height(self):
        return self._screen.geometry().height()

    def _x(self):
        return self._screen.geometry().x()

    def _y(self):
        return self._screen.geometry().y()

    def _dpr(self):
        return self._screen.devicePixelRatio()

    name = Property(str, _name, constant=True)
    model = Property(str, _model, constant=True)
    width = Property(int, _width, constant=True)
    height = Property(int, _height, constant=True)
    x = Property(int, _x, constant=True)
    y = Property(int, _y, constant=True)
    devicePixelRatio = Property(float, _dpr, constant=True)


# --------------------------------------------------------------------------- #
# The Quickshell singleton
# --------------------------------------------------------------------------- #


@QmlElement
@QmlSingleton
class Quickshell(QObject):
    screensChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._screens = []
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._rebuildScreens)
            app.screenRemoved.connect(self._rebuildScreens)
        self._rebuildScreens()

    def _rebuildScreens(self, *_):
        app = QGuiApplication.instance()
        self._screens = [ShellScreen(s, self) for s in (app.screens() if app else [])]
        self.screensChanged.emit()

    def _getScreens(self):
        return list(self._screens)

    screens = Property("QVariantList", _getScreens, notify=screensChanged)

    @Slot(str, result=str)
    def env(self, name):
        return os.environ.get(name, "")

    @Slot("QVariant")
    def execDetached(self, command):
        cwd = ""
        argv = command
        if isinstance(command, dict):
            argv = command.get("command", [])
            cwd = command.get("workingDirectory", "") or ""
        argv = [str(a) for a in (argv or [])]
        if not argv:
            _warn("execDetached called with an empty command")
            return
        ok, _pid = QProcess.startDetached(argv[0], argv[1:], cwd)
        if not ok:
            _warn(f"execDetached failed to start: {argv}")

    @Slot(str, result=str)
    @Slot(str, str, result=str)
    def iconPath(self, name, fallback=""):
        # No freedesktop icon themes on macOS. Callers fall back gracefully.
        return fallback or ""

    @Slot()
    @Slot(bool)
    def reload(self, hard=False):
        _warn("Quickshell.reload() is not supported by the mac host yet")

    def _shellDir(self):
        return os.environ.get("QS_SHELL_DIR", "")

    def _shellPath(self):
        return os.environ.get("QS_SHELL_PATH", "")

    def _configDir(self):
        return os.path.expanduser("~/.config/omarchy-shell-mac")

    def _dataDir(self):
        return os.path.expanduser("~/Library/Application Support/omarchy-shell-mac")

    def _stateDir(self):
        return os.path.expanduser("~/.local/state/omarchy-shell-mac")

    def _cacheDir(self):
        return os.path.expanduser("~/Library/Caches/omarchy-shell-mac")

    def _workingDirectory(self):
        return os.getcwd()

    def _processId(self):
        return os.getpid()

    shellDir = Property(str, _shellDir, constant=True)
    shellPath = Property(str, _shellPath, constant=True)
    configDir = Property(str, _configDir, constant=True)
    dataDir = Property(str, _dataDir, constant=True)
    stateDir = Property(str, _stateDir, constant=True)
    cacheDir = Property(str, _cacheDir, constant=True)
    workingDirectory = Property(str, _workingDirectory, constant=True)
    processId = Property(int, _processId, constant=True)


# --------------------------------------------------------------------------- #
# SystemClock
# --------------------------------------------------------------------------- #


@QmlElement
class SystemClock(QObject):
    @QEnum
    class Precision(IntEnum):
        Hours = 0
        Minutes = 1
        Seconds = 2

    dateChanged = Signal()
    precisionChanged = Signal()
    enabledChanged = Signal()

    _UNIT_MS = {0: 3_600_000, 1: 60_000, 2: 1_000}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._precision = int(SystemClock.Precision.Minutes)
        self._enabled = True
        self._date = QDateTime.currentDateTime()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._schedule()

    def _schedule(self):
        if not self._enabled:
            self._timer.stop()
            return
        unit = self._UNIT_MS.get(self._precision, 60_000)
        now = QDateTime.currentDateTime()
        local_ms = now.toMSecsSinceEpoch() + now.offsetFromUtc() * 1000
        wait = unit - (local_ms % unit)
        self._timer.start(max(1, wait + 5))

    def _tick(self):
        self._date = QDateTime.currentDateTime()
        self.dateChanged.emit()
        self._schedule()

    def _getDate(self):
        return self._date

    def _getPrecision(self):
        return self._precision

    def _setPrecision(self, value):
        value = int(value)
        if value == self._precision:
            return
        self._precision = value
        self.precisionChanged.emit()
        self._tick()

    def _getEnabled(self):
        return self._enabled

    def _setEnabled(self, value):
        value = bool(value)
        if value == self._enabled:
            return
        self._enabled = value
        self.enabledChanged.emit()
        if value:
            self._tick()
        else:
            self._timer.stop()

    def _hours(self):
        return self._date.time().hour()

    def _minutes(self):
        return self._date.time().minute()

    def _seconds(self):
        return self._date.time().second()

    date = Property(QDateTime, _getDate, notify=dateChanged)
    precision = Property(int, _getPrecision, _setPrecision, notify=precisionChanged)
    enabled = Property(bool, _getEnabled, _setEnabled, notify=enabledChanged)
    hours = Property(int, _hours, notify=dateChanged)
    minutes = Property(int, _minutes, notify=dateChanged)
    seconds = Property(int, _seconds, notify=dateChanged)
