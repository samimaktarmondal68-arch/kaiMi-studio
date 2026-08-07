# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Centralized runtime access to the official KaiMi Studio branding assets.

``resources/branding`` is the ONLY branding source. ``logo.png`` is the
official master lockup; ``app_icon.png`` and ``app_icon.ico`` are derived
from it by ``generate_icon.py`` (aspect-preserving, never redesigned). All
windows, taskbar icons, dialogs, the sidebar and the About pages resolve
their artwork through this module. Never hardcode image paths elsewhere in
the application or build system.

The derived files are build-time artifacts: if ``app_icon.png``/``.ico`` are
missing at runtime, the accessors fall back to the official ``logo.png`` so
the app still displays correct branding.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Return the directory that contains bundled resources at runtime.

    In a frozen PyInstaller build the data files live under ``sys._MEIPASS``
    (or next to the executable); in development they live at the repo root.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def branding_dir() -> Path:
    """Path to the centralized branding folder (``resources/branding``)."""
    return _bundle_root() / "resources" / "branding"


def logo_path() -> Path:
    """Path to the official master logo (``logo.png``)."""
    return branding_dir() / "logo.png"


def app_icon_path() -> Path:
    """Path to the official application icon (``app_icon.png``)."""
    return branding_dir() / "app_icon.png"


def app_icon_ico_path() -> Path:
    """Path to the Windows ``app_icon.ico``.

    Generated from ``app_icon.png`` by ``generate_icon.py`` (wired into
    ``build.py``). Used by PyInstaller (executable icon) and the Inno
    installer only — never by runtime code.
    """
    return branding_dir() / "app_icon.ico"


def app_icon():
    """QIcon for the application window and taskbar (lazy Qt import).

    Loads the derived ``app_icon.png`` (the official lockup, squared without
    distortion); falls back to ``logo.png`` when the derived file is absent.
    The Windows executable/installer icons come from the build-time
    ``app_icon.ico``.
    """
    from PySide6.QtGui import QIcon
    icon = QIcon(str(app_icon_path()))
    if icon.isNull():
        icon = QIcon(str(logo_path()))
    return icon


def logo_pixmap(pixel_size: int = 96):
    """QPixmap of the official ``logo.png`` scaled to ``pixel_size`` px.

    The square lockup is scaled with smooth transformation and its aspect
    ratio is always preserved (no stretching or distortion). Falls back to
    ``app_icon.png`` when the master logo is missing.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(str(logo_path()))
    if pixmap.isNull():
        pixmap = QPixmap(str(app_icon_path()))
    if pixmap.isNull():
        return pixmap
    if pixmap.width() != pixel_size:
        pixmap = pixmap.scaled(
            pixel_size, pixel_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
    return pixmap
