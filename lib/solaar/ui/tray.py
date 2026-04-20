## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""System tray icon via the StatusNotifierItem D-Bus spec.

GTK4 dropped `GtkStatusIcon` and the standard AyatanaAppIndicator3 binding
depends on GTK3, which conflicts with the main libadwaita UI. Instead we
export a minimal StatusNotifierItem directly via Gio.DBusConnection. Works
with the KDE Plasma system tray out of the box and with GNOME when the
'AppIndicator and KStatusNotifierItem Support' extension is enabled (ships
on by default on Bazzite and similar distros).

Spec: https://specifications.freedesktop.org/sni-spec/latest/
Menu spec: https://specifications.freedesktop.org/dbusmenu-spec/latest/
"""

from __future__ import annotations

import logging
import os

from typing import Callable
from typing import Optional

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio  # NOQA: E402
from gi.repository import GLib  # NOQA: E402

logger = logging.getLogger(__name__)


_SNI_INTERFACE_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

_DBUSMENU_INTERFACE_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in" name="parentId"/>
      <arg type="i" direction="in" name="recursionDepth"/>
      <arg type="as" direction="in" name="propertyNames"/>
      <arg type="u" direction="out" name="revision"/>
      <arg type="(ia{sv}av)" direction="out" name="layout"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in" name="ids"/>
      <arg type="as" direction="in" name="propertyNames"/>
      <arg type="a(ia{sv})" direction="out" name="properties"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in" name="id"/>
      <arg type="s" direction="in" name="name"/>
      <arg type="v" direction="out" name="value"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in" name="id"/>
      <arg type="s" direction="in" name="eventId"/>
      <arg type="v" direction="in" name="data"/>
      <arg type="u" direction="in" name="timestamp"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" direction="in" name="id"/>
      <arg type="b" direction="out" name="needUpdate"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
  </interface>
</node>
"""


class _Tray:
    """Single-app tray. Owns an object path per instance so multiple Solaar
    instances wouldn't collide, though the systemd unit enforces single-run."""

    OBJECT_PATH = "/StatusNotifierItem"
    MENU_PATH = "/MenuBar"

    def __init__(self):
        self._conn: Optional[Gio.DBusConnection] = None
        self._sni_reg_id = 0
        self._menu_reg_id = 0
        self._bus_name_id = 0
        self._on_activate: Optional[Callable[[], None]] = None
        self._on_quit: Optional[Callable[[], None]] = None
        self._icon_name = "solaar"
        self._title = "Solaar"
        self._status = "Active"
        self._window_visible = False

        # Menu items — id 0 is the root, 1..N are leaf items.
        self._menu_items = [
            {"id": 1, "label": "Show Solaar", "event": "show"},
            {"id": 2, "label": "Quit", "event": "quit"},
        ]
        self._menu_revision = 0

    # ---------- public API (called from app.py) ----------

    def init(self, on_activate, on_quit):
        """Start exporting the tray on the session bus."""
        self._on_activate = on_activate
        self._on_quit = on_quit

        try:
            self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            logger.exception("tray: cannot connect to session bus")
            return False

        # Unique bus name — SNI spec requires org.kde.StatusNotifierItem-PID-ID
        pid = os.getpid()
        bus_name = f"org.kde.StatusNotifierItem-{pid}-1"
        try:
            self._bus_name_id = Gio.bus_own_name_on_connection(
                self._conn,
                bus_name,
                Gio.BusNameOwnerFlags.NONE,
                None,
                None,
            )

            sni_info = Gio.DBusNodeInfo.new_for_xml(_SNI_INTERFACE_XML).interfaces[0]
            self._sni_reg_id = self._conn.register_object(
                self.OBJECT_PATH,
                sni_info,
                self._sni_method_call,
                self._sni_get_property,
                None,
            )

            menu_info = Gio.DBusNodeInfo.new_for_xml(_DBUSMENU_INTERFACE_XML).interfaces[0]
            self._menu_reg_id = self._conn.register_object(
                self.MENU_PATH,
                menu_info,
                self._menu_method_call,
                self._menu_get_property,
                None,
            )
        except Exception:
            logger.exception("tray: failed to export StatusNotifierItem")
            return False

        # Ask the watcher to show us.
        self._register_with_watcher(bus_name)
        logger.info("tray: registered as %s", bus_name)
        return True

    def destroy(self):
        if self._conn is None:
            return
        try:
            if self._sni_reg_id:
                self._conn.unregister_object(self._sni_reg_id)
            if self._menu_reg_id:
                self._conn.unregister_object(self._menu_reg_id)
            if self._bus_name_id:
                Gio.bus_unown_name(self._bus_name_id)
        except Exception:
            logger.exception("tray: cleanup failed")
        self._conn = None

    def set_window_visible(self, visible: bool):
        """The window's visibility changed — update the toggle label."""
        self._window_visible = visible
        self._menu_items[0]["label"] = "Hide Solaar" if visible else "Show Solaar"
        self._menu_revision += 1
        if self._conn is not None:
            try:
                self._conn.emit_signal(
                    None,
                    self.MENU_PATH,
                    "com.canonical.dbusmenu",
                    "LayoutUpdated",
                    GLib.Variant("(ui)", (self._menu_revision, 0)),
                )
            except Exception:
                logger.exception("tray: LayoutUpdated signal failed")

    def update(self, device):
        """Device status changed — nothing visible yet but a future commit
        could count-badge paired devices or swap the icon on low battery."""
        pass

    def attention(self, reason):
        """Temporary notification-level urgency."""
        pass

    # ---------- StatusNotifierItem interface ----------

    def _sni_get_property(self, _conn, _sender, _path, _iface, name, _err):
        if name == "Category":
            return GLib.Variant("s", "ApplicationStatus")
        if name == "Id":
            return GLib.Variant("s", "solaar")
        if name == "Title":
            return GLib.Variant("s", self._title)
        if name == "Status":
            return GLib.Variant("s", self._status)
        if name == "IconName":
            return GLib.Variant("s", self._icon_name)
        if name == "IconPixmap":
            return GLib.Variant("a(iiay)", [])
        if name == "AttentionIconName":
            return GLib.Variant("s", "")
        if name == "OverlayIconName":
            return GLib.Variant("s", "")
        if name == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)", ("", [], self._title, "Logitech device manager"))
        if name == "Menu":
            return GLib.Variant("o", self.MENU_PATH)
        if name == "ItemIsMenu":
            return GLib.Variant("b", False)
        return None

    def _sni_method_call(self, _conn, _sender, _path, _iface, method, _params, invocation):
        if method == "Activate":
            logger.debug("tray: Activate")
            if self._on_activate:
                GLib.idle_add(self._on_activate)
            invocation.return_value(None)
        elif method in ("SecondaryActivate", "ContextMenu"):
            invocation.return_value(None)
        elif method == "Scroll":
            invocation.return_value(None)
        else:
            invocation.return_error_literal(
                Gio.DBusError.quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f"Unknown method: {method}",
            )

    # ---------- DBusMenu interface ----------

    def _menu_get_property(self, _conn, _sender, _path, _iface, name, _err):
        if name == "Version":
            return GLib.Variant("u", 3)
        if name == "TextDirection":
            return GLib.Variant("s", "ltr")
        if name == "Status":
            return GLib.Variant("s", "normal")
        if name == "IconThemePath":
            return GLib.Variant("as", [])
        return None

    def _menu_layout(self):
        """Return the (revision, (id, props, children)) tuple GetLayout expects."""
        children = []
        for item in self._menu_items:
            props = {
                "label": GLib.Variant("s", item["label"]),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
                "type": GLib.Variant("s", "standard"),
            }
            children.append(GLib.Variant("(ia{sv}av)", (item["id"], props, [])))

        root_props = {
            "children-display": GLib.Variant("s", "submenu"),
        }
        return GLib.Variant(
            "(ui(ia{sv}av))",
            (self._menu_revision, (0, root_props, children)),
        )

    def _menu_method_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "GetLayout":
            invocation.return_value(self._menu_layout())
        elif method == "GetGroupProperties":
            ids, _prop_names = params.unpack()
            result = []
            for item in self._menu_items:
                if item["id"] in ids:
                    props = {
                        "label": GLib.Variant("s", item["label"]),
                        "enabled": GLib.Variant("b", True),
                        "visible": GLib.Variant("b", True),
                        "type": GLib.Variant("s", "standard"),
                    }
                    result.append(GLib.Variant("(ia{sv})", (item["id"], props)))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))
        elif method == "GetProperty":
            invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", ""),)))
        elif method == "Event":
            item_id, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                self._dispatch_menu_click(item_id)
            invocation.return_value(None)
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        else:
            invocation.return_error_literal(
                Gio.DBusError.quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f"Unknown menu method: {method}",
            )

    def _dispatch_menu_click(self, item_id):
        for item in self._menu_items:
            if item["id"] != item_id:
                continue
            event = item["event"]
            if event == "show" and self._on_activate:
                GLib.idle_add(self._on_activate)
            elif event == "quit" and self._on_quit:
                GLib.idle_add(self._on_quit)
            break

    # ---------- Register with the watcher ----------

    def _register_with_watcher(self, bus_name):
        def _on_registered(proxy, result):
            try:
                proxy.call_finish(result)
                logger.debug("tray: RegisterStatusNotifierItem OK")
            except Exception as e:
                logger.warning(
                    "tray: watcher rejected registration (%s) — "
                    "make sure the AppIndicator shell extension is enabled",
                    e,
                )

        def _on_proxy_ready(_src, result):
            try:
                proxy = Gio.DBusProxy.new_finish(result)
                proxy.call(
                    "RegisterStatusNotifierItem",
                    GLib.Variant("(s)", (bus_name,)),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None,
                    _on_registered,
                )
            except Exception as e:
                logger.warning("tray: watcher unavailable (%s)", e)

        Gio.DBusProxy.new(
            self._conn,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            None,
            _on_proxy_ready,
        )


_tray: Optional[_Tray] = None


def init(on_activate, on_quit=None):
    """Create the tray icon. `on_activate` is called for left-click and
    "Show Solaar"; `on_quit` for the Quit menu entry."""
    global _tray
    if _tray is None:
        _tray = _Tray()
    _tray.init(on_activate, on_quit or (lambda: None))
    return _tray


def destroy(*_args, **_kwargs):
    global _tray
    if _tray is not None:
        _tray.destroy()
        _tray = None


def update(device=None, *_args, **_kwargs):
    if _tray is not None:
        _tray.update(device)


def attention(reason=None, *_args, **_kwargs):
    if _tray is not None:
        _tray.attention(reason)


def set_window_visible(visible: bool):
    if _tray is not None:
        _tray.set_window_visible(visible)
