"""`import Quickshell.Wayland` — enums plus an inert `WlrLayershell` attached type.

Layer-shell is a Wayland concept with no macOS analogue. The attached
properties are accepted and stored so upstream QML that sets them still
parses; the mac host places windows itself (see `OmarchyMac.MacWindow`).
"""

from enum import IntEnum

from PySide6.QtCore import Property, QEnum, QObject, Signal
from PySide6.QtQml import QmlAttached, QmlElement, QmlUncreatable

QML_IMPORT_NAME = "Quickshell.Wayland"
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
@QmlUncreatable("enum holder")
class WlrLayer(QObject):
    @QEnum
    class Enum(IntEnum):
        Background = 0
        Bottom = 1
        Top = 2
        Overlay = 3


@QmlElement
@QmlUncreatable("enum holder")
class WlrKeyboardFocus(QObject):
    # "None" is a Python keyword, so the member is built through the
    # functional API. QML still reads it as WlrKeyboardFocus.None.
    Enum = QEnum(IntEnum("Enum", {"None": 0, "Exclusive": 1, "OnDemand": 2}))


class WlrLayershellAttached(QObject):
    layerChanged = Signal()
    namespaceChanged = Signal()
    keyboardFocusChanged = Signal()
    exclusiveZoneChanged = Signal()
    exclusionModeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layer = 2
        self._namespace = ""
        self._keyboardFocus = 0
        self._exclusiveZone = 0
        self._exclusionMode = 0

    def _g(name):
        return lambda self: getattr(self, name)

    def _s(name, signal):
        def setter(self, value):
            setattr(self, name, value)
            getattr(self, signal).emit()
        return setter

    layer = Property(int, _g("_layer"), _s("_layer", "layerChanged"), notify=layerChanged)
    namespace = Property(str, _g("_namespace"), _s("_namespace", "namespaceChanged"), notify=namespaceChanged)
    keyboardFocus = Property(int, _g("_keyboardFocus"), _s("_keyboardFocus", "keyboardFocusChanged"), notify=keyboardFocusChanged)
    exclusiveZone = Property(int, _g("_exclusiveZone"), _s("_exclusiveZone", "exclusiveZoneChanged"), notify=exclusiveZoneChanged)
    exclusionMode = Property(int, _g("_exclusionMode"), _s("_exclusionMode", "exclusionModeChanged"), notify=exclusionModeChanged)


@QmlElement
@QmlAttached(WlrLayershellAttached)
@QmlUncreatable("attached properties only")
class WlrLayershell(QObject):
    @staticmethod
    def qmlAttachedProperties(self, obj):
        return WlrLayershellAttached(obj)
