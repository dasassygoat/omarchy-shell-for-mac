"""Quickshell compatibility layer.

Importing this package registers the QML modules that Omarchy plugins import
(`Quickshell`, `Quickshell.Io`, `Quickshell.Hyprland`, `Quickshell.Wayland`)
plus the host-only `OmarchyMac` module. Registration happens at import time
through the `QmlElement` decorators, so import this before the QML engine
loads anything.
"""

from . import core, io, hyprland, wayland, mac  # noqa: F401  (side effects)

__all__ = ["core", "io", "hyprland", "wayland", "mac"]
