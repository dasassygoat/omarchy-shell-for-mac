# Vendored Omarchy QML

`qs/Commons` and `qs/Ui` are copied from `omacom/omarchy` (branch and commit
recorded in `../upstream/`). Pristine copies live in `../upstream/pristine/`
so `diff -r` shows exactly what the Mac host changes.

Replaced files:

| File | Why |
|---|---|
| `qs/Ui/KeyboardPanel.qml` | upstream is a layer-shell surface; the Mac version is a frameless top-level window under the anchor, dismissed when it loses activation |

Everything else in `qs/` is pristine. `qs/Ui/OverlayWindow.qml`,
`qs/Ui/PopupCard.qml` and `qs/Ui/SpeedTestOverlay.qml` load unchanged on top
of the `PanelWindow` / `PopupWindow` / `Region` implementations in
`Quickshell/`.

# The `Quickshell` module

`Quickshell/` is the QML half of the compatibility layer; the Python half is
`host/quickshell_compat/`. Both register under the same `Quickshell` URI.

| Type | Notes |
|---|---|
| `QsWindow` (Python) | `QQuickWindow` subclass with `screen`, `implicitWidth/Height`, `mask`, `backingWindowVisible`, `itemPosition()`, and the `QsWindow.window` / `QsWindow.contentItem` attached properties. Its `contentItem` is a full-size child of the real root item, because Qt 6.11 never re-shows a root item once hidden and upstream's `OverlayWindow` toggles `contentItem.visible` on every open. |
| `PanelWindow` | Layer-shell geometry (anchors, margins, implicit size) mapped onto a frameless NSWindow. `WlrLayershell.layer` picks the NSWindow level, `keyboardFocus` decides activation, `mask` becomes an input mask (empty mask = click-through). `exclusiveZone` is accepted and ignored. Registers itself as unconstrained so AppKit does not push it below the menu bar. |
| `PopupWindow` | Positioned from `anchor` (window/item, rect, edges, gravity, Slide adjustment), raised to popup level and activated when shown so `HyprlandFocusGrab` can dismiss it. |
| `FloatingWindow` | Plain window. |
| `Region` | Rect or item geometry plus child regions with `Intersection` ops. |
| enums (Python) | `ExclusionMode`, `Edges`, `PopupAdjustment`, `Intersection`, `RegionShape`, `WlrLayer`, `WlrKeyboardFocus`. |

Window flags on these windows never change after the first show: Qt recreates
the native window on a flags change and, on Qt 6.11, leaves the root item
hidden afterwards. Focus and click-through are applied natively instead.
