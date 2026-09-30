# Vendored Omarchy QML

`qs/Commons` and `qs/Ui` are copied from `omacom/omarchy` (branch and commit
recorded in `../upstream/`). Pristine copies live in `../upstream/pristine/`
so `diff -r` shows exactly what the Mac host changes.

Replaced files (Wayland/Hyprland-specific windows rebuilt on QtQuick Window):

| File | Why |
|---|---|
| `qs/Ui/KeyboardPanel.qml` | upstream is a layer-shell surface; Mac version is a frameless top-level window under the anchor |

Files still pristine but not loadable on macOS yet (they reference
`PanelWindow` / `PopupWindow` / layer-shell attached properties that the
compat layer does not implement): `qs/Ui/OverlayWindow.qml`,
`qs/Ui/PopupCard.qml`, `qs/Ui/SpeedTestOverlay.qml`. Plugins that do not use
them are unaffected.
