# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Generate the derived application icons from the official ``logo.png``.

The official branding master is ``resources/branding/logo.png``. Everything
else is derived from it and never redesigned, recolored, or distorted:

* ``app_icon.png``  — square, transparent-padded render of the lockup used
  for the window/taskbar icon and as the ICO source.
* ``app_icon.ico``  — multi-resolution Windows icon (16–256 px) for the
  executable and installer.
* ``installer_wizard.bmp``        — Inno Setup welcome/sidebar image (240×459,
  164:314 aspect) rendered on the app's dark background with the official
  lockup and a thin emerald brand accent.
* ``installer_wizard_small.bmp``  — Inno Setup header image (147×147, square)
  in the same dark style.

Run ``python generate_icon.py`` manually, or let ``build.py`` invoke it
automatically before every build. Requirements: Pillow.
"""

from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Run: pip install Pillow")
    raise SystemExit(1)

from core.branding import (
    app_icon_ico_path,
    app_icon_path,
    installer_wizard_image_path,
    installer_wizard_small_image_path,
    logo_path,
)
from core.theme import Dark

#: ICO sizes Windows expects in one multi-resolution file.
ICO_SIZES = [16, 32, 48, 64, 128, 256]
#: Edge length of the derived square ``app_icon.png``.
ICON_PNG_SIZE = 512

#: Inno Setup wizard image: 164:314 aspect ratio (maintained by Setup at any
#: DPI). 240×459 matches the size of Inno Setup's own default image, keeping
#: the lockup crisp at 100–150% DPI.
WIZARD_IMAGE_SIZE = (240, 459)
#: Inno Setup small wizard image area is square; 147×147 matches the default.
WIZARD_SMALL_IMAGE_SIZE = (147, 147)
#: Padding around the lockup inside the wizard canvases.
WIZARD_LOGO_PADDING = 26
#: Height of the emerald brand accent strip at the bottom of the big image.
WIZARD_ACCENT_HEIGHT = 8


def _hex_to_rgb(value: str) -> tuple:
    """Convert an ``#RRGGBB`` theme token into an (r, g, b) tuple."""
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _fit_square(source: "Image.Image", size: int) -> "Image.Image":
    """Fit ``source`` inside a ``size`` x ``size`` canvas, aspect preserved.

    The official lockup is not perfectly square; icons must never stretch or
    distort it, so it is centered on a transparent canvas at the requested
    size (the standard icon treatment for non-square artwork).
    """
    width, height = source.size
    scale = min(size / width, size / height)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    resized = source.resize((new_width, new_height), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - new_width) // 2, (size - new_height) // 2), resized)
    return canvas


def _fit_canvas(
    logo: "Image.Image",
    size: tuple,
    padding: int,
    accent_height: int = 0,
) -> "Image.Image":
    """Composite the official lockup onto the dark wizard canvas.

    The canvas uses the app's dark background token; the lockup is fitted
    (aspect preserved — never stretched) and centered in the area above the
    optional emerald accent strip. Returns a 24-bit RGB image, which is the
    format Inno Setup expects for wizard bitmaps.
    """
    width, height = size
    bg = _hex_to_rgb(Dark.BG)
    accent = _hex_to_rgb(Dark.PRIMARY)
    content_height = height - accent_height
    inner_w = max(1, width - 2 * padding)
    inner_h = max(1, content_height - 2 * padding)

    scale = min(inner_w / logo.width, inner_h / logo.height)
    new_w = max(1, round(logo.width * scale))
    new_h = max(1, round(logo.height * scale))
    logo_resized = logo.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", size, bg)
    logo_x = (width - new_w) // 2
    logo_y = (content_height - new_h) // 2
    canvas.paste(logo_resized, (logo_x, logo_y), logo_resized)
    if accent_height > 0:
        accent_bar = Image.new("RGB", (width, accent_height), accent)
        canvas.paste(accent_bar, (0, content_height))
    return canvas


def ensure_app_icon_png(png_path: Path | None = None, out_path: Path | None = None) -> Path:
    """Derive ``app_icon.png`` from the official ``logo.png``.

    Rebuilds when missing or when the master logo is newer, so a swapped
    official logo is always picked up without touching build code.
    """
    source_path = png_path or logo_path()
    output_path = out_path or app_icon_path()
    if output_path.exists():
        try:
            if source_path.stat().st_mtime <= output_path.stat().st_mtime:
                print(f"App icon PNG up to date: {output_path}")
                return output_path
        except OSError:
            pass
    icon = _fit_square(Image.open(source_path).convert("RGBA"), ICON_PNG_SIZE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    icon.save(output_path, format="PNG")
    print(f"App icon PNG saved: {output_path}")
    return output_path


def generate_app_icon_ico(png_path: Path | None = None, ico_path: Path | None = None) -> Path:
    """Convert ``app_icon.png`` into the multi-resolution ``app_icon.ico``.

    Each frame is fitted (not stretched) at the requested size; the original
    PNG is never modified. Returns the path of the written .ico.
    """
    source_path = png_path or app_icon_path()
    output_path = ico_path or app_icon_ico_path()

    source = Image.open(source_path).convert("RGBA")
    images = [_fit_square(source, size) for size in ICO_SIZES]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=images[:-1],
    )
    print(f"Icon saved: {output_path}")
    return output_path


def ensure_app_icon_ico() -> Path:
    """Ensure ``app_icon.png`` and ``app_icon.ico`` are current.

    ``app_icon.png`` is derived from the official ``logo.png``; the .ico is
    derived from that PNG. Both are build-time artifacts — the runtime app
    always loads ``logo.png`` / ``app_icon.png`` from the branding folder.
    """
    ensure_app_icon_png()
    output_path = app_icon_ico_path()
    source_path = app_icon_path()
    if output_path.exists():
        try:
            if source_path.stat().st_mtime <= output_path.stat().st_mtime:
                print(f"Icon up to date: {output_path}")
                return output_path
        except OSError:
            pass
    return generate_app_icon_ico(source_path, output_path)


def generate_installer_wizard_image(
    png_path: Path | None = None, out_path: Path | None = None
) -> Path:
    """Render the Inno Setup welcome/sidebar bitmap from the official logo.

    The 164:314 lockup panel uses the app's dark background token with the
    official logo centered (aspect preserved) and a thin emerald accent at
    the bottom — matching the application's dark/emerald identity without
    touching the logo artwork. Returns the path of the written .bmp.
    """
    source_path = png_path or logo_path()
    output_path = out_path or installer_wizard_image_path()
    logo = Image.open(source_path).convert("RGBA")
    canvas = _fit_canvas(
        logo, WIZARD_IMAGE_SIZE, WIZARD_LOGO_PADDING, WIZARD_ACCENT_HEIGHT
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="BMP")
    print(f"Installer wizard image saved: {output_path}")
    return output_path


def generate_installer_wizard_small_image(
    png_path: Path | None = None, out_path: Path | None = None
) -> Path:
    """Render the square Inno Setup header bitmap from the official logo.

    Uses the same dark background token and aspect-preserving fit as the
    large wizard image. Returns the path of the written .bmp.
    """
    source_path = png_path or logo_path()
    output_path = out_path or installer_wizard_small_image_path()
    logo = Image.open(source_path).convert("RGBA")
    canvas = _fit_canvas(logo, WIZARD_SMALL_IMAGE_SIZE, WIZARD_LOGO_PADDING)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="BMP")
    print(f"Installer wizard small image saved: {output_path}")
    return output_path


def ensure_installer_wizard_images() -> tuple:
    """Ensure both Inno Setup wizard bitmaps are current.

    Rebuilds when missing or when the master logo is newer, so a swapped
    official logo is always picked up without touching build code. Returns
    the pair ``(big_image_path, small_image_path)``.
    """
    source_path = logo_path()
    big_path = installer_wizard_image_path()
    small_path = installer_wizard_small_image_path()

    def _current(output_path: Path) -> bool:
        if not output_path.exists():
            return False
        try:
            return source_path.stat().st_mtime <= output_path.stat().st_mtime
        except OSError:
            return False

    if not _current(big_path):
        generate_installer_wizard_image(source_path, big_path)
    else:
        print(f"Installer wizard image up to date: {big_path}")
    if not _current(small_path):
        generate_installer_wizard_small_image(source_path, small_path)
    else:
        print(f"Installer wizard small image up to date: {small_path}")
    return big_path, small_path


if __name__ == "__main__":
    ensure_app_icon_ico()
    ensure_installer_wizard_images()
