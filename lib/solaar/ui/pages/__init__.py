## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## Device-specific libadwaita pages. `page_for_device` picks the best match
## based on the device's wpid/kind.

from __future__ import annotations

from solaar.ui.device_page import DevicePage
from solaar.ui.pages.mouse_pro_x_2 import ProX2Page

_PRO_X_2_WPIDS = {"40A9", "40BD", "4093"}


def page_for_device(device) -> DevicePage:
    wpid = (getattr(device, "wpid", None) or "").upper()
    if wpid in _PRO_X_2_WPIDS:
        return ProX2Page(device)
    return DevicePage(device)
