"""Automatic checks on the finished video + a contact sheet for a visual review."""
import json
import re

from PIL import Image, ImageDraw, ImageFont

from .assemble import frame_plan
from .clips import load_timeline
from .util import FONTS_DIR, FPS, H, W, ffmpeg, ffprobe, log, run, save_json


def _loudness(path):
    p = run(["ffmpeg", "-hide_banner", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    return json.loads(m.group(0)) if m else {}


def _events(path, vf, key):
    p = run(["ffmpeg", "-hide_banner", "-i", path, "-vf", vf, "-an", "-f", "null", "-"])
    return p.stderr.splitlines() if key is None else [l for l in p.stderr.splitlines() if key in l]


def run_qa(job):
    final = job.out / f"{job.slug}.mp4"
    tl = load_timeline(job)
    total_frames, starts = frame_plan(tl)
    report, problems, notes = {"file": str(final)}, [], []
    info = ffprobe(final)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    report.update({"width": v["width"], "height": v["height"], "fps": v.get("r_frame_rate"), "duration": dur,
                   "video_codec": v["codec_name"], "audio": bool(a),
                   "size_mb": round(int(info["format"]["size"]) / 1e6, 1)})
    if (v["width"], v["height"]) != (W, H):
        problems.append(f"resolution is {v['width']}x{v['height']}, expected {W}x{H}")
    if not a:
        problems.append("no audio track")
    if not 20 <= dur <= 60.5:
        problems.append(f"length {dur:.1f}s is outside 20-60s")
    if abs(dur - total_frames / FPS) > 0.15:
        notes.append(f"length {dur:.2f}s differs from the plan's {total_frames / FPS:.2f}s")
    ld = _loudness(final)
    if ld:
        report["loudness_lufs"], report["true_peak_db"] = float(ld["input_i"]), float(ld["input_tp"])
        if abs(report["loudness_lufs"] + 14) > 1.5:
            notes.append(f"loudness {report['loudness_lufs']:.1f} LUFS (target -14)")
        if report["true_peak_db"] > -0.5:
            problems.append(f"audio peaks at {report['true_peak_db']:.1f} dBTP (clipping risk)")
    blacks = [l for l in _events(final, "blackdetect=d=0.25:pix_th=0.08", "black_start")]
    if blacks:
        problems.append(f"{len(blacks)} black section(s): " + "; ".join(b.split("]")[-1].strip() for b in blacks[:3]))
    # frozen picture inside talking / b-roll segments = an AI clip shorter than its audio
    ec_ranges = [(starts[e["id"]], starts[e["id"]] + e["dur"]) for e in tl["segments"] if e["shot"] == "endcard"]
    for line in _events(final, "freezedetect=n=0.002:d=1.0", "freeze_start"):
        t = float(line.split("freeze_start:")[1].split()[0])
        if not any(lo - 0.2 <= t <= hi for lo, hi in ec_ranges):
            seg = max((e for e in tl["segments"] if starts[e["id"]] <= t + 1e-3), key=lambda e: starts[e["id"]])
            notes.append(f"picture looks frozen from {t:.1f}s (segment {seg['id']}) - check that clip")
    report["problems"], report["notes"] = problems, notes
    report["contact_sheet"] = str(contact(job, final, tl, starts))
    save_json(report, job.out / f"{job.slug}_qa.json")
    log(f"QA: {final.name}  {v['width']}x{v['height']}  {dur:.1f}s  "
        f"{report.get('loudness_lufs', float('nan')):.1f} LUFS  {report['size_mb']} MB")
    for p_ in problems:
        log(f"  FAIL  {p_}")
    for n_ in notes:
        log(f"  CHECK {n_}")
    if not problems and not notes:
        log("  PASS  all automatic checks")
    log(f"Contact sheet: {report['contact_sheet']}  (look at it: faces, hands, product label, captions)")
    return report


def contact(job, final, tl, starts):
    times = []
    for e in tl["segments"]:
        s0 = starts[e["id"]]
        times.append((e["id"], s0 + min(0.4, e["dur"] / 3)))
        if e["dur"] > 3.5:
            times.append((e["id"], s0 + e["dur"] * 0.7))
    tw, th, cols = 270, 480, 5
    rows = (len(times) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 36)), (20, 20, 20))
    font = ImageFont.truetype(str(FONTS_DIR / "Manrope-ExtraBold.ttf"), 20)
    tmp = job.work / "qa_frame.jpg"
    for k, (sid, t) in enumerate(times):
        ffmpeg("-ss", f"{t:.3f}", "-i", final, "-frames:v", "1", "-vf", f"scale={tw}:{th}", tmp)
        x, y = (k % cols) * tw, (k // cols) * (th + 36)
        sheet.paste(Image.open(tmp), (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + th + 6), f"{sid}  {t:5.1f}s", font=font, fill=(255, 255, 255))
    out = job.out / f"{job.slug}_contact.jpg"
    sheet.save(out, quality=88)
    return out
