## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Factory mapping logitech_receiver Settings to libadwaita preference rows."""

import logging

from typing import Optional

import gi

from logitech_receiver import settings_validator

from solaar.ui.common import ui_async

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # NOQA: E402
from gi.repository import GLib  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

logger = logging.getLogger(__name__)


def _apply_write(setting, value, row):
    try:
        result = setting.write(value)
    except Exception:
        logger.exception("writing %s=%r failed", setting.name, value)
        result = None

    def _done():
        if result is None:
            row.add_css_class("error")
            row.set_subtitle(row.get_subtitle() + "  ✗")
        else:
            row.remove_css_class("error")
        return False

    GLib.idle_add(_done)


def _async_write(setting, value, row):
    ui_async(_apply_write, setting, value, row)


def _build_boolean_row(setting) -> Adw.SwitchRow:
    row = Adw.SwitchRow.new()
    row.set_title(setting.label or setting.name)
    if setting.description:
        row.set_subtitle(setting.description)
    current = setting.read()
    row.set_active(bool(current))
    row.connect("notify::active", lambda r, _p: _async_write(setting, r.get_active(), r))
    return row


def _coarse_dpi_choices(choices, current, step=100):
    """Drop DPI list to multiples of `step`. The device supports every 50-DPI
    step (or finer), which floods the dropdown. Keep the current value in the
    list even when it isn't a multiple of the step, so the combo can select it.
    """
    coarse = [c for c in choices if int(c) % step == 0]
    if current is not None and current not in coarse:
        try:
            coarse = sorted([*coarse, current], key=int)
        except Exception:
            pass
    return coarse


def _is_dpi_key(setting_name, key=None) -> bool:
    if key is not None:
        return str(key).upper() in ("X", "Y") and setting_name.startswith("dpi")
    return setting_name.startswith("dpi")


def _build_choice_row(setting) -> Adw.ComboRow:
    row = Adw.ComboRow.new()
    row.set_title(setting.label or setting.name)
    if setting.description:
        row.set_subtitle(setting.description)

    current = setting.read()
    values = list(setting.choices)
    if _is_dpi_key(setting.name):
        values = _coarse_dpi_choices(values, current)

    model = Gtk.StringList.new([str(choice) for choice in values])
    row.set_model(model)

    try:
        idx = values.index(current)
    except ValueError:
        idx = 0
    row.set_selected(idx)

    def _on_selected(r, _p):
        selected = r.get_selected()
        if 0 <= selected < len(values):
            _async_write(setting, values[selected], r)

    row.connect("notify::selected", _on_selected)
    return row


def _build_range_row(setting) -> Adw.SpinRow:
    validator = setting._validator
    lo, hi = validator.min_value, validator.max_value
    row = Adw.SpinRow.new_with_range(float(lo), float(hi), 1.0)
    row.set_title(setting.label or setting.name)
    if setting.description:
        row.set_subtitle(setting.description)
    current = setting.read()
    if current is not None:
        row.set_value(float(current))

    def _on_changed(spinrow, _p):
        _async_write(setting, int(spinrow.get_value()), spinrow)

    row.connect("notify::value", _on_changed)
    return row


def _build_choices_map_row(setting) -> Adw.ExpanderRow:
    """DPI X/Y/LOD, Backlight etc. — one group of sub-rows."""
    row = Adw.ExpanderRow.new()
    row.set_title(setting.label or setting.name)
    if setting.description:
        row.set_subtitle(setting.description)

    value = setting.read() or {}
    for key, choices in setting._validator.choices.items():
        sub = Adw.ComboRow.new()
        sub.set_title(str(key))
        values = list(choices)
        current = value.get(key) if isinstance(value, dict) else None
        if _is_dpi_key(setting.name, key):
            values = _coarse_dpi_choices(values, current)
        model = Gtk.StringList.new([str(c) for c in values])
        sub.set_model(model)
        try:
            idx = values.index(current)
        except (ValueError, AttributeError):
            idx = 0
        sub.set_selected(idx)

        def _make_handler(k, vs):
            def _on_selected(r, _p):
                selected = r.get_selected()
                if 0 <= selected < len(vs):
                    ui_async(setting.write_key_value, k, vs[selected])

            return _on_selected

        sub.connect("notify::selected", _make_handler(key, values))
        row.add_row(sub)
    return row


def build_row_for_setting(setting) -> Optional[Gtk.Widget]:
    """Return a PreferencesRow widget for `setting`, or None if unsupported."""
    validator = getattr(setting, "_validator", None)
    if validator is None:
        return None

    kind_cls = type(validator)
    try:
        if kind_cls is settings_validator.BooleanValidator or issubclass(kind_cls, settings_validator.BooleanValidator):
            return _build_boolean_row(setting)
        if issubclass(kind_cls, settings_validator.ChoicesMapValidator):
            return _build_choices_map_row(setting)
        if issubclass(kind_cls, settings_validator.ChoicesValidator):
            return _build_choice_row(setting)
        if issubclass(kind_cls, settings_validator.RangeValidator):
            return _build_range_row(setting)
    except Exception:
        logger.exception("building row for %s", setting.name)
        return None

    logger.debug("no libadwaita row for %s (%s)", setting.name, kind_cls.__name__)
    return None
