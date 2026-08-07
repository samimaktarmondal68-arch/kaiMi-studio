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

Run ``python generate_icon.py`` manually, or let ``build.py`` invoke it
automatically before every build. Requirements: Pillow.
"""

from pathlib import Path
try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Run: pip install Pillow")
    raise SystemExit(1)

from core.branding import app_icon_ico_path, app_icon_path, logo_path

#: ICO sizes Windows expects in one multi-resolution file.
ICO_SIZES = [16, 32, 48, 64, 128, 256]
#: Edge length of the derived square ``app_icon.png``.
ICON_PNG_SIZE = 512


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


if __name__ == "__main__":
    ensure_app_icon_ico()
