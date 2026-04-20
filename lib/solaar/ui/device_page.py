## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Generic libadwaita device page. Subclasses override build_content()
to render a device-specific layout; the default implementation auto-
generates rows from the device's settings.
"""

import logging

import gi

from solaar.i18n import _
from solaar.ui.setting_rows import build_row_for_setting

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

logger = logging.getLogger(__name__)


class DevicePage(Adw.NavigationPage):
    """Default device page — device info header + auto-generated settings rows."""

    def __init__(self, device):
        super().__init__()
        self.device = device
        self.set_title(device.name or _("Device"))
        self.set_tag(f"device-{id(device)}")

        toolbar = Adw.ToolbarView.new()
        header = Adw.HeaderBar.new()
        toolbar.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow.new()
        scrolled.set_vexpand(True)
        clamp = Adw.Clamp.new()
        clamp.set_maximum_size(720)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)

        content = Gtk.Box.new(Gtk.Orientation.VERTICAL, 24)
        clamp.set_child(content)
        scrolled.set_child(clamp)
        toolbar.set_content(scrolled)

        content.append(self._build_header())
        for group in self.build_content():
            content.append(group)

        self.set_child(toolbar)

    def _build_header(self) -> Gtk.Widget:
        """Device illustration + name + battery/firmware summary."""
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("input-mouse-symbolic")
        icon.set_pixel_size(96)
        box.append(icon)

        title = Gtk.Label.new(self.device.name or _("Device"))
        title.add_css_class("title-1")
        box.append(title)

        subtitle_parts = []
        codename = getattr(self.device, "codename", None)
        if codename and codename != self.device.name:
            subtitle_parts.append(codename)
        protocol = getattr(self.device, "protocol", None)
        if protocol:
            subtitle_parts.append(f"HID++ {protocol}")
        if subtitle_parts:
            subtitle = Gtk.Label.new(" · ".join(subtitle_parts))
            subtitle.add_css_class("dim-label")
            box.append(subtitle)

        battery = self._battery_text()
        if battery:
            badge = Gtk.Label.new(battery)
            badge.add_css_class("caption")
            badge.add_css_class("accent")
            box.append(badge)

        return box

    def _battery_text(self):
        try:
            status = self.device.battery()
        except Exception:
            return None
        if status is None:
            return None
        try:
            level = status.level
        except AttributeError:
            level = None
        if level is None:
            return None
        return _("Battery: {level}%").format(level=level)

    def build_content(self):
        """Yield Adw.PreferencesGroup widgets. Override in subclasses for device-specific UI."""
        yield self._build_settings_group()

    def _build_settings_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup.new()
        group.set_title(_("Settings"))
        settings = getattr(self.device, "settings", None) or []
        any_added = False
        for setting in settings:
            row = build_row_for_setting(setting)
            if row is not None:
                group.add(row)
                any_added = True
        if not any_added:
            placeholder = Adw.ActionRow.new()
            placeholder.set_title(_("No configurable settings"))
            placeholder.set_subtitle(_("This device exposes no settings Solaar can show yet."))
            group.add(placeholder)
        return group
