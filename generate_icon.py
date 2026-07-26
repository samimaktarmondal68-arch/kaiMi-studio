"""Generate the KaiMi Studio application icon (.ico).

Run this script to produce assets/icons/kaimi.ico from the same
vector logic used by KaiMiLogo in the sidebar.

Requirements: Pillow
"""

from pathlib import Path
try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required. Run: pip install Pillow")
    raise SystemExit(1)


def _draw_logo(size: int) -> Image.Image:
    """Render the KaiMi gradient-K logo at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = size / 2

    # Gradient background circle — 24 steps
    for i in range(24):
        ratio = i / 24
        r = int(109 + (77 - 109) * ratio)
        g = int(74 + (168 - 74) * ratio)
        b = 255
        half = m * (1 - ratio * 0.15)
        draw.ellipse([m - half, m - half, m + half, m + half],
                     fill=(r, g, b, 255))

    # Stylized "K" letterform
    p = size * 0.12
    kw = size * 0.1

    # Vertical bar
    x1 = p + size * 0.08
    y1 = p + size * 0.15
    x2 = x1 + kw
    y2 = size - p - size * 0.15
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 255))

    # Upper diagonal
    pts_upper = [
        (x2 + 1, m),
        (size - p - size * 0.08, p + size * 0.15),
        (size - p - size * 0.08 - kw * 0.7, p + size * 0.15),
        (x2 + 1, m - kw * 0.5),
    ]
    draw.polygon(pts_upper, fill=(255, 255, 255, 255))

    # Lower diagonal
    pts_lower = [
        (x2 + 1, m),
        (size - p - size * 0.08, size - p - size * 0.15),
        (size - p - size * 0.08 - kw * 0.7, size - p - size * 0.15),
        (x2 + 1, m + kw * 0.5),
    ]
    draw.polygon(pts_lower, fill=(255, 255, 255, 255))

    return img


def generate_ico(output_path: Path) -> None:
    """Generate multi-resolution .ico at 16, 32, 48, 64, 128, 256 px."""
    sizes = [16, 32, 48, 64, 128, 256]
    images = [_draw_logo(s) for s in sizes]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"Icon saved: {output_path}")


def generate_png(output_path: Path, size: int = 256) -> None:
    """Generate a PNG version of the logo."""
    img = _draw_logo(size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    print(f"PNG saved: {output_path}")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    ico_path = base / "assets" / "icons" / "kaimi.ico"
    png_path = base / "assets" / "icons" / "kaimi_256.png"

    generate_ico(ico_path)
    generate_png(png_path)
