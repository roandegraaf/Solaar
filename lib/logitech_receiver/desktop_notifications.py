## Copyright (C) 2024 Solaar contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Notification helper used by logitech_receiver (e.g. the DPI-sliding
button hook). GTK version-agnostic: talks to libnotify directly and
uses generic freedesktop icon names.
"""

import importlib
import logging

logger = logging.getLogger(__name__)


def notifications_available():
    """Return True when libnotify Python bindings can be imported."""
    try:
        import gi

        gi.require_version("Notify", "0.7")
        importlib.util.find_spec("gi.repository.GLib")
        importlib.util.find_spec("gi.repository.Notify")
        return True
    except (ValueError, ImportError) as e:
        logger.warning("Notification service is not available: %s", e)
        return False


available = notifications_available()


_KIND_ICON = {
    "mouse": "input-mouse",
    "keyboard": "input-keyboard",
    "numpad": "input-keyboard",
    "touchpad": "input-touchpad",
    "trackball": "input-mouse",
    "headset": "audio-headphones",
    "tablet": "input-tablet",
}


def _icon_for_kind(kind):
    return _KIND_ICON.get(str(kind).lower(), "preferences-desktop-peripherals")


if available:
    from gi.repository import GLib
    from gi.repository import Notify

    _notifications = {}

    def init():
        global available
        if available and not Notify.is_initted():
            logger.info("starting desktop notifications")
            try:
                return Notify.init("solaar")
            except Exception:
                logger.exception("initializing desktop notifications")
                available = False
        return available and Notify.is_initted()

    def uninit():
        if available and Notify.is_initted():
            logger.info("stopping desktop notifications")
            _notifications.clear()
            Notify.uninit()

    def show(dev, message: str, icon=None):
        if not available or not (Notify.is_initted() or init()):
            return
        summary = dev.name
        n = _notifications.get(summary)
        if n is None:
            n = _notifications[summary] = Notify.Notification()
        icon_name = icon if icon else _icon_for_kind(getattr(dev, "kind", None))
        n.update(summary, message, icon_name)
        n.set_urgency(Notify.Urgency.NORMAL)
        n.set_hint("desktop-entry", GLib.Variant("s", "solaar"))
        try:
            return n.show()
        except Exception:
            logger.exception("showing %s", n)

else:

    def init():
        return False

    def uninit():
        return None

    def show(dev, reason=None, icon=None):
        return None
