## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Solaar libadwaita application — AdwApplicationWindow with a
navigation sidebar listing receivers/devices and a content pane
showing the selected device page.
"""

from __future__ import annotations

import logging

from typing import Optional

import gi

from solaar.i18n import _
from solaar.ui.pages import page_for_device

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # NOQA: E402
from gi.repository import Gio  # NOQA: E402
from gi.repository import GLib  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

logger = logging.getLogger(__name__)

APP_ID = "io.github.pwr_solaar.solaar"


_main_window: Optional["SolaarWindow"] = None
_app: Optional[Adw.Application] = None


def get_main_window():
    return _main_window


class _DeviceRow(Gtk.ListBoxRow):
    """Sidebar row. Carries a reference to the device so the selection handler
    can map it back to a page."""

    def __init__(self, device):
        super().__init__()
        self.device = device

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        icon_name = _icon_name_for(device)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        box.append(icon)

        text_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        title = Gtk.Label.new(device.name or _("Unknown device"))
        title.set_halign(Gtk.Align.START)
        title.add_css_class("heading")
        text_box.append(title)

        subtitle_text = getattr(device, "codename", None) or ""
        if subtitle_text:
            subtitle = Gtk.Label.new(str(subtitle_text))
            subtitle.set_halign(Gtk.Align.START)
            subtitle.add_css_class("caption")
            subtitle.add_css_class("dim-label")
            text_box.append(subtitle)

        box.append(text_box)
        self.set_child(box)


def _icon_name_for(device) -> str:
    kind = (getattr(device, "kind", None) or "").lower()
    mapping = {
        "mouse": "input-mouse-symbolic",
        "keyboard": "input-keyboard-symbolic",
        "touchpad": "input-touchpad-symbolic",
        "trackball": "input-mouse-symbolic",
        "headset": "audio-headphones-symbolic",
        "receiver": "network-wireless-symbolic",
    }
    return mapping.get(kind, "preferences-desktop-peripherals-symbolic")


class SolaarWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("Solaar")
        self.set_default_size(1000, 680)

        self._device_rows: dict[int, _DeviceRow] = {}
        self._device_pages: dict[int, Adw.NavigationPage] = {}

        self._split = Adw.NavigationSplitView.new()
        self._split.set_max_sidebar_width(300)
        self._split.set_min_sidebar_width(220)

        # Sidebar
        sidebar_page = Adw.NavigationPage.new(self._build_sidebar(), "Solaar")
        sidebar_page.set_tag("sidebar")
        self._split.set_sidebar(sidebar_page)

        # Content — NavigationView lets us push per-device pages. It must live
        # inside a NavigationPage because that's what NavigationSplitView.content
        # expects.
        self._content_stack = Adw.NavigationView.new()
        self._content_stack.push(self._build_placeholder())
        content_page = Adw.NavigationPage.new(self._content_stack, _("Solaar"))
        content_page.set_tag("content")
        self._split.set_content(content_page)

        self.set_content(self._split)

    def _build_sidebar(self) -> Gtk.Widget:
        toolbar = Adw.ToolbarView.new()
        header = Adw.HeaderBar.new()
        toolbar.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow.new()
        scrolled.set_vexpand(True)
        self._device_list = Gtk.ListBox.new()
        self._device_list.add_css_class("navigation-sidebar")
        self._device_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._device_list.connect("row-selected", self._on_row_selected)
        scrolled.set_child(self._device_list)
        toolbar.set_content(scrolled)
        return toolbar

    def _build_placeholder(self) -> Adw.NavigationPage:
        page = Adw.NavigationPage.new(Adw.StatusPage.new(), "placeholder")
        status = page.get_child()
        status.set_icon_name("input-mouse-symbolic")
        status.set_title(_("No device selected"))
        status.set_description(_("Select a receiver or device from the sidebar."))
        page.set_title(_("Solaar"))
        return page

    def _on_row_selected(self, _list, row):
        if row is None:
            return
        device = row.device
        page = self._device_pages.get(id(device))
        if page is None:
            try:
                page = page_for_device(device)
            except Exception:
                logger.exception("building page for %s", device)
                return
            self._device_pages[id(device)] = page
        # Replace the current page instead of stacking.
        self._content_stack.replace([page])

    # Called from status_changed on idle_add.
    def update_device(self, device, need_popup: bool, refresh: bool):
        key = id(device)
        if not getattr(device, "present", True):
            row = self._device_rows.pop(key, None)
            if row is not None:
                self._device_list.remove(row)
            page = self._device_pages.pop(key, None)
            if page is not None:
                logger.debug("device removed: %s", device)
            return

        row = self._device_rows.get(key)
        if row is None:
            row = _DeviceRow(device)
            self._device_rows[key] = row
            self._device_list.append(row)

        if need_popup:
            self.present()

        # If this is the currently-selected device, rebuild its page so new
        # settings show up.
        if refresh and key in self._device_pages:
            self._device_pages.pop(key)
            selected = self._device_list.get_selected_row()
            if selected is not None and selected.device is device:
                self._on_row_selected(self._device_list, selected)


def run_loop(startup_hook, shutdown_hook, use_tray: bool, show_window: bool):
    """Main entry point called from solaar.gtk."""
    global _app, _main_window

    Adw.init()
    _app = Adw.Application.new(APP_ID, Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    def _on_startup(app):
        logger.debug("startup")
        from solaar.ui import common as ui_common
        from solaar.ui import desktop_notifications

        ui_common.start_async()
        desktop_notifications.init()
        startup_hook()

    def _on_activate(app):
        global _main_window
        if _main_window is None:
            _main_window = SolaarWindow(application=app)
        if show_window:
            _main_window.present()

    def _on_shutdown(app):
        logger.debug("shutdown")
        from solaar.ui import common as ui_common
        from solaar.ui import desktop_notifications

        shutdown_hook()
        ui_common.stop_async()
        desktop_notifications.uninit()

    def _on_command_line(app, command_line):
        _on_activate(app)
        return 0

    _app.connect("startup", _on_startup)
    _app.connect("activate", _on_activate)
    _app.connect("shutdown", _on_shutdown)
    _app.connect("command-line", _on_command_line)

    _app.register()
    if _app.get_is_remote():
        print(_("Another Solaar process is already running so just expose its window"))
    _app.run()


def update_device(device, need_popup: bool, refresh: bool):
    """Thread-safe hook used by status_changed — schedules a UI update."""

    def _apply():
        if _main_window is not None:
            _main_window.update_device(device, need_popup, refresh)
        return False

    GLib.idle_add(_apply)
