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
from PySide6.QtQml import ListProperty, QJSValue, QmlElement, QmlSingleton, QQmlComponent, QQmlEngine

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
        if isinstance(value, QJSValue):
            value = value.toVariant()
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
        if isinstance(command, QJSValue):
            command = command.toVariant()
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


# --------------------------------------------------------------------------- #
# Enums used by PanelWindow / PopupWindow / Region
# --------------------------------------------------------------------------- #

from PySide6.QtCore import QPointF, QSizeF  # noqa: E402
from PySide6.QtQml import QmlAttached, QmlUncreatable  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402


@QmlElement
@QmlUncreatable("enum holder")
class ExclusionMode(QObject):
    @QEnum
    class Enum(IntEnum):
        Normal = 0
        Ignore = 1
        Auto = 2


@QmlElement
@QmlUncreatable("enum holder")
class Edges(QObject):
    Enum = QEnum(IntEnum("Enum", {"None": 0, "Top": 1, "Left": 2, "Right": 4, "Bottom": 8}))


@QmlElement
@QmlUncreatable("enum holder")
class PopupAdjustment(QObject):
    Enum = QEnum(IntEnum("Enum", {
        "None": 0,
        "SlideX": 1, "SlideY": 2, "Slide": 3,
        "FlipX": 4, "FlipY": 8, "Flip": 12,
        "ResizeX": 16, "ResizeY": 32, "Resize": 48,
        "All": 63,
    }))


@QmlElement
@QmlUncreatable("enum holder")
class Intersection(QObject):
    @QEnum
    class Enum(IntEnum):
        Combine = 0
        Subtract = 1
        Intersect = 2
        Xor = 3


@QmlElement
@QmlUncreatable("enum holder")
class RegionShape(QObject):
    @QEnum
    class Enum(IntEnum):
        Rect = 0
        Ellipse = 1


# --------------------------------------------------------------------------- #
# QsWindow: the window base PanelWindow / PopupWindow / FloatingWindow build on
# --------------------------------------------------------------------------- #


class QsWindowAttached(QObject):
    """`Item.QsWindow.window` — the QsWindow (or any QQuickWindow) an item lives in."""

    windowChanged = Signal()

    def __init__(self, item):
        super().__init__(item)
        self._item = item if isinstance(item, QQuickItem) else None
        if self._item is not None:
            self._item.windowChanged.connect(self._onWindowChanged)

    def _onWindowChanged(self, _window):
        self.windowChanged.emit()

    def _window(self):
        return self._item.window() if self._item is not None else None

    def _contentItem(self):
        window = self._window()
        if window is None:
            return None
        surface = getattr(window, "_surface", None)
        return surface if surface is not None else window.contentItem()

    def _mask(self):
        window = self._window()
        return getattr(window, "_mask", None) if window is not None else None

    window = Property(QObject, _window, notify=windowChanged)
    contentItem = Property(QObject, _contentItem, notify=windowChanged)
    mask = Property(QObject, _mask, notify=windowChanged)


@QmlElement
@QmlAttached(QsWindowAttached)
@ClassInfo(DefaultProperty="qsData")
class QsWindow(QQuickWindow):
    """A QQuickWindow with Quickshell's window surface.

    Adds `screen` (a ShellScreen, not Qt's screen info), `implicitWidth` /
    `implicitHeight`, `mask` and `backingWindowVisible`.

    `contentItem` is not the QQuickWindow root but a full-size child of it,
    and declared children are parented there. Qt 6.11 never re-shows a root
    item once it has been hidden, and Omarchy's OverlayWindow toggles
    `contentItem.visible` on every open; a plain child item has no such
    problem and sits at the same origin, so coordinates are unchanged.
    """

    screenChanged = Signal()
    implicitWidthChanged = Signal()
    implicitHeightChanged = Signal()
    maskChanged = Signal()
    backingWindowVisibleChanged = Signal()

    def __init__(self, parent=None):
        QQuickWindow.__init__(self, parent)
        self._screen = None
        self._implicitWidth = 100.0
        self._implicitHeight = 100.0
        self._mask = None
        self._data = []
        self._syncCount = 0
        self._surface = QQuickItem(QQuickWindow.contentItem(self))
        self._surface.setObjectName("qsContentItem")
        self._syncSurface()
        self.widthChanged.connect(self._syncSurface)
        self.heightChanged.connect(self._syncSurface)
        self.visibilityChanged.connect(lambda _v: self.backingWindowVisibleChanged.emit())

    def _syncSurface(self, *_):
        self._syncCount += 1
        self._surface.setWidth(float(max(1, self.width())))
        self._surface.setHeight(float(max(1, self.height())))

    def resizeEvent(self, event):
        # Belt and braces next to the widthChanged/heightChanged connections.
        QQuickWindow.resizeEvent(self, event)
        self._syncSurface()

    # ---- default property: children go onto the surface ---------------- #

    def _appendData(self, obj):
        if obj is None:
            return
        if isinstance(obj, QQuickItem):
            obj.setParentItem(self._surface)
        elif obj.parent() is None:
            obj.setParent(self)
        self._data.append(obj)

    def _countData(self):
        return len(self._data)

    def _atData(self, index):
        return self._data[index]

    def _clearData(self):
        self._data.clear()

    # Named qsData rather than data: QQuickWindow already has a `data` list
    # property and QML resolved the default property to the base class one.
    qsData = ListProperty(QObject, _appendData, _countData, _atData, _clearData)

    def _getSurface(self):
        return self._surface

    # Exposed as qsSurface; the QML window types re-export it as `contentItem`.
    # A Python property named contentItem would compete with QQuickWindow's own
    # C++ property of that name, and QML picked the root item.
    qsSurface = Property(QObject, _getSurface, constant=True)

    # ---- attached ---------------------------------------------------------- #

    @staticmethod
    def qmlAttachedProperties(self, obj):
        return QsWindowAttached(obj)

    # ---- invokables -------------------------------------------------------- #

    @Slot(QObject, result="QVariant")
    def itemPosition(self, item):
        if not isinstance(item, QQuickItem):
            return QPointF(0, 0)
        return item.mapToItem(self._surface, QPointF(0, 0))

    @Slot(QObject, float, float, result="QVariant")
    def mapFromItem(self, item, x, y):
        if not isinstance(item, QQuickItem):
            return QPointF(x, y)
        return item.mapToItem(self._surface, QPointF(x, y))

    # ---- properties -------------------------------------------------------- #

    def _getScreen(self):
        return self._screen

    def _setScreen(self, value):
        if value is self._screen:
            return
        self._screen = value
        self.screenChanged.emit()

    def _getImplicitWidth(self):
        return self._implicitWidth

    def _setImplicitWidth(self, value):
        value = float(value)
        if value == self._implicitWidth:
            return
        self._implicitWidth = value
        self.implicitWidthChanged.emit()

    def _getImplicitHeight(self):
        return self._implicitHeight

    def _setImplicitHeight(self, value):
        value = float(value)
        if value == self._implicitHeight:
            return
        self._implicitHeight = value
        self.implicitHeightChanged.emit()

    def _getMask(self):
        return self._mask

    def _setMask(self, value):
        if value is self._mask:
            return
        self._mask = value
        self.maskChanged.emit()

    def _backingWindowVisible(self):
        return self.visibility() != QQuickWindow.Visibility.Hidden

    screen = Property(QObject, _getScreen, _setScreen, notify=screenChanged)
    implicitWidth = Property(float, _getImplicitWidth, _setImplicitWidth, notify=implicitWidthChanged)
    implicitHeight = Property(float, _getImplicitHeight, _setImplicitHeight, notify=implicitHeightChanged)
    mask = Property(QObject, _getMask, _setMask, notify=maskChanged)
    backingWindowVisible = Property(bool, _backingWindowVisible, notify=backingWindowVisibleChanged)


# --------------------------------------------------------------------------- #
# TransformWatcher
# --------------------------------------------------------------------------- #


@QmlElement
class TransformWatcher(QObject):
    """Emits `transformChanged` whenever the geometry of any item between `a`
    and `b` changes, so a binding that maps between them stays reactive."""

    aChanged = Signal()
    bChanged = Signal()
    transformChanged = Signal()

    _SIGNALS = ("xChanged", "yChanged", "widthChanged", "heightChanged", "scaleChanged", "rotationChanged", "parentChanged")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._a = None
        self._b = None
        self._watched = []
        self._serial = 0

    def _chain(self, item):
        out = []
        while isinstance(item, QQuickItem):
            out.append(item)
            item = item.parentItem()
        return out

    def _rewatch(self):
        for item in self._watched:
            for name in self._SIGNALS:
                try:
                    getattr(item, name).disconnect(self._bump)
                except (RuntimeError, TypeError):
                    pass
        self._watched = []
        seen = set()
        for item in self._chain(self._a) + self._chain(self._b):
            if id(item) in seen:
                continue
            seen.add(id(item))
            for name in self._SIGNALS:
                getattr(item, name).connect(self._bump)
            self._watched.append(item)
        self._bump()

    def _bump(self, *_):
        self._serial += 1
        self.transformChanged.emit()

    def _getA(self):
        return self._a

    def _setA(self, value):
        self._a = value
        self.aChanged.emit()
        self._rewatch()

    def _getB(self):
        return self._b

    def _setB(self, value):
        self._b = value
        self.bChanged.emit()
        self._rewatch()

    def _transform(self):
        return self._serial

    a = Property(QObject, _getA, _setA, notify=aChanged)
    b = Property(QObject, _getB, _setB, notify=bChanged)
    transform = Property(int, _transform, notify=transformChanged)
