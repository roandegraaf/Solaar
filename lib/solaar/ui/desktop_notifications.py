## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Optional libnotify desktop notifications.

The Notify library is GTK-version independent, so this module stays the
same across the GTK3 → GTK4 migration. We drop the old `icons` helper and
pick an icon name from the device kind instead.
"""

import importlib
import logging

from solaar import NAME
from solaar.i18n import _

logger = logging.getLogger(__name__)


def notifications_available():
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


_DEVICE_KIND_ICONS = {
    "mouse": "input-mouse",
    "keyboard": "input-keyboard",
    "touchpad": "input-touchpad",
    "trackball": "input-mouse",
    "headset": "audio-headphones",
    "tablet": "input-tablet",
}


def _icon_for_kind(kind):
    return _DEVICE_KIND_ICONS.get(str(kind).lower(), "preferences-desktop-peripherals")


if available:
    from gi.repository import GLib
    from gi.repository import Notify

    _notifications = {}

    def init():
        global available
        if available and not Notify.is_initted():
            logger.info("starting desktop notifications")
            try:
                return Notify.init(NAME.lower())
            except Exception:
                logger.exception("initializing desktop notifications")
                available = False
        return available and Notify.is_initted()

    def uninit():
        if available and Notify.is_initted():
            logger.info("stopping desktop notifications")
            _notifications.clear()
            Notify.uninit()

    def alert(reason, icon=None):
        if not available or not Notify.is_initted():
            return
        n = _notifications.get(NAME.lower())
        if n is None:
            n = _notifications[NAME.lower()] = Notify.Notification()
        icon_name = icon or "preferences-desktop-peripherals"
        n.update(NAME.lower(), reason, icon_name)
        n.set_urgency(Notify.Urgency.NORMAL)
        n.set_hint("desktop-entry", GLib.Variant("s", NAME.lower()))
        try:
            n.show()
        except Exception:
            logger.exception("showing %s", n)

    def show(dev, reason=None, icon=None, progress=None):
        if not available or not Notify.is_initted():
            return
        summary = dev.name
        n = _notifications.get(summary)
        if n is None:
            n = _notifications[summary] = Notify.Notification()
        message = reason if reason else _("unspecified reason")
        icon_name = icon or _icon_for_kind(getattr(dev, "kind", None))
        n.update(summary, message, icon_name)
        n.set_urgency(Notify.Urgency.NORMAL)
        n.set_hint("desktop-entry", GLib.Variant("s", NAME.lower()))
        if progress:
            n.set_hint("value", GLib.Variant("i", progress))
        try:
            return n.show()
        except Exception:
            logger.exception("showing %s", n)

else:

    def init():
        return False

    def uninit():
        return None

    def alert(reason, icon=None):
        return None

    def show(dev, reason=None, icon=None, progress=None):
        return None
