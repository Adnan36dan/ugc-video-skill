"""Offline stand-ins for every paid model, so the whole pipeline can be tested for free (--mock).

The mock outputs look nothing like the real thing (tones instead of a voice, labelled cards
instead of photos); they only prove that installation, timing, editing and captions work.
"""
import colorsys
import json
import re
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import FONTS_DIR, SR, ffmpeg


def _norm_len(tok):
    import unicodedata
    return max(1, sum(1 for c in tok if unicodedata.category(c)[0] not in "PSZC"))


def tts(text, dest_wav):
    """Voice-like tone bursts, one per word, with realistic (and some too-long) pauses."""
    toks = [t for t in re.split(r"\s+", text.strip()) if t]
    rng = np.random.default_rng(len(text))
    t, chunks, words = 0.15, [np.zeros(int(0.15 * SR), np.float32)], []
    for tok in toks:
        if not re.search(r"\w", tok):
            continue
        d = min(0.62, max(0.16, 0.06 + 0.05 * _norm_len(tok)))
        tt = np.arange(int(d * SR)) / SR
        f0 = 140 + 70 * rng.random()
        sig = sum(np.sin(2 * np.pi * f0 * h * tt) / h for h in (1, 2, 3, 4)).astype(np.float32) * 0.16
        env = np.minimum(1, np.minimum(tt / 0.02, (d - tt) / 0.03)) * (0.65 + 0.35 * np.sin(2 * np.pi * 5 * tt))
        chunks.append((sig * env).astype(np.float32))
        words.append({"text": tok, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
        last = tok.rstrip()[-1]
        gap = 0.55 if last in ".?!।" else 0.26 if last in ",;:—-" else 0.06
        chunks.append(np.zeros(int(gap * SR), np.float32))
        t += gap
    chunks.append(np.zeros(int(0.25 * SR), np.float32))
    y = (np.clip(np.concatenate(chunks), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(dest_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(y.tobytes())
    Path(str(dest_wav) + ".mockwords.json").write_text(json.dumps(words, ensure_ascii=False))
    return dest_wav


def stt(wav):
    side = Path(str(wav) + ".mockwords.json")
    return json.loads(side.read_text()) if side.exists() else []


def _font(size):
    try:
        return ImageFont.truetype(str(FONTS_DIR / "Manrope-ExtraBold.ttf"), size)
    except OSError:
        return ImageFont.load_default()


def image(label, dest, face=None, product=None, variant=1, size=(1080, 1920)):
    """A labelled placeholder 'keyframe' built from the reference photos."""
    w, h = size
    hue = (sum(map(ord, label)) * 37 % 360) / 360
    top = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.25, 0.85))
    bot = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + 0.08) % 1, 0.45, 0.45))
    grad = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - grad) + np.array(bot)[None, None, :] * grad)
    im = Image.fromarray(np.repeat(arr, w, axis=1).astype(np.uint8), "RGB")
    if face:
        r = Image.open(face).convert("RGB")
        r.thumbnail((620, 620))
        m = Image.new("L", r.size, 0)
        ImageDraw.Draw(m).ellipse((0, 0, *r.size), fill=255)
        im.paste(r, ((w - r.width) // 2, int(h * 0.16)), m)
    if product:
        r = Image.open(product).convert("RGBA")
        r.thumbnail((420, 560))
        im.paste(r, (w - r.width - 80 - 60 * (variant - 1), int(h * 0.56)), r)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, 150), fill=(0, 0, 0))
    d.text((40, 40), f"MOCK {label}  v{variant}", font=_font(52), fill=(255, 255, 255))
    im.filter(ImageFilter.SMOOTH).save(dest)
    return dest


def avatar(image_path, audio_path, dest):
    """'Talking' clip: the keyframe at 720x1280/25fps (to exercise scaling) for the audio's length."""
    ffmpeg("-loop", "1", "-i", image_path, "-i", audio_path,
           "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
                  "drawbox=x=300:y=600:w=120:h=24:color=red@0.7:t=fill:enable='lt(mod(t,0.4),0.2)'",
           "-r", "25", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", dest)
    return dest


def i2v(image_path, seconds, dest):
    """'B-roll' clip: slow zoom on the keyframe at 24 fps."""
    n = int(round(seconds * 24))
    ffmpeg("-i", image_path, "-vf",
           f"scale=1440:2560,zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=720x1280:fps=24",
           "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", dest)
    return dest


def demo_inputs(folder):
    """Synthetic (non-human) face and product images for the mock demo."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    face = Image.new("RGB", (900, 1100), (214, 170, 140))
    d = ImageDraw.Draw(face)
    d.ellipse((220, 180, 680, 760), fill=(196, 150, 118))
    d.ellipse((330, 380, 400, 430), fill=(40, 30, 25))
    d.ellipse((500, 380, 570, 430), fill=(40, 30, 25))
    d.arc((370, 520, 530, 640), 20, 160, fill=(120, 60, 50), width=10)
    d.text((300, 900), "MOCK FACE", font=_font(60), fill=(60, 40, 30))
    face.save(folder / "face.png")
    prod = Image.new("RGBA", (700, 1000), (0, 0, 0, 0))
    d = ImageDraw.Draw(prod)
    d.rounded_rectangle((210, 60, 490, 170), 20, fill=(200, 160, 60, 255))
    d.rounded_rectangle((150, 160, 550, 940), 60, fill=(28, 90, 60, 255))
    d.rectangle((170, 420, 530, 700), fill=(250, 245, 230, 255))
    d.text((205, 520), "MOCK JUICE", font=_font(54), fill=(28, 90, 60, 255))
    prod.save(folder / "product.png")
    return folder / "face.png", folder / "product.png"
