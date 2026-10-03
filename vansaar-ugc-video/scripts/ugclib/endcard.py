"""Branded end card built from the REAL product photo (so the label is always exactly right).

Text (CTA, accent line, disclaimer) is drawn later by libass, in captions.py, using LAYOUT.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .util import SKILL_DIR, H, W, hex_to_rgb

LAYOUT = {"logo_y": 250, "logo_w": 540, "product_box": (150, 500, 930, 1390),
          "accent_y": 1500, "cta_y": 1596, "disclaimer_y": 1772}


def _gradient(top, mid, bottom):
    t = np.linspace(0, 1, H)[:, None]
    up = np.clip(1 - t * 2, 0, 1)
    down = np.clip(t * 2 - 1, 0, 1)
    midw = 1 - up - down
    col = (np.array(top)[None, :] * up + np.array(mid)[None, :] * midw + np.array(bottom)[None, :] * down)
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8), "RGB")


def _glow(img, center, radius, rgb, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx, cy = center
    ImageDraw.Draw(layer).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*rgb, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.45))
    return Image.alpha_composite(img.convert("RGBA"), layer)


def cutout(path):
    """Product with a transparent background: uses the PNG's own alpha, or removes a plain white backdrop.
    Returns (RGBA image, True) on success, or (RGB image, False) when the backdrop can't be removed."""
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    im.thumbnail((1400, 1400))
    if im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        a = np.asarray(rgba)[..., 3]
        if a.min() < 200:
            return rgba.crop(rgba.getbbox()), True
    rgb = im.convert("RGB")
    arr = np.asarray(rgb).astype(np.int16)
    near_white = (arr.min(axis=2) > 232) & ((arr.max(axis=2) - arr.min(axis=2)) < 18)
    mask = Image.fromarray((near_white * 255).astype(np.uint8), "L").copy()  # copy: fromarray is read-only
    w, h = mask.size
    seeds = [(x, 0) for x in range(0, w, 16)] + [(x, h - 1) for x in range(0, w, 16)] + \
            [(0, y) for y in range(0, h, 16)] + [(w - 1, y) for y in range(0, h, 16)]
    for xy in seeds:
        if mask.getpixel(xy) == 255:
            ImageDraw.floodfill(mask, xy, 128)
    bg = np.asarray(mask) == 128
    if bg.mean() < 0.06 or bg.mean() > 0.97:
        return rgb, False
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8), "L")
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.1))
    rgba = rgb.copy()
    rgba.putalpha(alpha)
    return rgba.crop(alpha.getbbox()), True


def _fit(im, box_w, box_h):
    s = min(box_w / im.width, box_h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def render_endcard(job, dest):
    brand, ec = job.brand, job.plan["endcard"]
    c = {k: hex_to_rgb(v) for k, v in brand["colors"].items()}
    dark = ec.get("theme", "dark") == "dark"
    if dark:
        img = _gradient(c["forest_deep"], c["forest"], c["forest_deep"])
    else:
        img = _gradient(c["ivory"], c["ivory"], c["ivory_warm"])
    x0, y0, x1, y1 = LAYOUT["product_box"]
    img = _glow(img, ((x0 + x1) // 2, (y0 + y1) // 2 + 40), 430, c["saffron"], 70 if dark else 45)

    logo = Image.open(SKILL_DIR / brand["logo"]).convert("RGBA")
    if not dark:  # deep-gold version for light backgrounds
        r, g, b, a = logo.split()
        r, g, b = (ch.point(lambda v: int(v * 0.68)) for ch in (r, g, b))
        logo = Image.merge("RGBA", (r, g, b, a))
    logo = _fit(logo, LAYOUT["logo_w"], 400)
    img.alpha_composite(logo, ((W - logo.width) // 2, LAYOUT["logo_y"]))

    prod, is_cut = cutout(job.path(job.plan["inputs"]["product"]))
    if is_cut:
        prod = _fit(prod, x1 - x0, y1 - y0)
        px, py = (W - prod.width) // 2, y0 + (y1 - y0 - prod.height) // 2
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh = Image.new("RGBA", prod.size, (0, 0, 0, 150 if dark else 90))
        shadow.paste(sh, (px + 18, py + 30), prod.split()[3])
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(28)))
        img.alpha_composite(prod, (px, py))
    else:  # photo with a busy background: show it as a rounded card
        card = _fit(prod.convert("RGB"), x1 - x0 - 40, y1 - y0 - 40)
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), 36, fill=255)
        px, py = (W - card.width) // 2, y0 + (y1 - y0 - card.height) // 2
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((px + 12, py + 24, px + card.width + 12, py + card.height + 24),
                                                 36, fill=(0, 0, 0, 140))
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(26)))
        img.paste(card, (px, py), mask)
    img.convert("RGB").save(dest)
    return dest
