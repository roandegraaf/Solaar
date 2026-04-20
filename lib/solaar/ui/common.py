## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

import logging

from enum import Enum
from typing import Tuple

import gi

from solaar.i18n import _
from solaar.tasks import TaskRunner

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # NOQA: E402
from gi.repository import GLib  # NOQA: E402

logger = logging.getLogger(__name__)


class ErrorReason(Enum):
    PERMISSIONS = "Permissions"
    NO_DEVICE = "No device"
    UNPAIR = "Unpair"


def _create_error_text(reason: ErrorReason, object_) -> Tuple[str, str]:
    if reason == ErrorReason.PERMISSIONS:
        title = _("Permissions error")
        text = (
            _("Found a Logitech receiver or device (%s), but did not have permission to open it.") % object_
            + "\n\n"
            + _("If you've just installed Solaar, try disconnecting the receiver or device and then reconnecting it.")
        )
    elif reason == ErrorReason.NO_DEVICE:
        title = _("Cannot connect to device error")
        text = (
            _("Found a Logitech receiver or device at %s, but encountered an error connecting to it.") % object_
            + "\n\n"
            + _("Try disconnecting the device and then reconnecting it or turning it off and then on.")
        )
    elif reason == ErrorReason.UNPAIR:
        title = _("Unpairing failed")
        text = (
            _("Failed to unpair %{device} from %{receiver}.").format(
                device=object_.name,
                receiver=object_.receiver.name,
            )
            + "\n\n"
            + _("The receiver returned an error, with no further details.")
        )
    else:
        raise Exception("ui.error_dialog: don't know how to handle (%s, %s)", reason.name, object_)
    return title, text


def _error_dialog(reason: ErrorReason, object_):
    logger.error("error: %s %s", reason, object_)
    title, text = _create_error_text(reason, object_)

    # GTK4: Adw.AlertDialog replaces Gtk.MessageDialog. Parent is resolved at present-time.
    from solaar.ui.app import get_main_window

    dialog = Adw.AlertDialog.new(title, text)
    dialog.add_response("close", _("Close"))
    dialog.set_default_response("close")
    parent = get_main_window()
    dialog.present(parent)


def error_dialog(reason: ErrorReason, object_):
    GLib.idle_add(_error_dialog, reason, object_)


_task_runner = None


def start_async():
    global _task_runner
    _task_runner = TaskRunner("AsyncUI")
    _task_runner.start()


def stop_async():
    global _task_runner
    if _task_runner is not None:
        _task_runner.stop()
        _task_runner = None


def ui_async(function, *args, **kwargs):
    """Runs a function asynchronously on the UI task runner."""
    if _task_runner:
        _task_runner(function, *args, **kwargs)
