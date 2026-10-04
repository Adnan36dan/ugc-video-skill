"""Voice stage.

TTS per segment (or one real recording) -> speech-to-text word timings -> script/transcript
alignment -> long pauses tightened like a human editor would -> one clean audio slice per
segment + timeline.json (segment durations and word timings used by every later stage).
"""
import difflib
import re
import unicodedata
import wave
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from . import mock
from .falapi import download, elevenlabs_tts
from .util import SR, UGCError, ffmpeg, file_hash, load_json, log, obj_hash, print_table, save_json, warn

LEAD, TAIL = 0.10, 0.18   # silence kept before the first / after the last word of a segment
XFADE = 0.010             # crossfade when a pause is shortened
EDGE_FADE = 0.005


# ---------------------------------------------------------------- text helpers
def norm(tok):
    t = unicodedata.normalize("NFC", tok.lower())
    return "".join(c for c in t if unicodedata.category(c)[0] not in "PSZC")


def tokens(text):
    """Display tokens: whitespace split; punctuation-only tokens (like '—') stick to the previous word."""
    out = []
    for raw in re.split(r"\s+", (text or "").strip()):
        if not raw:
            continue
        if norm(raw):
            out.append(raw)
        elif out:
            out[-1] += " " + raw
    return out


# ---------------------------------------------------------------- audio helpers
def to_wav(src, dst):
    ffmpeg("-i", src, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", dst)
    return dst


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise UGCError(f"{path} must be {SR} Hz mono 16-bit (use to_wav)")
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path, x):
    y = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(y.tobytes())
    return path


def silence(seconds):
    return np.zeros(int(round(seconds * SR)), dtype=np.float32)


def fade_edges(x):
    n = min(int(EDGE_FADE * SR), len(x) // 2)
    if n > 0:
        r = np.linspace(0, 1, n, dtype=np.float32)
        x = x.copy()
        x[:n] *= r
        x[-n:] *= r[::-1]
    return x


# ---------------------------------------------------------------- timing helpers
def _charmap(timed):
    pos, c = [], 0
    for txt, s, e in timed:
        n = max(1, len(norm(txt)))
        pos.append((c, n, s, e))
        c += n
    return pos, c


def _time_at(pos, p):
    k = max(0, bisect_right([q[0] for q in pos], p) - 1)
    c, n, s, e = pos[k]
    f = min(1.0, max(0.0, (p - c) / n))
    return s + f * (e - s)


def distribute(toks, timed):
    """Spread display tokens over timed words proportionally to their letters (handles 50 vs 'fifty')."""
    if not toks:
        return []
    pos, total_b = _charmap(timed)
    lens = [max(1, len(norm(t))) for t in toks]
    total_a, acc, out = sum(lens), 0, []
    for n in lens:
        a = acc * total_b / total_a
        b = (acc + n) * total_b / total_a - 1e-6
        s, e = _time_at(pos, a), _time_at(pos, b)
        out.append((s, max(e, s + 0.04)))
        acc += n
    return out


def align(script_toks, stt_words, fallback_span):
    """Give every script token a (start, end) using the transcript. Returns (times, match_ratio)."""
    if not stt_words:
        lo, hi = fallback_span
        return distribute(script_toks, [("x" * sum(len(norm(t)) for t in script_toks), lo, hi)]), 0.0
    a = [norm(t) for t in script_toks]
    b = [norm(w["text"]) for w in stt_words]
    times = [None] * len(a)
    matched = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = stt_words[j1 + k]
                times[i1 + k] = (w["start"], w["end"])
            matched += i2 - i1
        elif tag == "replace":
            span = [(w["text"], w["start"], w["end"]) for w in stt_words[j1:j2]]
            for k, se in enumerate(distribute(script_toks[i1:i2], span)):
                times[i1 + k] = se
    i, n = 0, len(times)
    while i < n:  # script words the transcript missed: spread them between their neighbours
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 else stt_words[0]["start"]
        right = times[j][0] if j < n else stt_words[-1]["end"]
        if right <= left:
            right = left + 0.25 * (j - i)
        chunk = script_toks[i:j]
        for k, se in enumerate(distribute(chunk, [("x" * sum(len(norm(t)) for t in chunk), left, right)])):
            times[i + k] = se
        i = j
    out, prev_s = [], 0.0
    for s, e in times:
        s = max(s, prev_s)
        out.append((s, max(e, s + 0.04)))
        prev_s = s
    return out, matched / max(1, len(a))


def tighten(x, times, max_gap):
    """Shorten every pause longer than max_gap (s). Returns (audio, remap_fn)."""
    ident = (x, lambda t: t)
    if not max_gap or len(times) < 2:
        return ident
    cuts = []
    for (_, e0), (s1, _) in zip(times, times[1:]):
        if s1 - e0 > max_gap + 0.02:
            cuts.append((e0 + max_gap / 2, s1 - max_gap / 2))
    if not cuts:
        return ident
    keep, cur = [], 0.0
    for a, b in cuts:
        keep.append((cur, a))
        cur = b
    keep.append((cur, len(x) / SR))
    xf = int(XFADE * SR)
    out = x[int(round(keep[0][0] * SR)):int(round(keep[0][1] * SR))]
    offsets, acc = [0.0], (keep[0][1] - keep[0][0])
    ramp = np.linspace(0, 1, xf, dtype=np.float32)
    for a, b in keep[1:]:
        piece = x[int(round(a * SR)):int(round(b * SR))]
        if len(out) > xf and len(piece) > xf:
            out = np.concatenate([out[:-xf], out[-xf:] * (1 - ramp) + piece[:xf] * ramp, piece[xf:]])
            offsets.append(acc - XFADE)
            acc += (b - a) - XFADE
        else:
            out = np.concatenate([out, piece])
            offsets.append(acc)
            acc += b - a

    def remap(t):
        for k, (a, b) in enumerate(keep):
            if t <= b or k == len(keep) - 1:
                return offsets[k] + (max(a, t) - a)
        return t

    return out, remap


def split_source(x, seg_list, max_gap, stt_words, label):
    """Cut one audio source into per-segment slices. Returns {seg_id: (audio, [(tok, s, e)])}."""
    dur = len(x) / SR
    toks, owner = [], []
    for seg in seg_list:
        t = tokens(seg["say"])
        toks += t
        owner += [seg["id"]] * len(t)
    times, ratio = align(toks, stt_words, (0.1, max(0.2, dur - 0.1)))
    if stt_words and ratio < 0.5:
        warn(f"[{label}] the transcript matches only {ratio:.0%} of the script words - listen to "
             f"vo_preview.mp3: the voice may have skipped or mispronounced words (or the language is off)")
    y, remap = tighten(x, times, max_gap)
    times = [(remap(s), remap(e)) for s, e in times]
    dur = len(y) / SR
    first, last = {}, {}
    for i, sid in enumerate(owner):
        first.setdefault(sid, i)
        last[sid] = i
    result = {}
    for k, seg in enumerate(seg_list):
        sid = seg["id"]
        s_first, e_last = times[first[sid]][0], times[last[sid]][1]
        start = max(0.0, s_first - LEAD)
        if k > 0:
            prev_e = times[last[seg_list[k - 1]["id"]]][1]
            start = max(start, (prev_e + s_first) / 2)
        end = min(dur, e_last + TAIL)
        if k < len(seg_list) - 1:
            next_s = times[first[seg_list[k + 1]["id"]]][0]
            end = min(end, (e_last + next_s) / 2)
        piece = fade_edges(y[int(round(start * SR)):int(round(end * SR))])
        words = [(toks[i], round(times[i][0] - start, 3), round(times[i][1] - start, 3))
                 for i in range(first[sid], last[sid] + 1)]
        result[sid] = (piece, words)
    return result


# ---------------------------------------------------------------- providers
def tts_segment(job, seg, prev_text, next_text, force=False):
    """Generate (or reuse) the raw voice file for one segment. Returns a wav path."""
    v, m = job.plan["voice"], job.models
    src_dir = job.work / "voice" / "src"
    if v["provider"] == "fal":
        endpoint = v.get("model") or m["tts"]["endpoint"]
        settings = {k: v[k] for k in ("voice", "stability", "similarity_boost", "style", "speed", "language_code")}
        sig = {"p": "fal", "e": endpoint, "s": settings, "t": seg["say"]}
    else:
        model_id = v.get("model") or m["elevenlabs_direct"]["model_id"]
        settings = {k: v[k] for k in ("voice", "stability", "similarity_boost", "style", "speed", "language_code")}
        sig = {"p": "elevenlabs", "e": model_id, "s": settings, "t": seg["say"]}
    if job.mock:
        sig["mock"] = True
    h = obj_hash(sig)
    raw = src_dir / f"{seg['id']}.{'wav' if job.mock else 'mp3'}"
    wav = src_dir / f"{seg['id']}.wav"
    rec = job.state.get("voice_src", seg["id"])
    if rec and rec.get("hash") == h and wav.exists() and not force:
        return wav, False
    price = (m["tts"] if v["provider"] == "fal" else m["elevenlabs_direct"])["price_per_1k_chars"]
    if job.mock:
        mock.tts(seg["say"], wav)
    elif v["provider"] == "fal":
        allowed = set(m["tts"].get("params") or [])
        args = {"text": seg["say"], "voice": v["voice"], "stability": v["stability"],
                "similarity_boost": v["similarity_boost"], "style": v["style"], "speed": v["speed"],
                "previous_text": prev_text, "next_text": next_text, "language_code": v["language_code"],
                "apply_text_normalization": "auto"}
        args = {k: val for k, val in args.items() if k in allowed and val not in (None, "")}
        res = job.fal.run(endpoint, args, key=f"tts:{seg['id']}", label=f"voice {seg['id']}")
        download(res["audio"]["url"], raw)
        to_wav(raw, wav)
    else:
        es = {"stability": v["stability"], "similarity_boost": v["similarity_boost"], "style": v["style"],
              "speed": v["speed"], "use_speaker_boost": True}
        elevenlabs_tts(seg["say"], v["voice"], model_id, es, raw, prev_text, next_text, v["language_code"])
        to_wav(raw, wav)
    job.spend("voice", seg["id"], len(seg["say"]) / 1000 * price)
    job.state.put("voice_src", seg["id"], {"hash": h, "file": str(wav.name)})
    return wav, True


def transcribe(job, wav, label):
    """Word timings for an audio file (cached by content)."""
    fh = file_hash(wav)
    cache = job.work / "voice" / "src" / f"{wav.stem}.{fh}.words.json"
    if cache.exists():
        return load_json(cache)
    if job.mock:
        words = mock.stt(wav)
    else:
        args = {"audio_url": job.fal.upload(wav), "diarize": False, "tag_audio_events": False}
        lang = {"en": "eng", "hi": "hin"}.get(job.plan["language"])
        if lang:
            args["language_code"] = lang
        res = job.fal.run(job.models["stt"]["endpoint"], args, key=f"stt:{fh}", label=f"timings {label}")
        words = [{"text": w["text"], "start": float(w["start"]), "end": float(w["end"])}
                 for w in res.get("words", []) if w.get("type", "word") == "word" and w.get("start") is not None]
    secs = len(read_wav(wav)) / SR
    job.spend("timings", label, secs / 60 * job.models["stt"]["price_per_minute"])
    save_json(words, cache)
    return words


# ---------------------------------------------------------------- stage
def run_voice(job, only=None):
    p = job.plan
    v = p["voice"]
    speaking = [s for s in job.segments if s["say"]]
    max_gap = p["finish"].get("tighten_pauses")
    vdir = job.work / "voice"
    results = {}
    if v["provider"] == "file":
        src = to_wav(job.path(v["file"]), vdir / "src" / "recording.wav")
        words = transcribe(job, src, "recording")
        results.update(split_source(read_wav(src), speaking, max_gap, words, "recording"))
    else:
        def one(i):
            seg = speaking[i]
            prev_t = speaking[i - 1]["say"] if i > 0 else None
            next_t = speaking[i + 1]["say"] if i + 1 < len(speaking) else None
            force = job.force and (not only or seg["id"] in only)
            wav, _ = tts_segment(job, seg, prev_t, next_t, force=force)
            words = transcribe(job, wav, seg["id"])
            return split_source(read_wav(wav), [seg], max_gap, words, seg["id"])
        with ThreadPoolExecutor(max_workers=int(job.models.get("concurrency", 3))) as ex:
            for r in ex.map(one, range(len(speaking))):
                results.update(r)

    ec = p["endcard"]
    timeline, rows, chunks = [], [], []
    for seg in job.segments:
        entry = {"id": seg["id"], "shot": seg["shot"], "audio": None, "words": []}
        if seg["say"]:
            audio, words = results[seg["id"]]
            if seg["shot"] == "endcard":
                audio = np.concatenate([audio, silence(float(ec.get("hold_after_voice", 0.8)))])
            wav = vdir / "seg" / f"{seg['id']}.wav"
            write_wav(wav, audio)
            if seg["shot"] == "talk":  # compressed copy to upload to the lip-sync model
                ffmpeg("-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", wav.with_suffix(".mp3"))
            entry["audio"] = f"voice/seg/{seg['id']}.wav"
            entry["words"] = [{"t": t, "s": s, "e": e} for t, s, e in words]
            entry["dur"] = round(len(audio) / SR, 4)
        else:
            hold = float(seg.get("hold") or (ec.get("hold", 2.5) if seg["shot"] == "endcard" else 2.0))
            audio = silence(hold)
            entry["dur"] = hold
        chunks.append(audio)
        timeline.append(entry)
        rows.append([seg["id"], seg["shot"], f"{entry['dur']:5.2f}s", (seg["say"] or "(silent)")[:58]])
    total = sum(e["dur"] for e in timeline)
    voice_fields = [{k: s.get(k) for k in ("id", "shot", "say", "hold")} for s in job.segments]
    save_json({"segments": timeline, "total": round(total, 4), "voice_hash": obj_hash(voice_fields)},
              job.work / "timeline.json")
    write_wav(vdir / "vo_preview.wav", np.concatenate(chunks))
    ffmpeg("-i", vdir / "vo_preview.wav", "-c:a", "libmp3lame", "-b:a", "160k", vdir / "vo_preview.mp3")
    print_table(rows, ["id", "shot", "length", "says"])
    log(f"\nVoice-over length: {total:.1f}s   preview: {vdir / 'vo_preview.mp3'}")
    if total < 20 or total > 60:
        warn(f"total {total:.1f}s is outside 20-60s: adjust the script or voice.speed, then re-run voice")
    for e in timeline:
        if e["shot"] == "talk" and e["dur"] < 1.5:
            warn(f"{e['id']} is only {e['dur']:.1f}s - consider merging it with a neighbour")
    return timeline
