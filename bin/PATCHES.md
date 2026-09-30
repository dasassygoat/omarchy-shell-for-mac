# Vendored Omarchy CLI

`omarchy-plugin-*` and `omarchy-git-url-check` are copied from
`omacom/omarchy/bin` (commit in `../upstream/OMARCHY_COMMIT`; pristine copies
in `../upstream/pristine/bin/`). Each gets a preamble that puts this `bin/`
first on `PATH` and defaults `OMARCHY_PATH` to the checkout, plus:

| Script | Change |
|---|---|
| all | preamble (PATH / OMARCHY_PATH) |
| `omarchy-plugin-add` | `gum` → `omarchy-gum`; guard an empty-array expansion (`set -u` on bash 3.2) |
| `omarchy-plugin-remove` | `gum` → `omarchy-gum`; BSD `find` has no `-printf` |
| `omarchy-plugin-update` | `gum` → `omarchy-gum`; `omarchy-cmd-present delta` → `command -v delta` |
| `omarchy-plugin-catalog` | scans `$OMARCHY_PATH/plugins` (flat) instead of `shell/plugins`; honours `OMARCHY_MAC_PLUGIN_DIRS` |

Mac-only additions: `omarchy` (dispatcher for `omarchy plugin …` / `omarchy
shell …`), `omarchy-gum` (gum stand-in), `omarchy-shell` (IPC client) and
`omarchy-shell-mac` (host launcher).

Not vendored: `omarchy-plugin-clone` (needs `rg` and GNU `sed -i`; the clone
bookkeeping in shell.json is also not implemented on the host).

The scripts talk to the running shell through `omarchy-shell shell
listPlugins | rescanPlugins | enablePlugin | setPluginEnabled | moveBarWidget`,
implemented in `shell/shell.qml`.
