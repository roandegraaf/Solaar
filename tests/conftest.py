"""Test-suite-level conftest.

Provides a lightweight mock for PyGObject (`gi`) when it isn't installed,
so the pure-logic tests can run on non-Linux developer machines. On Linux
with PyGObject installed, this is a no-op.
"""

import sys
import types

from unittest.mock import MagicMock


def _install_gi_stub():
    try:
        import gi  # noqa: F401

        return
    except ImportError:
        pass

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *args, **kwargs: None

    repository = types.ModuleType("gi.repository")
    for name in ("Gtk", "Gdk", "GLib", "Gio", "GObject", "Notify", "Pango", "Adw"):
        sub = MagicMock(name=f"gi.repository.{name}")
        setattr(repository, name, sub)
        sys.modules[f"gi.repository.{name}"] = sub

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repository
    gi_mod.repository = repository


_install_gi_stub()
