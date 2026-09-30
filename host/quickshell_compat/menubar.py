"""`import OmarchyMac` — MenuBarItems: bar widgets as native menu bar items.

On this macOS the status item content is rendered by the system from a
remote proxy window, so a Qt view embedded in the item never gets exposed.
The host therefore mirrors: every widget runs unmodified in a hidden Qt Quick
window, `render()` grabs that window into an image and hands it to the
NSStatusBarButton, and clicks come back through `pressed` with the widget-
local point and the item's real on-screen origin (from the click event), so
popups anchored to the widget open under the menu bar item.
"""

import sys

from PySide6.QtCore import Property, QBuffer, QByteArray, QIODevice, QObject, Signal, Slot
from PySide6.QtQml import QmlElement, QmlSingleton

QML_IMPORT_NAME = "OmarchyMac"
QML_IMPORT_MAJOR_VERSION = 1

QT_LEFT, QT_RIGHT, QT_MIDDLE = 1, 2, 4
NS_LEFT_UP, NS_RIGHT_UP, NS_OTHER_UP = 2, 4, 26
NS_LEFT_UP_MASK, NS_RIGHT_UP_MASK, NS_OTHER_UP_MASK = 1 << 2, 1 << 4, 1 << 26


def _warn(message):
    sys.stderr.write(f"omarchy-shell-mac: {message}\n")


def _make_target_class():
    import objc
    from AppKit import NSObject

    class OmarchyMenuBarTarget(NSObject):
        def init(self):
            self = objc.super(OmarchyMenuBarTarget, self).init()
            self.callback = None
            return self

        @objc.typedSelector(b"v@:@")
        def clicked_(self, sender):
            if self.callback is not None:
                self.callback(sender)

    return OmarchyMenuBarTarget


@QmlElement
@QmlSingleton
class MenuBarItems(QObject):
    pressed = Signal(int, float, float, int)      # handle, localX, localY, Qt mouse button
    originChanged = Signal(int, float, float)     # handle, screen x, screen y (Qt coordinates)
    darkChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = {}
        self._byButton = {}
        self._next = 1
        self._target = None
        self._dark = False
        self._available = False
        try:
            import objc  # noqa: F401
            from AppKit import NSStatusBar  # noqa: F401
            self._available = True
        except ImportError:
            _warn("pyobjc is not installed; menubar mode is unavailable")

    def _ensureTarget(self):
        if self._target is None:
            cls = _make_target_class()
            self._target = cls.alloc().init()
            self._target.callback = self._onClick
        return self._target

    # ---- lifecycle -------------------------------------------------------- #

    @Slot(QObject, str, str, result=int)
    def create(self, window, pluginId, tooltip):
        if not self._available or window is None:
            return 0
        import objc
        from AppKit import NSStatusBar

        bar = NSStatusBar.systemStatusBar()
        item = bar.statusItemWithLength_(float(max(1, window.width())))
        if pluginId:
            item.setAutosaveName_(str(pluginId))
        button = item.button()
        button.setToolTip_(str(tooltip or ""))
        button.setTarget_(self._ensureTarget())
        button.setAction_("clicked:")
        button.sendActionOn_(NS_LEFT_UP_MASK | NS_RIGHT_UP_MASK | NS_OTHER_UP_MASK)
        handle = self._next
        self._next += 1
        self._items[handle] = {"item": item, "button": button, "window": window}
        self._byButton[objc.pyobjc_id(button)] = handle
        return handle

    @Slot(int)
    def remove(self, handle):
        entry = self._items.pop(int(handle), None)
        if entry is None:
            return
        import objc
        from AppKit import NSStatusBar

        self._byButton.pop(objc.pyobjc_id(entry["button"]), None)
        NSStatusBar.systemStatusBar().removeStatusItem_(entry["item"])

    @Slot(int)
    def render(self, handle):
        entry = self._items.get(int(handle))
        if entry is None:
            return
        window = entry["window"]
        image = window.grabWindow()
        if image.isNull():
            return
        from AppKit import NSData, NSImage

        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buf, "PNG")
        buf.close()
        data = NSData.dataWithBytes_length_(bytes(ba), len(ba))
        nsimage = NSImage.alloc().initWithData_(data)
        if nsimage is None:
            return
        dpr = image.devicePixelRatio() or 1.0
        nsimage.setSize_((image.width() / dpr, image.height() / dpr))
        nsimage.setTemplate_(False)
        entry["button"].setImage_(nsimage)
        entry["item"].setLength_(float(max(1, image.width() / dpr)))
        self._refreshAppearance(entry["button"])

    @Slot(int, str)
    def setToolTip(self, handle, text):
        entry = self._items.get(int(handle))
        if entry is not None:
            entry["button"].setToolTip_(str(text or ""))

    @Slot(result=float)
    def thickness(self):
        if not self._available:
            return 22.0
        from AppKit import NSStatusBar

        return float(NSStatusBar.systemStatusBar().thickness())

    def _refreshAppearance(self, button):
        try:
            name = str(button.effectiveAppearance().name())
        except Exception:  # noqa: BLE001
            return
        dark = "Dark" in name
        if dark != self._dark:
            self._dark = dark
            self.darkChanged.emit()

    def _getDark(self):
        return self._dark

    def _getAvailable(self):
        return self._available

    dark = Property(bool, _getDark, notify=darkChanged)
    available = Property(bool, _getAvailable, constant=True)

    # ---- clicks ----------------------------------------------------------- #

    def _onClick(self, sender):
        import objc
        from AppKit import NSApplication, NSEvent, NSScreen

        handle = self._byButton.get(objc.pyobjc_id(sender))
        if handle is None:
            return
        event = NSApplication.sharedApplication().currentEvent()
        button = QT_LEFT
        if event is not None:
            kind = int(event.type())
            if kind == NS_RIGHT_UP:
                button = QT_RIGHT
            elif kind == NS_OTHER_UP:
                button = QT_MIDDLE
        frame = sender.frame()
        if event is not None:
            loc = event.locationInWindow()
            local_x = float(loc.x - frame.origin.x)
            local_y_cocoa = float(loc.y - frame.origin.y)
        else:
            local_x = frame.size.width / 2
            local_y_cocoa = frame.size.height / 2
        local_y = float(frame.size.height - local_y_cocoa)
        mouse = NSEvent.mouseLocation()
        screens = NSScreen.screens()
        primary_height = float(screens[0].frame().size.height) if screens else 0.0
        origin_x = float(mouse.x - local_x)
        top_cocoa = float(mouse.y + (frame.size.height - local_y_cocoa))
        origin_y = primary_height - top_cocoa
        self.originChanged.emit(handle, origin_x, origin_y)
        self.pressed.emit(handle, local_x, local_y, button)
