## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Stub tray module. GTK4 removed GtkStatusIcon and the AyatanaAppIndicator
bindings need a separate port; the GTK4 rewrite ships without a tray icon
as a known limitation.
"""

import logging

logger = logging.getLogger(__name__)


def init(*_args, **_kwargs):
    logger.info("tray unsupported in this build (GTK4 rewrite)")
    return None


def destroy(*_args, **_kwargs):
    return None


def update(*_args, **_kwargs):
    return None


def attention(*_args, **_kwargs):
    return None
