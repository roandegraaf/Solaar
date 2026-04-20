## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Solaar UI package — GTK4 / libadwaita.

External callers (listener, gtk.py, CLI remote bridge) use:
- run_loop(startup, shutdown, use_tray, show_window)
- status_changed(device, alert, reason, refresh)
- setting_changed(device, setting_class, vals)
- common.error_dialog(reason, object_)
"""

from __future__ import annotations

import logging

import gi

from logitech_receiver.common import Alert

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # NOQA: E402

from . import common  # NOQA: E402
from . import desktop_notifications  # NOQA: E402
from .app import run_loop  # NOQA: E402
from .app import update_device as _ui_update_device  # NOQA: E402

logger = logging.getLogger(__name__)


__all__ = ["run_loop", "status_changed", "setting_changed", "common", "desktop_notifications"]


def _status_changed(device, alert, reason, refresh):
    if device is None:
        logger.debug("status changed on nil device: %s (%s) %s", device, alert, reason)
        return
    logger.debug("status changed: %s (%s) %s", device, alert, reason)
    if alert is None:
        alert = Alert.NONE

    need_popup = bool(alert & Alert.SHOW_WINDOW)
    _ui_update_device(device, need_popup, refresh)

    if alert & (Alert.NOTIFICATION | Alert.ATTENTION):
        desktop_notifications.show(device, reason)


def status_changed(device, alert=Alert.NONE, reason=None, refresh=False):
    GLib.idle_add(_status_changed, device, alert, reason, refresh)


def setting_changed(device, setting_class, vals):
    """Hook invoked when a device's setting value changes.

    Previously recorded the new value in the GTK3 config_panel to avoid
    clobbering the UI while the user was mid-edit. The libadwaita rows
    drive their state from the setting's current value directly, so this
    is currently a no-op. Kept as the public hook wired into listener.
    """
    logger.debug("setting_changed: %s %s = %r", device, getattr(setting_class, "name", setting_class), vals)
