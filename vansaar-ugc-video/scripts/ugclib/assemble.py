"""Assembly: frame-exact edit of all clips + phone-real audio + captions -> final 1080x1920 MP4.

Realism touches applied here (all subtle, all configurable in plan.finish):
  * jump-cut punch-ins between consecutive talking segments (like a creator trimming takes)
  * gentle handheld drift, phone-camera grade and fine temporal grain on AI footage
  * the clean TTS voice gets a small-room / phone-mic colour and a faint room tone
  * loudness normalised to -14 LUFS (Instagram / YouTube Shorts level)
"""
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .captions import build_ass
from .clips import load_timeline
from .util import FONTS_DIR, FPS, SR, H, W, UGCError, ffmpeg, log, run
from .voice import read_wav, silence, write_wav


def _even(v):
    return int(round(v / 2)) * 2


def frame_plan(timeline):
    acc, starts = 0.0, {}
    for e in timeline["segments"]:
        f0 = int(round(acc * FPS))
        acc += e["dur"]
        e["f0"], e["nf"] = f0, int(round(acc * FPS)) - f0
        starts[e["id"]] = f0 / FPS
    return int(round(acc * FPS)), starts


def zooms(job):
    """Auto punch-in: alternate 1.0 / 1.1 on consecutive talking segments from the same setup."""
    out, prev_setup, level = {}, None, 0
    for s in job.segments:
        if s["shot"] != "talk":
            prev_setup = None
            continue
        if s.get("zoom"):
            out[s["id"]] = float(s["zoom"])
            prev_setup = s["setup"]
            continue
        level = level + 1 if s["setup"] == prev_setup else 0
        close = job.plan["setups"][s["setup"]]["framing"] == "close"
        punch = (1.07 if close else 1.12) if job.plan["finish"].get("punch_in", True) else 1.0
        out[s["id"]] = punch if level % 2 else 1.0
        prev_setup = s["setup"]
    return out


def norm_segment(job, seg, e, idx, zoom, dest):
    nf, fin = e["nf"], job.plan["finish"]
    if seg["shot"] == "endcard":
        src = job.work / "clips" / f"{seg['id']}.png"
        vf = (f"scale={W * 2}:{H * 2},zoompan=z='1+0.035*on/{max(nf, 1)}':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{H}:fps={FPS},format=yuv420p")
        ffmpeg("-i", src, "-vf", vf, "-frames:v", nf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
               "-pix_fmt", "yuv420p", "-an", dest)
        return dest
    if seg["shot"] == "broll" and seg["broll"]["video"]:
        src = job.path(seg["broll"]["video"])
    else:
        src = job.work / "clips" / f"{seg['id']}.mp4"
    if not src.exists():
        raise UGCError(f"{seg['id']}: clip missing ({src.name}) - run the clips step")
    amp = 14.0 * float(fin.get("handheld", 0.5))
    scale = zoom * (1 + 2.6 * amp / W)
    sw, sh = _even(W * scale), _even(H * scale)
    fy = 0.40 if seg["shot"] == "talk" else 0.5
    p1, p2 = 1.3 + idx * 1.7, 0.4 + idx * 2.3
    x = f"(iw-{W})/2+{amp:.2f}*(0.6*sin(2*PI*t*0.31+{p1:.2f})+0.4*sin(2*PI*t*0.83+{p2:.2f}))"
    y = f"(ih-{H})*{fy}+{0.75 * amp:.2f}*(0.6*sin(2*PI*t*0.27+{p2:.2f})+0.4*sin(2*PI*t*0.71+{p1:.2f}))"
    grain = float(fin.get("grain", 0.45))
    chain = [f"fps={FPS}", "tpad=stop_mode=clone:stop_duration=20", f"trim=end_frame={nf}", "setpts=PTS-STARTPTS",
             f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}:{x}:{y}",
             "setsar=1", "eq=contrast=1.03:saturation=1.04", "unsharp=5:5:0.35:5:5:0"]
    if grain > 0:
        chain.append(f"noise=c0s={int(round(2 + 7 * grain))}:c0f=t+u")
    chain.append("format=yuv420p")
    ffmpeg("-i", src, "-vf", ",".join(chain), "-frames:v", nf, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "15", "-pix_fmt", "yuv420p", "-an", dest)
    return dest


def build_audio(job, timeline, total_frames):
    n = int(round(total_frames / FPS * SR))
    pieces = [read_wav(job.work / e["audio"]) if e["audio"] else silence(e["dur"]) for e in timeline["segments"]]
    x = np.concatenate(pieces)
    x = np.pad(x, (0, max(0, n - len(x))))[:n]
    mix = job.work / "mix"
    write_wav(mix / "vo_timeline.wav", x)
    fin, music = job.plan["finish"], job.plan["music"]
    T = n / SR
    phone = bool(fin.get("phone_audio", True))
    voice = "highpass=f=80"
    if phone:
        voice += (",lowpass=f=13500,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2,"
                  "aecho=0.9:0.55:11|19:0.07|0.05")
    args, fc, ins = ["-i", mix / "vo_timeline.wav"], [], ["[vo]"]
    if music.get("file"):
        args = ["-i", mix / "vo_timeline.wav", "-stream_loop", "-1", "-i", job.path(music["file"])]
        fc.append(f"[0:a]{voice},asplit=2[vo][key]")
        fc.append(f"[1:a]aresample={SR},aformat=channel_layouts=mono,atrim=0:{T:.3f},"
                  f"volume={float(music.get('volume_db', -22))}dB[mus]")
        fc.append("[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400[duck]")
        ins.append("[duck]")
    else:
        fc.append(f"[0:a]{voice}[vo]")
    if phone:
        fc.append(f"anoisesrc=color=pink:amplitude=0.0012:sample_rate={SR}:duration={T:.3f},"
                  f"highpass=f=100,lowpass=f=5000[room]")
        ins.append("[room]")
    if len(ins) > 1:
        fc.append(f"{''.join(ins)}amix=inputs={len(ins)}:normalize=0:duration=first[out]")
    else:
        fc.append("[vo]anull[out]")
    pre = mix / "premaster.wav"
    ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", "[out]", "-ac", "1", "-ar", SR, "-c:a", "pcm_s16le", pre)
    # two-pass loudness normalisation to -14 LUFS / -1.5 dBTP
    target = "I=-14:TP=-1.5:LRA=11"
    p = run(["ffmpeg", "-hide_banner", "-i", pre, "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    ln = f"loudnorm={target}"
    if m:
        meas = json.loads(m.group(0))
        if meas.get("input_i") not in (None, "-inf"):
            ln += (f":measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
                   f":measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true")
    final = mix / "final_audio.wav"
    ffmpeg("-i", pre, "-af", f"{ln},aresample={SR},apad=whole_len={n},atrim=end_sample={n}",
           "-ac", "1", "-ar", SR, "-c:a", "pcm_s16le", final)
    return final


def encode(job, ass_name, total_frames, dest):
    ffmpeg("-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", "mix/final_audio.wav",
           "-filter_complex", f"[0:v]subtitles={ass_name}:fontsdir=fonts[v]", "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "10M", "-bufsize", "20M",
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-r", FPS, "-g", FPS * 2, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "2",
           "-movflags", "+faststart", "-frames:v", total_frames, dest, cwd=job.work)
    return dest


def run_assemble(job):
    tl = load_timeline(job)
    total_frames, starts = frame_plan(tl)
    seg_by_id = {s["id"]: s for s in job.segments}
    zm = zooms(job)
    shutil.copytree(FONTS_DIR, job.work / "fonts", dirs_exist_ok=True)
    log(f"Editing {len(tl['segments'])} segments, {total_frames / FPS:.2f}s…")

    def one(args):
        i, e = args
        seg = seg_by_id[e["id"]]
        return norm_segment(job, seg, e, i, zm.get(e["id"], 1.0), job.work / "norm" / f"{e['id']}.mp4")

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, enumerate(tl["segments"])))
    (job.work / "concat.txt").write_text("".join(f"file 'norm/{e['id']}.mp4'\n" for e in tl["segments"]))
    build_audio(job, tl, total_frames)
    build_ass(job, tl, starts, job.work / "captions.ass", include_captions=True)
    final = job.out / f"{job.slug}.mp4"
    encode(job, "captions.ass", total_frames, final)
    log(f"Final video: {final}")
    if job.plan["captions"].get("clean_copy"):
        build_ass(job, tl, starts, job.work / "nocaptions.ass", include_captions=False)
        clean = job.out / f"{job.slug}_nocaptions.mp4"
        encode(job, "nocaptions.ass", total_frames, clean)
        log(f"Copy without captions: {clean}")
    return final
