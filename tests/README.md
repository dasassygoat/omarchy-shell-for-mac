# Manual test setup

```bash
OMARCHY_MAC_CONFIG=tests/shell.json OMARCHY_MAC_PLUGIN_DIRS=tests/plugins bin/omarchy-shell-mac
bin/omarchy-shell osd show '{"icon":"volume","message":"50%","value":"50","max":"100","duration":"3000"}'
bin/omarchy-shell shell toggle omarchy.reminders
bin/omarchy-shell mac.popupcard-probe toggle
bin/omarchy-shell shell debugWindows
```

`OMARCHY_MAC_CONFIG` keeps the run away from `~/.config/omarchy/shell.json`;
`OMARCHY_MAC_PLUGIN_DIRS` adds `tests/plugins` as a third-party plugin root.

Menu bar mode (must run outside any sandbox for the items to appear):

```bash
OMARCHY_MAC_CONFIG=tests/shell-menubar.json OMARCHY_MAC_PLUGIN_DIRS=tests/plugins bin/omarchy-shell-mac
```
