#!/usr/bin/env python3
"""Vansaar UGC video pipeline - command line.

  python3 scripts/ugc.py doctor                       check installation, keys, network
  python3 scripts/ugc.py setkey [--elevenlabs]        save an API key (paste it, press Enter)
  python3 scripts/ugc.py init --job DIR --face F --product P --script S [--lang hi]
  python3 scripts/ugc.py check    --job DIR | --text "..." | --file script.txt
  python3 scripts/ugc.py validate --job DIR           plan errors + length estimate
  python3 scripts/ugc.py estimate --job DIR           cost estimate before spending
  python3 scripts/ugc.py voice    --job DIR [--only s02]
  python3 scripts/ugc.py frames   --job DIR [--only sofa_close]
  python3 scripts/ugc.py clips    --job DIR [--only s03]
  python3 scripts/ugc.py assemble --job DIR
  python3 scripts/ugc.py qa       --job DIR
  python3 scripts/ugc.py all      --job DIR           voice -> frames -> clips -> assemble -> qa
  python3 scripts/ugc.py demo     --out DIR           full free test run with --mock stand-ins

Add --mock to any step to use free offline stand-ins instead of paid AI models.
Add --force to redo work that is already cached.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ugclib import claims  # noqa: E402
from ugclib.util import FONTS_DIR, TEMPLATES_DIR, UGCError, log, load_yaml, run, save_yaml  # noqa: E402


# ------------------------------------------------------------------ helpers
def _job(args):
    from ugclib.job import Job
    return Job(args.job, mock=args.mock, force=args.force)


def _prepare_image(src, dest, keep_alpha=False):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src))
    im.thumbnail((2048, 2048))
    if keep_alpha and im.mode in ("RGBA", "LA", "P"):
        im.convert("RGBA").save(dest)
    else:
        im.convert("RGB").save(dest)
    return dest


def _split_script(text, lang):
    sentences = [s.strip() for s in re.split(r"(?<=[.?!।])\s+", text.strip()) if s.strip()]
    segs, cur = [], ""
    for s in sentences:
        if cur and len((cur + " " + s).split()) > 16:
            segs.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        segs.append(cur)
    return segs


def _plan_text(title, product_name, lang, face, product, script_segments):
    setups_cycle = ["main_close", "main_medium", "main_medium", "main_product"]
    lines = []
    for i, say in enumerate(script_segments, 1):
        last = i == len(script_segments)
        is_end = last and re.search(r"vansaar|link|order|shop", say, re.I)
        lines.append(f"  - id: s{i:02d}")
        if is_end:
            lines.append("    shot: endcard")
        else:
            lines.append("    shot: talk")
            lines.append(f"    setup: {setups_cycle[(i - 1) % len(setups_cycle)]}")
        lines.append(f"    say: {yaml_str(say)}")
        if not is_end:
            lines.append("    performance: natural, warm, conversational")
        lines.append("")
    return f"""# Plan for one UGC video. Edit freely, then: validate -> estimate -> voice -> frames -> clips -> assemble -> qa
# Field reference: references/plan-reference.md     Worked example: templates/plan.example.yaml

title: {yaml_str(title)}
product_name: {yaml_str(product_name)}
language: {lang}                       # spoken language: en or hi (Hinglish counts as hi)

inputs:
  face: {face}
  product: {product}

character:
  pronoun: she                     # she | he | they
  description: ""                  # describe the face photo: age, hair, clothes (reinforces identity)

voice:
  provider: fal                    # fal | elevenlabs (direct, Indian voice library) | file (real recording)
  voice: ""                        # REQUIRED: see references/script-and-voice.md
  speed: 1.03
  stability: 0.42
  similarity_boost: 0.8
  style: 0.2
  file: null                       # for provider: file -> path to the recording

setups:                            # "camera positions" in one home; 2-3 looks like one real session
  main_medium:
    scene: ""                      # REQUIRED: where, what is behind them, light
    framing: medium                # close | medium | product
    candidates: 2
    pick: 1
  main_close:
    scene: ""
    framing: close
    candidates: 2
    pick: 1
  main_product:
    scene: ""
    framing: product
    candidates: 2
    pick: 1

segments:
{chr(10).join(lines)}
captions:
  words_per_card: 3
  position: 0.70

finish:
  tighten_pauses: 0.30
  grain: 0.45
  handheld: 0.5
  phone_audio: true

endcard:
  cta: "Shop at vansaar.com"
  accent: "Rooted in Ayurveda"
  theme: dark

music:
  file: null
  volume_db: -22
"""


def yaml_str(s):
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


# ------------------------------------------------------------------ commands
def cmd_doctor(args):
    ok = True
    log(f"python {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        log("  FAIL  Python 3.9+ is required")
        ok = False
    for mod, pip in (("yaml", "pyyaml"), ("numpy", "numpy"), ("PIL", "pillow"), ("requests", "requests"),
                     ("fal_client", "fal-client")):
        try:
            __import__(mod)
            log(f"  ok    {pip}")
        except ImportError:
            log(f"  FAIL  {pip} missing -> pip install -r requirements.txt")
            ok = False
    for b in ("ffmpeg", "ffprobe"):
        if shutil.which(b):
            log(f"  ok    {b}")
        else:
            log(f"  FAIL  {b} missing -> see references/troubleshooting.md")
            ok = False
    if shutil.which("ffmpeg"):
        filters = run(["ffmpeg", "-hide_banner", "-filters"], capture=True)
        if " subtitles " in filters:
            log("  ok    ffmpeg has libass (captions)")
        else:
            log("  FAIL  this ffmpeg has no libass/subtitles filter -> install a full ffmpeg build")
            ok = False
    fonts = sorted(p.name for p in FONTS_DIR.glob("*.ttf"))
    log(f"  {'ok  ' if len(fonts) >= 3 else 'FAIL'}  fonts: {', '.join(fonts)}")
    from ugclib.falapi import elevenlabs_key, fal_key
    k = fal_key()
    log(f"  {'ok  ' if k else 'MISSING'}  fal.ai key{' (…' + k[-4:] + ')' if k else ' -> run: ugc.py setkey'}")
    ek = elevenlabs_key()
    log(f"  {'ok  ' if ek else 'info'}  ElevenLabs key {'found' if ek else 'not set (only needed for voice.provider: elevenlabs)'}")
    try:
        import requests
        requests.head("https://queue.fal.run", timeout=8)
        log("  ok    network can reach fal.ai")
    except Exception as e:  # noqa: BLE001
        log(f"  FAIL  cannot reach fal.ai ({type(e).__name__}). Allow these domains: queue.fal.run, rest.fal.ai, "
            f"*.fal.media, storage.googleapis.com (and api.elevenlabs.io for direct ElevenLabs)")
        ok = False
    log("\nREADY" if ok and k else "\nNOT READY - fix the items above (use --mock to test without keys)")
    return 0 if ok else 1


def cmd_setkey(args):
    from ugclib.falapi import ELEVEN_KEY_FILE, KEY_FILE, save_key
    target = ELEVEN_KEY_FILE if args.elevenlabs else KEY_FILE
    key = (args.key or sys.stdin.readline()).strip()
    if len(key) < 10:
        raise UGCError("that does not look like an API key")
    path = save_key(key, target)
    log(f"Saved to {path} (only readable by you). Never paste keys into plan files or chat logs you share.")
    return 0


def cmd_init(args):
    job = Path(args.job).expanduser().resolve()
    if (job / "plan.yaml").exists() and not args.overwrite:
        raise UGCError(f"{job / 'plan.yaml'} already exists (use --overwrite to replace it)")
    (job / "inputs").mkdir(parents=True, exist_ok=True)
    face = _prepare_image(args.face, job / "inputs" / "face.png") if args.face else None
    product = _prepare_image(args.product, job / "inputs" / "product.png", keep_alpha=True) if args.product else None
    text = ""
    if args.script:
        text = Path(args.script).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    if text:
        (job / "inputs" / "script.txt").write_text(text, encoding="utf-8")
    segs = _split_script(text, args.lang) if text else ["(write the first line here)"]
    (job / "plan.yaml").write_text(_plan_text(args.title or job.name, args.product_name or "", args.lang,
                                              "inputs/face.png" if face else "", "inputs/product.png" if product else "",
                                              segs), encoding="utf-8")
    log(f"Job created: {job}\n  plan: {job / 'plan.yaml'}  ({len(segs)} draft segments - refine them)")
    return 0


def cmd_check(args):
    if args.job:
        from ugclib.job import Job
        items = claims.plan_texts(Job(args.job, mock=True))
    elif args.file:
        items = [(f"line {i}", l) for i, l in enumerate(Path(args.file).read_text(encoding="utf-8").splitlines(), 1)]
    else:
        items = [("text", args.text or "")]
    text, counts = claims.report(claims.check_texts(items))
    log(text)
    return 2 if (args.strict and counts["HIGH"]) else 0


def cmd_validate(args):
    from ugclib.plan import print_timeline_estimate, validate
    job = _job(args)
    errors, warns = validate(job)
    print_timeline_estimate(job)
    _, counts = claims.report(claims.check_texts(claims.plan_texts(job)))
    log(f"Script check: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM"
        + (" -> run 'check' for details and safer wording" if counts["HIGH"] + counts["MEDIUM"] else ""))
    for w in warns:
        log(f"WARNING: {w}")
    for e in errors:
        log(f"ERROR: {e}")
    log("\nPlan OK" if not errors else f"\n{len(errors)} error(s) to fix")
    return 1 if errors else 0


def _require_valid(job):
    from ugclib.plan import validate
    errors, warns = validate(job)
    for w in warns:
        log(f"WARNING: {w}")
    if errors:
        raise UGCError("plan has errors - run validate:\n  " + "\n  ".join(errors))


def cmd_estimate(args):
    from ugclib.plan import estimate_cost
    estimate_cost(_job(args))
    return 0


def cmd_voice(args):
    from ugclib.voice import run_voice
    job = _job(args)
    _require_valid(job)
    run_voice(job, only=args.only)
    _spent(job)
    return 0


def cmd_frames(args):
    from ugclib.frames import run_frames
    job = _job(args)
    _require_valid(job)
    run_frames(job, only=args.only)
    _spent(job)
    return 0


def cmd_clips(args):
    from ugclib.clips import run_clips
    job = _job(args)
    _require_valid(job)
    run_clips(job, only=args.only)
    _spent(job)
    return 0


def cmd_assemble(args):
    from ugclib.assemble import run_assemble
    run_assemble(_job(args))
    return 0


def cmd_qa(args):
    from ugclib.qa import run_qa
    rep = run_qa(_job(args))
    return 1 if rep["problems"] else 0


def cmd_all(args):
    from ugclib.assemble import run_assemble
    from ugclib.clips import run_clips
    from ugclib.frames import run_frames
    from ugclib.qa import run_qa
    from ugclib.voice import run_voice
    job = _job(args)
    _require_valid(job)
    log("== voice ==")
    run_voice(job)
    log("\n== keyframes ==")
    run_frames(job)
    log("\n== clips ==")
    run_clips(job)
    log("\n== assemble ==")
    run_assemble(job)
    log("\n== qa ==")
    rep = run_qa(job)
    _spent(job)
    return 1 if rep["problems"] else 0


def cmd_demo(args):
    from ugclib import mock
    out = Path(args.out).expanduser().resolve()
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    mock.demo_inputs(out / "inputs")
    plan = load_yaml(TEMPLATES_DIR / "plan.example.yaml")
    plan["voice"]["voice"] = "mock"
    if args.lang == "en":
        plan["language"] = "en"
        plan["title"] = "Liquid Collagen - morning routine (English)"
        english = ["If you're over fifty, this video is for you.",
                   "Every morning I add Vansaar Liquid Collagen to my routine.",
                   "It has sea buckthorn and amla, both known as good sources of vitamin C.",
                   "The taste is nice, and the routine is really easy to follow.",
                   "Just one thing: before starting any supplement, please talk to your doctor.",
                   "The link is below: vansaar dot com."]
        for seg, line in zip(plan["segments"], english):
            seg["say"], seg["caption"] = line, None
    save_yaml(plan, out / "plan.yaml")
    log(f"Demo job: {out}  (mock mode: no API calls, no cost)")
    args.job, args.mock = str(out), True
    return cmd_all(args)


def _spent(job):
    if not job.mock:
        log(f"\nEstimated spend on this job so far: ${job.state.spent():.2f}")


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Vansaar realistic UGC video pipeline", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, job=True):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        if job:
            p.add_argument("--job", required=True, help="job folder (contains plan.yaml)")
        p.add_argument("--mock", action="store_true", help="free offline stand-ins instead of paid models")
        p.add_argument("--force", action="store_true", help="redo cached work")
        return p

    add("doctor", cmd_doctor, job=False)
    p = add("setkey", cmd_setkey, job=False)
    p.add_argument("--elevenlabs", action="store_true", help="save an ElevenLabs key instead of fal.ai")
    p.add_argument("--key", help=argparse.SUPPRESS)
    p = add("init", cmd_init)
    p.add_argument("--face")
    p.add_argument("--product")
    p.add_argument("--script", help="text file with the script")
    p.add_argument("--text", help="the script as a string")
    p.add_argument("--title")
    p.add_argument("--product-name")
    p.add_argument("--lang", default="en", choices=["en", "hi"])
    p.add_argument("--overwrite", action="store_true")
    p = add("check", cmd_check, job=False)
    p.add_argument("--job")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--strict", action="store_true", help="exit code 2 if anything HIGH is found")
    add("validate", cmd_validate)
    add("estimate", cmd_estimate)
    for name, fn in (("voice", cmd_voice), ("frames", cmd_frames), ("clips", cmd_clips)):
        p = add(name, fn)
        p.add_argument("--only", nargs="+", help="only these segment ids / setup names")
    add("assemble", cmd_assemble)
    add("qa", cmd_qa)
    add("all", cmd_all)
    p = add("demo", cmd_demo, job=False)
    p.add_argument("--out", required=True)
    p.add_argument("--lang", default="hi", choices=["en", "hi"])
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except UGCError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Re-run the same command to continue; finished work is cached.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
