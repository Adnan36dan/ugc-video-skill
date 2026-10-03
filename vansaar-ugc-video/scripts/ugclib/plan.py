"""Plan validation, duration estimate and cost estimate (run these BEFORE spending money)."""
import math
import re

from .job import FRAMINGS, SHOTS
from .util import log, print_table

WPS = {"en": 2.5, "hi": 2.7}       # spoken words per second at speed 1.0 (UGC pace)
EDGE = 0.28                         # silence kept around each segment (lead + tail)


def words(text):
    return [w for w in re.split(r"\s+", text or "") if re.search(r"\w", w)]


def est_seconds(job, seg):
    if not seg["say"]:
        if seg["shot"] == "endcard":
            return float(seg.get("hold") or job.plan["endcard"].get("hold", 2.5))
        return float(seg.get("hold") or 2.0)
    wps = WPS.get(job.plan["language"], 2.5) * float(job.plan["voice"].get("speed") or 1.0)
    t = len(words(seg["say"])) / wps + EDGE
    if seg["shot"] == "endcard":
        t += float(job.plan["endcard"].get("hold_after_voice", 0.8))
    return t


def setups_in_use(job):
    return sorted({s["setup"] for s in job.segments if s["shot"] == "talk" and s.get("setup")})


def validate(job):
    """Return (errors, warnings). Errors must be fixed before generation."""
    p, errors, warns = job.plan, [], []
    segs = p["segments"]
    if not segs:
        errors.append("plan has no segments")
        return errors, warns
    ids = [s["id"] for s in segs]
    if len(set(ids)) != len(ids):
        errors.append("segment ids must be unique")
    needs_face = any(s["shot"] == "talk" or (s["shot"] == "broll" and s["broll"]["with_person"]
                                             and not (s["broll"]["image"] or s["broll"]["video"])) for s in segs)
    needs_product = any(s["shot"] == "endcard" for s in segs) or \
        any(st["with_product"] for st in p["setups"].values()) or \
        any(s["shot"] == "broll" and s["broll"]["with_product"] and not (s["broll"]["image"] or s["broll"]["video"])
            for s in segs)
    for what, needed in (("face", needs_face), ("product", needs_product)):
        f = p["inputs"].get(what)
        if needed and (not f or not job.path(f).exists()):
            errors.append(f"inputs.{what} is missing or not found: {f}")
    for k, s in enumerate(segs):
        sid = s["id"]
        if s["shot"] not in SHOTS:
            errors.append(f"{sid}: shot must be one of {SHOTS}")
            continue
        if s["shot"] == "talk":
            if not s["say"]:
                errors.append(f"{sid}: a talk segment needs 'say' text")
            if s.get("setup") not in p["setups"]:
                errors.append(f"{sid}: setup '{s.get('setup')}' is not defined under setups")
        if s["shot"] == "broll":
            b = s["broll"]
            if b["video"] and not job.path(b["video"]).exists():
                errors.append(f"{sid}: broll.video not found: {b['video']}")
            if b["image"] and not job.path(b["image"]).exists():
                errors.append(f"{sid}: broll.image not found: {b['image']}")
            if not (b["video"] or b["image"] or b["scene"]):
                errors.append(f"{sid}: broll needs 'scene' (to generate), 'image' or 'video'")
            if not (b["video"] or b["motion"]):
                warns.append(f"{sid}: broll has no 'motion' prompt; a slow Ken Burns move will be used")
        if s["shot"] == "endcard" and k != len(segs) - 1:
            warns.append(f"{sid}: the end card is usually the last segment")
        t = est_seconds(job, s)
        if s["shot"] == "talk":
            if t < 1.6:
                warns.append(f"{sid}: very short talk segment (~{t:.1f}s); merge it with a neighbour for smoother lip-sync")
            if t > 12:
                warns.append(f"{sid}: long talk segment (~{t:.1f}s); split it so the edit has jump cuts")
            if t > float(job.models["avatar"].get("max_audio_seconds", 30)):
                errors.append(f"{sid}: ~{t:.0f}s is longer than the avatar model allows")
    used = set(setups_in_use(job))
    for name in p["setups"]:
        if name not in used:
            warns.append(f"setup {name} is not used by any talk segment (it will be skipped)")
    for name, st in p["setups"].items():
        if name not in used:
            continue
        if st["framing"] not in FRAMINGS:
            errors.append(f"setup {name}: framing must be one of {FRAMINGS}")
        if not st["scene"]:
            errors.append(f"setup {name}: describe the 'scene' (where they are, light, background)")
    v = p["voice"]
    if v["provider"] not in ("fal", "elevenlabs", "file"):
        errors.append("voice.provider must be fal, elevenlabs or file")
    if v["provider"] in ("fal", "elevenlabs") and not v["voice"] and not job.mock:
        errors.append("voice.voice is empty: choose a voice (see references/script-and-voice.md)")
    if v["provider"] == "file" and (not v["file"] or not job.path(v["file"]).exists()):
        errors.append(f"voice.file not found: {v['file']}")
    if p["music"]["file"] and not job.path(p["music"]["file"]).exists():
        errors.append(f"music.file not found: {p['music']['file']}")
    total = sum(est_seconds(job, s) for s in segs)
    if total < 18 or total > 62:
        warns.append(f"estimated length {total:.0f}s is outside the 20-60s target; trim or extend the script")
    if len(setups_in_use(job)) > 4:
        warns.append("more than 4 talk setups: each one costs keyframes; 2-3 looks more like one real recording session")
    return errors, warns


def print_timeline_estimate(job):
    rows, total = [], 0.0
    for s in job.segments:
        t = est_seconds(job, s)
        total += t
        what = s.get("setup") or ("own footage" if s["shot"] == "broll" and s["broll"]["video"] else "")
        rows.append([s["id"], s["shot"], what, f"{t:4.1f}s", (s["say"][:60] + ("…" if len(s["say"]) > 60 else ""))])
    print_table(rows, ["id", "shot", "setup", "≈len", "says"])
    log(f"\nEstimated length: {total:.1f}s  (target 20-60s; the real length is known after the voice step)")
    return total


def estimate_cost(job):
    m, p = job.models, job.plan
    lines = []
    chars = sum(len(s["say"]) for s in job.segments)
    if p["voice"]["provider"] == "fal":
        lines.append(("voice (ElevenLabs via fal)", chars / 1000 * m["tts"]["price_per_1k_chars"]))
    elif p["voice"]["provider"] == "elevenlabs":
        lines.append(("voice (ElevenLabs direct, billed by ElevenLabs)",
                      chars / 1000 * m["elevenlabs_direct"]["price_per_1k_chars"]))
    spoken = sum(est_seconds(job, s) for s in job.segments if s["say"])
    lines.append(("word timings (speech-to-text)", spoken / 60 * m["stt"]["price_per_minute"]))
    n_img = sum(int(p["setups"][n]["candidates"]) for n in setups_in_use(job))
    n_img += sum(int(s["broll"]["candidates"]) for s in job.segments
                 if s["shot"] == "broll" and not (s["broll"]["image"] or s["broll"]["video"]))
    lines.append((f"keyframe images ({n_img})", n_img * m["image"]["price_per_image"]))
    talk = sum(est_seconds(job, s) for s in job.segments if s["shot"] == "talk")
    lines.append((f"talking clips (~{talk:.0f}s)", talk * m["avatar"]["price_per_second"]))
    broll_s = 0
    for s in job.segments:
        if s["shot"] == "broll" and not s["broll"]["video"] and s["broll"]["motion"] and \
                s["broll"]["motion"].strip().lower() != "kenburns":
            broll_s += pick_duration(m["broll"]["duration_choices"], est_seconds(job, s))[0]
    lines.append((f"b-roll clips (~{broll_s:.0f}s generated)", broll_s * m["broll"]["price_per_second"]))
    total = sum(v for _, v in lines)
    rows = [[k, f"${v:6.2f}"] for k, v in lines]
    rows.append(["TOTAL (one clean pass)", f"${total:6.2f}"])
    rows.append(["Budget with typical re-dos (x1.4)", f"${total * 1.4:6.2f}"])
    print_table(rows, ["item", "USD"])
    spent = job.state.spent()
    if spent:
        log(f"\nAlready spent on this job (estimated): ${spent:.2f}")
    log("Prices come from config/models.yaml (checked Oct 2026) - verify at https://fal.ai/pricing")
    return total


def pick_duration(choices, needed):
    """Smallest allowed duration >= needed. Returns (seconds, original_choice_value)."""
    parsed = sorted(((float(re.sub(r"[^0-9.]", "", str(c))), c) for c in choices), key=lambda x: x[0])
    for sec, raw in parsed:
        if sec >= needed - 0.05:
            return sec, raw
    return parsed[-1]


def ceil_frames(seconds, fps):
    return int(math.ceil(seconds * fps))
