# omarchy-shell-mac

A macOS host that runs **unmodified Omarchy shell plugins**.

[Omarchy](https://omarchy.org) (Arch + Hyprland) ships its desktop shell as one
long-lived [Quickshell](https://quickshell.org) process, and everything on
screen is a plugin: a directory with a `manifest.json` and QML entry points.
Quickshell only builds on Linux, but the plugins themselves are QtQuick plus a
thin slice of Quickshell's API. This project provides that slice on macOS, so a
plugin repo cloned from Omarchy or its marketplace loads as-is.

Proof points, all byte-for-byte copies of Omarchy's first-party plugins
(branch and commit in `upstream/`):

- `plugins/omarchy.clock/` (bar-widget): renders in the bar, its calendar
  popup opens, keyboard navigation works, format changes persist to
  `~/.config/omarchy/shell.json` exactly as on Linux.
- `plugins/omarchy.osd/` (panel): `omarchy-shell osd show '{...}'` draws the
  on-screen display above the Dock, click-through, and hides on its timer.
- `plugins/omarchy.reminders/` (overlay): a full-screen scrim with a
  keyboard-driven card, summoned with `omarchy-shell shell toggle
  omarchy.reminders`, taking keyboard focus like a layer-shell overlay.
- `tests/plugins/mac.popupcard-probe/` exercises upstream's `PopupCard`
  (a `PopupWindow` anchored to a bar button, dismissed on outside click).

## Layout

| Path | What it is |
|---|---|
| `host/quickshell_compat/` | Python (PySide6) half of the QML modules plugins import: `Quickshell` (singleton, `SystemClock`, `QsWindow`, enums), `Quickshell.Io`, `Quickshell.Hyprland` (inert singleton, working `HyprlandFocusGrab`), `Quickshell.Wayland` (inert), plus the host-only `OmarchyMac` |
| `qml/Quickshell/` | QML half of the `Quickshell` module: `PanelWindow`, `PopupWindow`, `FloatingWindow`, `Region`. See `qml/PATCHES.md` |
| `host/ipc.py` | Unix-socket IPC speaking Omarchy's `omarchy-shell` wire protocol |
| `host/main.py` | Entry point (`run` / `ipc`) |
| `qml/qs/Commons`, `qml/qs/Ui` | Omarchy's shared QML, vendored. See `qml/PATCHES.md` for the files rebuilt for macOS |
| `shell/` | The Mac shell root and bar (the parts of upstream `shell.qml` / `Bar.qml` a plugin can observe) |
| `plugins/` | Bundled first-party plugins (unmodified upstream copies) |
| `config/shell.json` | Default layout; `~/.config/omarchy/shell.json` overrides it, same as upstream |
| `upstream/` | Provenance: Omarchy commit, license, pristine copies of the vendored QML |

Third-party plugins go in `~/.config/omarchy/plugins/<id>/`, the same path
Omarchy uses.

## Run

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
bin/omarchy-shell-mac
```

The bar appears along the top edge of the main display, directly under the
macOS menu bar (macOS does not let a window cover the menu bar; set the menu
bar to auto-hide if you want the bar at the very top). The host has no Dock
icon.

Talk to it with the same command Omarchy scripts use:

```bash
bin/omarchy-shell shell ping
bin/omarchy-shell shell listPlugins
bin/omarchy-shell omarchy.clock toggle
bin/omarchy-shell omarchy.clock cycleFormat
bin/omarchy-shell shell summon omarchy.clock
bin/omarchy-shell osd show '{"icon":"volume","message":"50%","value":"50","max":"100","duration":"2000"}'
bin/omarchy-shell shell toggle omarchy.reminders
bin/omarchy-shell shell debugWindows
bin/omarchy-shell shell nativeWindows
bin/omarchy-shell shell quit
```

Environment:

- `OMARCHY_MAC_FONT` — font family for the bar and panels (default: first of
  JetBrainsMono Nerd Font, JetBrains Mono, Menlo that is installed). Omarchy's
  icons are Nerd Font glyphs, so install a Nerd Font for them to render.
- `OMARCHY_SHELL_MAC_SOCKET` — IPC socket path.
- `OMARCHY_MAC_CONFIG` — use this file instead of `~/.config/omarchy/shell.json`.
- `OMARCHY_MAC_PLUGIN_DIRS` — extra third-party plugin roots, colon separated.
- `OMARCHY_MAC_DEBUG_FOCUS=1` — log window activation decisions.

`config/shell.json` accepts an extra `mac` block (`cornerRadius`, `gapsOut`,
`font`) for the values Omarchy reads from Hyprland.

## What works, what does not

Plugin kinds `bar-widget` (with its own `Panel`) and `service` load when the
plugin sticks to QtQuick, `Quickshell` (`env`, `execDetached`, `screens`,
`SystemClock`), `Quickshell.Io` (`Process`, `FileView`, `IpcHandler`) and
`qs.Commons` / `qs.Ui`. That covers the clock, weather, elsewhen, tailscale and
agents style of widget.

Not implemented yet:

- `PanelWindow` / `PopupWindow` (so `panel`, `overlay`, `menu`, `bar` kinds and
  the `OverlayWindow` / `PopupCard` UI helpers)
- Linux service modules: `Quickshell.Services.*` (Pipewire, UPower, Mpris,
  SystemTray, Notifications, Polkit, Pam), `Quickshell.Bluetooth`,
  `Quickshell.Networking`. These need macOS-backed implementations.
- Hyprland workspaces / focused window (the `Hyprland` singleton is inert)
- Multi-monitor bars, vertical bars, hot reload of plugin files
- The `omarchy plugin add/enable/...` CLI (upstream's bash scripts are close to
  portable; not vendored yet)

Anything that shells out to `hyprctl`, `pacman`, `wl-copy` and friends fails
at the command, not in QML.
