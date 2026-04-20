## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Pro X 2 / Pro X Superlight mouse page — Logi Options+ style."""

from __future__ import annotations

import logging

import gi

from solaar.i18n import _
from solaar.ui.device_page import DevicePage
from solaar.ui.setting_rows import build_row_for_setting

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

logger = logging.getLogger(__name__)


# Setting names the Pro X 2 page surfaces as primary controls (in order).
# Everything else falls into an "Advanced" group via build_row_for_setting.
_PRIMARY_SETTINGS = ("dpi_extended", "dpi", "report_rate_extended", "report_rate", "onboard_profiles")


class ProX2Page(DevicePage):
    def build_content(self):
        primary = Adw.PreferencesGroup.new()
        primary.set_title(_("Performance"))
        primary.set_description(_("Core mouse settings that match Logi Options+"))

        settings_by_name = {s.name: s for s in getattr(self.device, "settings", []) or []}
        advanced_settings = list(settings_by_name.values())

        added_primary = False
        for name in _PRIMARY_SETTINGS:
            setting = settings_by_name.get(name)
            if setting is None:
                continue
            row = build_row_for_setting(setting)
            if row is not None:
                primary.add(row)
                added_primary = True
                if setting in advanced_settings:
                    advanced_settings.remove(setting)

        if not added_primary:
            placeholder = Adw.ActionRow.new()
            placeholder.set_title(_("No performance settings available"))
            placeholder.set_subtitle(_("Waiting for device to report its features."))
            primary.add(placeholder)

        yield primary

        if advanced_settings:
            advanced = Adw.PreferencesGroup.new()
            advanced.set_title(_("Advanced"))
            for setting in advanced_settings:
                row = build_row_for_setting(setting)
                if row is not None:
                    advanced.add(row)
            yield advanced

        yield self._build_info_group()

    def _build_info_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup.new()
        group.set_title(_("Device"))

        wpid = getattr(self.device, "wpid", None)
        if wpid:
            row = Adw.ActionRow.new()
            row.set_title(_("Wireless ID"))
            row.set_subtitle(str(wpid))
            group.add(row)

        serial = getattr(self.device, "serial", None)
        if serial:
            row = Adw.ActionRow.new()
            row.set_title(_("Serial"))
            row.set_subtitle(str(serial))
            group.add(row)

        fw_list = getattr(self.device, "firmware", None) or []
        for fw in fw_list:
            row = Adw.ActionRow.new()
            label = getattr(fw, "kind", None) or _("Firmware")
            version = getattr(fw, "version", None) or ""
            row.set_title(str(label))
            row.set_subtitle(str(version))
            group.add(row)

        icon = Gtk.Image.new_from_icon_name("help-about-symbolic")
        icon.set_pixel_size(16)
        return group
