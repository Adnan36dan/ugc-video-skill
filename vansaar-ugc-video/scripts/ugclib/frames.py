"""Keyframe stage: face photo + product photo -> photoreal 'phone video still' images.

Every talk *setup* gets 1-4 candidate stills (the lip-sync model animates the chosen one);
every generated B-roll shot gets its own still (the image-to-video model animates it).
A contact sheet (work/frames/contact.jpg) shows all candidates for review.
"""
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import mock
from .falapi import download
from .plan import setups_in_use
from .util import FONTS_DIR, UGCError, file_hash, log, obj_hash

FRAMING = {
    "close": ("close-up selfie framing: head and the top of the shoulders fill most of the frame, face centred "
              "in the upper half, phone held at arm's length slightly above eye level"),
    "medium": ("medium selfie framing from mid-chest up with some of the room visible behind, phone held at "
               "arm's length at eye level, face in the upper third"),
    "product": ("medium framing from the waist up; {p} holds the product from the product reference in one hand "
                "at chest height beside {pos} face, label turned to the camera, fingers not covering the logo; "
                "the face stays fully visible and unobstructed"),
}

PRONOUNS = {"she": ("she", "her"), "he": ("he", "his"), "they": ("they", "their")}

AVOID = ("text overlays, captions, subtitles, watermarks, extra logos, a visible phone or selfie stick, mirrors, "
         "other people, extra or fused fingers, distorted hands, warped or invented packaging text, studio "
         "backdrop, ring-light reflections in the eyes, beauty-filter skin, cinematic colour grading")


def identity_clause(ref_no, description):
    return (f"IDENTITY (most important): the person is exactly the person in image {ref_no} - same face shape, "
            f"eyes, eyebrows, nose, lips, teeth, skin tone, apparent age, wrinkles, moles and marks, hairline, "
            f"hair colour and hairstyle. Do not beautify, de-age, slim, lighten or otherwise change them. "
            f"{description}".strip())


def product_clause(ref_no, product_name):
    name = f" ({product_name})" if product_name else ""
    return (f"PRODUCT: the product{name} is exactly the one in image {ref_no}. Reproduce its packaging exactly: "
            f"same shape, proportions, colours, cap, logo and label layout; keep every word of the label "
            f"identical and legible, never invent or alter text; correct real-world size relative to the hand.")


def talk_prompt(plan, setup):
    ch = plan["character"]
    p, pos = PRONOUNS.get(ch.get("pronoun", "she"), PRONOUNS["they"])
    framing = FRAMING[setup["framing"]].format(p=p, pos=pos)
    with_product = setup["with_product"] or setup["framing"] == "product"
    parts = [
        "Create one photorealistic vertical 9:16 image. It must look like a real frame grabbed from a selfie "
        "video that an ordinary person recorded on a smartphone front camera at home for Instagram - not an "
        "advert, not a studio photo, not AI art.",
        identity_clause(1, ch.get("description", "")),
        "SKIN AND DETAIL: real, unretouched skin with visible pores, fine lines, natural under-eye texture and "
        "slight unevenness; natural hair flyaways; clothes with real fabric creases. No beauty filter, no waxy or "
        "plastic skin, no glamour make-up beyond what image 1 shows.",
        f"FRAMING: {framing}. Eyes look straight into the lens. Mouth relaxed and closed or very slightly parted, "
        "neutral friendly expression (this frame will be animated into speech). Nothing covers the mouth or eyes.",
        f"SETTING: {setup['scene']}. A real, lived-in Indian home with ordinary furniture and a few everyday "
        "objects, slightly imperfect tidiness. Background in natural focus like a phone camera (mild blur only, "
        "no portrait-mode bokeh).",
        "LIGHT AND CAMERA: soft daylight from a window, realistic exposure and gentle shadows, true-to-life skin "
        "colour. Smartphone front camera look: 24-28 mm equivalent, mild wide-angle perspective, slight HDR, "
        "faint sensor noise in the shadows.",
        product_clause(2, plan.get("product_name")) if with_product else "PRODUCT: no product in this frame.",
        f"DO NOT include: {AVOID}.",
    ]
    return "\n\n".join(parts), with_product


def broll_prompt(plan, b):
    refs, parts = [], [
        "Create one photorealistic vertical 9:16 image that looks like a real frame from a smartphone video "
        "shot by an ordinary person at home (a cut-away shot for an Instagram reel) - not an advert, not a "
        "studio photo, not AI art.",
        f"SCENE: {b['scene']}",
    ]
    if b["with_person"]:
        refs.append("face")
        parts.append(identity_clause(len(refs), plan["character"].get("description", "")) +
                     " Real, unretouched skin texture.")
    if b["with_product"]:
        refs.append("product")
        parts.append(product_clause(len(refs), plan.get("product_name")))
    parts += [
        "LIGHT AND CAMERA: natural daylight, realistic exposure, handheld phone camera, natural depth of field, "
        "faint sensor noise, true-to-life colour.",
        f"DO NOT include: {AVOID}.",
    ]
    return "\n\n".join(parts), refs


def keyframe_jobs(job):
    """List of keyframe tasks: {key, prompt, refs: [paths], n, pick}."""
    p, tasks = job.plan, []
    face, product = job.path(p["inputs"].get("face")), job.path(p["inputs"].get("product"))
    for name in setups_in_use(job):
        st = p["setups"][name]
        prompt, with_product = talk_prompt(p, st)
        roles = ["face"] + (["product"] if with_product else [])
        tasks.append({"key": f"setup_{name}", "prompt": prompt, "roles": roles,
                      "refs": [face if r == "face" else product for r in roles],
                      "n": int(st["candidates"]), "pick": int(st["pick"])})
    for s in job.segments:
        if s["shot"] != "broll":
            continue
        b = s["broll"]
        if b["video"] or b["image"]:
            continue
        prompt, roles = broll_prompt(p, b)
        tasks.append({"key": f"broll_{s['id']}", "prompt": prompt, "roles": roles,
                      "refs": [face if r == "face" else product for r in roles],
                      "n": int(b["candidates"]), "pick": int(b["pick"])})
    return tasks


def frame_dir(job, key):
    d = job.work / "frames" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def chosen(job, key, pick):
    f = frame_dir(job, key) / f"v{pick}.png"
    if not f.exists():
        raise UGCError(f"keyframe {key} v{pick} does not exist yet - run the frames step (or fix 'pick')")
    return f


def _generate(job, t):
    m = job.models["image"]
    d = frame_dir(job, t["key"])
    sig = {"e": m["endpoint"], "d": m.get("defaults"), "p": t["prompt"], "r": [file_hash(r) for r in t["refs"]],
           "n": t["n"], "mock": job.mock}
    h = obj_hash(sig)
    files = [d / f"v{i}.png" for i in range(1, t["n"] + 1)]
    rec = job.state.get("frames", t["key"])
    if rec and rec.get("hash") == h and all(f.exists() for f in files) and not job.force:
        log(f"  [{t['key']}] keyframes already made (use --force to redo)")
        return files
    (d / "prompt.txt").write_text(t["prompt"], encoding="utf-8")
    if job.mock:
        face = next((r for r, role in zip(t["refs"], t["roles"]) if role == "face"), None)
        prod = next((r for r, role in zip(t["refs"], t["roles"]) if role == "product"), None)
        for i, f in enumerate(files, 1):
            mock.image(t["key"], f, face=face, product=prod, variant=i)
    else:
        names = m.get("arg_names") or {}
        args = dict(m.get("defaults") or {})
        args[names.get("prompt", "prompt")] = t["prompt"]
        args[names.get("images", "image_urls")] = [job.fal.upload(r) for r in t["refs"]]
        args[names.get("count", "num_images")] = t["n"]
        res = job.fal.run(m["endpoint"], args, key=f"frames:{t['key']}", label=f"keyframes {t['key']}")
        imgs = res.get("images") or []
        if not imgs:
            raise UGCError(f"[{t['key']}] the image model returned no image (it may have refused the prompt): "
                           f"{str(res)[:300]}")
        for i, f in enumerate(files, 1):
            src = imgs[min(i, len(imgs)) - 1]["url"]
            download(src, f.with_suffix(".dl"))
            Image.open(f.with_suffix(".dl")).convert("RGB").save(f)
            f.with_suffix(".dl").unlink()
    job.spend("keyframes", t["key"], t["n"] * m["price_per_image"])
    job.state.put("frames", t["key"], {"hash": h, "files": [f.name for f in files]})
    return files


def contact_sheet(job, tasks):
    cells = []
    for t in tasks:
        for i in range(1, t["n"] + 1):
            f = frame_dir(job, t["key"]) / f"v{i}.png"
            if f.exists():
                cells.append((f"{t['key']}  v{i}" + ("  (picked)" if i == t["pick"] else ""), f))
    if not cells:
        return None
    cw, ch, cols = 360, 640, 4
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + 50)), (24, 24, 24))
    font = ImageFont.truetype(str(FONTS_DIR / "Manrope-ExtraBold.ttf"), 24)
    for k, (label, f) in enumerate(cells):
        im = ImageOps.fit(Image.open(f).convert("RGB"), (cw - 10, ch - 10))
        x, y = (k % cols) * cw, (k // cols) * (ch + 50)
        sheet.paste(im, (x + 5, y + 5))
        ImageDraw.Draw(sheet).text((x + 10, y + ch + 8), label, font=font, fill=(255, 255, 255))
    out = job.work / "frames" / "contact.jpg"
    sheet.save(out, quality=88)
    return out


def run_frames(job, only=None):
    tasks = keyframe_jobs(job)
    if only:
        tasks = [t for t in tasks if t["key"] in only or t["key"].split("_", 1)[1] in only]
        if not tasks:
            raise UGCError(f"nothing matches --only {only}")
    log(f"Keyframes: {len(tasks)} shot(s), {sum(t['n'] for t in tasks)} image(s)")
    errors = []
    with ThreadPoolExecutor(max_workers=int(job.models.get("concurrency", 3))) as ex:
        futs = {ex.submit(_generate, job, t): t for t in tasks}
        for fut, t in futs.items():
            try:
                fut.result()
            except UGCError as e:
                errors.append(f"{t['key']}: {e}")
    sheet = contact_sheet(job, keyframe_jobs(job))
    if sheet:
        log(f"Contact sheet: {sheet}")
    if errors:
        raise UGCError("some keyframes failed:\n" + "\n".join(errors))
