"""Clip stage: talking clips (keyframe + voice slice -> lip-sync video), B-roll, end card."""
from concurrent.futures import ThreadPoolExecutor

from . import frames, mock
from .endcard import render_endcard
from .falapi import download
from .plan import pick_duration
from .util import FPS, H, W, UGCError, duration, ffmpeg, file_hash, load_json, log, obj_hash, warn

NEGATIVE = ("warped or morphing packaging, changing or gibberish label text, extra fingers, deformed hands, face "
            "distortion, identity change, flicker, slow motion, cinematic lighting, text overlay, watermark, "
            "blur, low quality")


def performance_prompt(plan, seg):
    pron = {"she": "She", "he": "He"}.get(plan["character"].get("pronoun", "she"), "They")
    text = (f"{pron} talks to the phone camera like a natural, unscripted selfie video for friends: relaxed and "
            f"warm, natural blinking, small head movements and nods, an occasional small hand gesture, subtle "
            f"breathing.")
    if seg.get("performance"):
        text += f" {seg['performance'].rstrip('.')}."
    text += (" Handheld phone camera with very slight natural movement. Keep the face identity, the room and any "
             "product exactly as in the image; the product packaging stays rigid and its label unchanged.")
    return text


def motion_prompt(motion):
    return (f"{motion.rstrip('.')}. Shot on a handheld smartphone in natural light, realistic everyday motion at "
            f"normal speed, subtle camera shake. Keep the person's face and the product packaging exactly as in "
            f"the image; the label text stays unchanged and legible.")


def load_timeline(job):
    tl = load_json(job.work / "timeline.json")
    if not tl:
        raise UGCError("no timeline yet - run the voice step first")
    voice_fields = [{k: s.get(k) for k in ("id", "shot", "say", "hold")} for s in job.segments]
    if tl.get("voice_hash") and tl["voice_hash"] != obj_hash(voice_fields):
        raise UGCError("the script / segments changed after the voice step - run voice again first")
    return tl


def kenburns(image, seconds, dest, zoom_to=1.08):
    n = max(1, int(round(seconds * FPS)))
    ffmpeg("-i", image, "-vf",
           f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
           f"zoompan=z='1+{zoom_to - 1:.3f}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS}",
           "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", dest)
    return dest


def _cached(job, sid, h, dest):
    rec = job.state.get("clips", sid)
    return rec and rec.get("hash") == h and dest.exists() and not job.force


def _talk(job, seg, entry):
    m = job.models["avatar"]
    st = job.plan["setups"][seg["setup"]]
    kf = frames.chosen(job, f"setup_{seg['setup']}", int(st["pick"]))
    audio = job.work / "voice" / "seg" / f"{seg['id']}.mp3"
    prompt = performance_prompt(job.plan, seg)
    dest = job.work / "clips" / f"{seg['id']}.mp4"
    h = obj_hash({"e": m["endpoint"], "d": m.get("defaults"), "p": prompt, "k": file_hash(kf),
                  "a": file_hash(audio), "mock": job.mock})
    if _cached(job, seg["id"], h, dest):
        log(f"  [{seg['id']}] talking clip already made")
        return
    if job.mock:
        mock.avatar(kf, audio, dest)
    else:
        names = m.get("arg_names") or {}
        args = dict(m.get("defaults") or {})
        args[names.get("image", "image_url")] = job.fal.upload(kf)
        args[names.get("audio", "audio_url")] = job.fal.upload(audio)
        if names.get("prompt"):
            args[names["prompt"]] = prompt
        res = job.fal.run(m["endpoint"], args, key=f"clip:{seg['id']}", label=f"talking {seg['id']}")
        download(res["video"]["url"], dest)
    log(f"  [{seg['id']}] talking clip ready ({entry['dur']:.1f}s)")
    job.spend("talking clip", seg["id"], entry["dur"] * m["price_per_second"])
    job.state.put("clips", seg["id"], {"hash": h, "kind": "talk"})
    got = duration(dest)
    if got < entry["dur"] - 0.25:
        warn(f"{seg['id']}: clip is {got:.2f}s but its audio is {entry['dur']:.2f}s - the end will freeze")


def _broll(job, seg, entry):
    b = seg["broll"]
    dest = job.work / "clips" / f"{seg['id']}.mp4"
    if b["video"]:
        log(f"  [{seg['id']}] using your own footage {b['video']}")
        job.state.put("clips", seg["id"], {"hash": file_hash(job.path(b["video"])), "kind": "footage"})
        return
    kf = job.path(b["image"]) if b["image"] else frames.chosen(job, f"broll_{seg['id']}", int(b["pick"]))
    motion = (b.get("motion") or "").strip()
    if not motion or motion.lower() == "kenburns":
        kenburns(kf, entry["dur"], dest)
        log(f"  [{seg['id']}] b-roll still with slow zoom ({entry['dur']:.1f}s, no cost)")
        job.state.put("clips", seg["id"], {"hash": file_hash(kf), "kind": "kenburns"})
        return
    m = job.models["broll"]
    sec, raw = pick_duration(m["duration_choices"], entry["dur"])
    prompt = motion_prompt(motion)
    h = obj_hash({"e": m["endpoint"], "d": m.get("defaults"), "p": prompt, "k": file_hash(kf), "s": raw,
                  "mock": job.mock})
    if _cached(job, seg["id"], h, dest):
        log(f"  [{seg['id']}] b-roll clip already made")
        return
    if job.mock:
        mock.i2v(kf, sec, dest)
    else:
        names = m.get("arg_names") or {}
        args = dict(m.get("defaults") or {})
        args[names.get("image", "image_url")] = job.fal.upload(kf)
        args[names.get("prompt", "prompt")] = prompt
        args[names.get("duration", "duration")] = raw
        if names.get("negative_prompt"):
            args[names["negative_prompt"]] = NEGATIVE
        res = job.fal.run(m["endpoint"], args, key=f"clip:{seg['id']}", label=f"b-roll {seg['id']}")
        download(res["video"]["url"], dest)
    log(f"  [{seg['id']}] b-roll clip ready ({sec:.0f}s generated, {entry['dur']:.1f}s used)")
    job.spend("b-roll clip", seg["id"], sec * m["price_per_second"])
    job.state.put("clips", seg["id"], {"hash": h, "kind": "broll"})


def run_clips(job, only=None):
    tl = load_timeline(job)
    entries = {e["id"]: e for e in tl["segments"]}
    todo = [s for s in job.segments if not only or s["id"] in only]
    tasks = []
    for seg in todo:
        if seg["shot"] == "talk":
            tasks.append((_talk, seg))
        elif seg["shot"] == "broll":
            tasks.append((_broll, seg))
        elif seg["shot"] == "endcard":
            render_endcard(job, job.work / "clips" / f"{seg['id']}.png")
            log(f"  [{seg['id']}] end card rendered")
    errors = []
    with ThreadPoolExecutor(max_workers=int(job.models.get("concurrency", 3))) as ex:
        futs = [(ex.submit(fn, job, seg, entries[seg["id"]]), seg) for fn, seg in tasks]
        for fut, seg in futs:
            try:
                fut.result()
            except UGCError as e:
                errors.append(f"{seg['id']}: {e}")
    if errors:
        raise UGCError("some clips failed (the others are saved; re-run to retry only the failed ones):\n"
                       + "\n".join(errors))
    log(f"Clips ready in {job.work / 'clips'}")
