"""One .ass subtitle file for everything drawn as text: UGC captions with the spoken word highlighted,
the AI-disclosure label, and the end-card CTA / accent / disclaimer. Rendered by libass (correct Hindi
shaping, brand fonts from assets/fonts)."""
import re

from .endcard import LAYOUT
from .util import H, W, hex_to_rgb
from .voice import distribute, tokens

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
BREAK_AFTER = re.compile(r"[.?!।,;:—–]$|[.?!।,;:—–]\s*[—–-]?$")


def ass_color(hexstr, alpha=0):
    r, g, b = hex_to_rgb(hexstr)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ts(t):
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(text):
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def wrap2(text, limit):
    """Balanced two-line wrap for short notes."""
    if len(text) <= limit:
        return text
    words, best, best_diff = text.split(), None, 10 ** 9
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if abs(len(a) - len(b)) < best_diff:
            best, best_diff = (a, b), abs(len(a) - len(b))
    return f"{best[0]}\\N{best[1]}"


def caption_words(entry, caption_text):
    spoken = [(w["t"], w["s"], w["e"]) for w in entry["words"]]
    if not caption_text or not spoken:
        return spoken
    toks = tokens(caption_text)
    return [(t, s, e) for t, (s, e) in zip(toks, distribute(toks, spoken))]


def make_cards(words, per_card, max_chars):
    cards, cur = [], []
    for t, s, e in words:
        if cur:
            prev = cur[-1]
            joined = len(" ".join(x[0] for x in cur)) + 1 + len(t)
            if len(cur) >= per_card or joined > max_chars or s - prev[2] > 0.45 or BREAK_AFTER.search(prev[0]):
                cards.append(cur)
                cur = []
        cur.append((t, s, e))
    if cur:
        cards.append(cur)
    return cards


def build_ass(job, timeline, starts, out_path, include_captions=True):
    brand, plan = job.brand, job.plan
    fonts, cols, cap = brand["fonts"], brand["colors"], plan["captions"]
    dark = plan["endcard"].get("theme", "dark") == "dark"
    txt, hl, outl = ass_color(cap["text_color"]), ass_color(cap["highlight_color"]), ass_color(cap["outline_color"])
    size = int(cap.get("size", 72))
    ec_main = ass_color(cols["ivory"] if dark else cols["forest"])
    ec_accent = ass_color(cols.get("saffron_light", cols["saffron"]) if dark else cols["burnt_saffron"])
    ec_note = ass_color(cols["ivory"] if dark else cols["ink"], 0x50)
    style_fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                 "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                 "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")

    def style(name, font, fs, prim, outline_c, back, italic=0, border=1, outline=0, shadow=0, align=5, spacing=0):
        return (f"Style: {name},{font},{fs},{prim},{prim},{outline_c},{back},0,{italic},0,0,100,100,{spacing},0,"
                f"{border},{outline},{shadow},{align},90,90,0,1")

    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
             "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "", "[V4+ Styles]", style_fmt,
             style("Cap", fonts["latin"], size, txt, outl, "&H78000000", outline=5, shadow=2),
             style("CapDeva", fonts["devanagari"], int(size * 1.1), txt, outl, "&H78000000", outline=5, shadow=2),
             style("Tag", fonts["latin"], 30, "&H00FFFFFF", "&H6A000000", "&H00000000", border=3, outline=9,
                   align=7, spacing=1),
             style("EcCta", fonts["latin"], 62, ec_main, "&H00000000", "&H00000000"),
             style("EcAccent", fonts["accent"], 86, ec_accent, "&H00000000", "&H00000000", italic=1),
             style("EcNote", fonts["latin"], 25, ec_note, "&H00000000", "&H00000000"),
             "", "[Events]",
             "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    events = []
    total = sum(e["dur"] for e in timeline["segments"])
    seg_by_id = {s["id"]: s for s in job.segments}
    y = int(float(cap.get("position", 0.70)) * H)

    for e in timeline["segments"]:
        seg, t0 = seg_by_id[e["id"]], starts[e["id"]]
        t1 = t0 + e["dur"]
        if seg["shot"] == "endcard":
            ec = plan["endcard"]
            fade = "{\\fad(300,0)}"
            if ec.get("accent"):
                events.append((2, t0 + 0.15, t1, "EcAccent",
                               f"{{\\an5\\pos({W // 2},{LAYOUT['accent_y']})}}{fade}{esc(ec['accent'])}"))
            if ec.get("cta"):
                events.append((2, t0 + 0.3, t1, "EcCta",
                               f"{{\\an5\\pos({W // 2},{LAYOUT['cta_y']})}}{fade}{esc(ec['cta'])}"))
            if brand["disclaimer"].get("show_on_endcard") and brand["disclaimer"].get("text"):
                note = wrap2(esc(brand["disclaimer"]["text"]), 48)
                events.append((2, t0 + 0.3, t1, "EcNote",
                               f"{{\\an5\\pos({W // 2},{LAYOUT['disclaimer_y']})}}{fade}{note}"))
            continue
        if not (include_captions and cap.get("enabled", True)):
            continue
        cards = make_cards(caption_words(e, seg.get("caption")), int(cap.get("words_per_card", 3)),
                           int(cap.get("max_chars", 20)))
        for ci, card in enumerate(cards):
            c_start = card[0][1]
            c_end = card[-1][2] + 0.12
            if ci + 1 < len(cards) and cards[ci + 1][0][1] - card[-1][2] < 0.35:
                c_end = cards[ci + 1][0][1]
            c_end = min(c_end, e["dur"])
            deva = any(DEVANAGARI.search(w[0]) for w in card)
            for k, (_, s, _) in enumerate(card):
                ev_s = c_start if k == 0 else s
                ev_e = card[k + 1][1] if k + 1 < len(card) else c_end
                if ev_e - ev_s < 0.02:
                    continue
                parts = [f"{{\\1c{hl}}}{esc(w)}{{\\1c{txt}}}" if j == k else esc(w) for j, (w, _, _) in enumerate(card)]
                pop = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
                events.append((1, t0 + ev_s, t0 + ev_e, "CapDeva" if deva else "Cap",
                               f"{{\\an5\\pos({W // 2},{y})}}{pop}{' '.join(parts)}"))

    disc = plan["disclosure"]
    if disc.get("show") and disc.get("label"):
        events.append((3, 0, total, "Tag", f"{{\\an7\\pos(46,132)}}{esc(disc['label'])}"))
    for layer, s, e_, st, text in sorted(events, key=lambda x: x[1]):
        lines.append(f"Dialogue: {layer},{ts(s)},{ts(e_)},{st},,0,0,0,,{text}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
