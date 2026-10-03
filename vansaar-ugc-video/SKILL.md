---
name: vansaar-ugc-video
description: Create ultra-realistic 20-60 second UGC-style vertical videos (Instagram Reels, YouTube Shorts, Meta ads) for Vansaar 45+ from a character face photo, a product photo and a script - an AI person speaks the script to a phone camera in a real-looking Indian home, holds the product, with B-roll cut-aways, word-by-word captions (English, Hinglish or Hindi), an AI-disclosure label and a branded end card. Use this whenever the user wants a UGC video, talking-head or testimonial-style reel, AI spokesperson / avatar / lip-sync video, or asks to turn a script plus a face into a video for any Vansaar product, even if they never say "UGC". Not for animating carousel PDFs (vansaar-animate) or building carousels.
---

# Vansaar UGC video

Face photo + product photo + script → a 9:16, 1080×1920, 30 fps MP4 that looks like a 45+ Indian
customer filmed it on their phone at home. Claude is the director: it writes the plan, checks
claims, reviews every image, and drives a bundled Python engine (`scripts/ugc.py`) that calls AI
models on fal.ai and edits the result with ffmpeg.

```
script ─► voice (ElevenLabs) ─► word timings ─► pauses tightened ─► one audio slice per shot
face+product ─► keyframes (Nano Banana Pro) ─► talking clips (OmniHuman 1.5) / B-roll (Kling 3)
everything ─► jump-cut edit + handheld drift + phone grade/grain + phone-mic audio
          ─► captions + AI label + end card (real product photo) ─► QA ─► final.mp4
```

## Ground rules

These protect the brand and the people in the video. Explain them to the user when they come up;
don't just refuse.

1. **The face must be usable.** It should be an AI-generated character or a real person who has
   given written permission for their likeness in ads. Never a celebrity, influencer, doctor or
   public figure, and never someone photographed without consent. If you're not sure where the
   face came from, ask once.
2. **Keep the "AI-generated" label on.** It's on by default, as a small label at the top. ASCI's
   virtual-influencer guidance and platform AI-content rules expect it. "Realistic" means good
   craft, not tricking viewers. If the user wants it removed, tell them what the rules expect and
   leave the decision to their compliance owner (`disclosure.show: false`).
3. **Claims must be safe.** Ayurvedic products fall under the Drugs & Magic Remedies Act and ASCI
   health-claim rules. Before anything is generated, run `check`, then rewrite every HIGH flag and
   flag each MEDIUM one to the user. The AI character must never describe its own health results
   ("my sugar came down"): that is a fabricated testimonial. It can talk about routine,
   ingredients, taste and ease of use. Details are in `references/compliance-india.md`.
4. **Money moves only after a "go".** Voice and keyframes cost cents; talking clips cost dollars.
   Stop at both checkpoints below and show the cost before each paid stage.
5. **Never ask the user to paste an API key into the chat.** Point them to the setup steps
   (`.env` file, `setkey` in their own terminal, or their environment settings).

## Setup (once per machine / session)

`SKILL_DIR` is the folder that contains this file. Jobs go in a folder the user can open: in
Claude Code use `./ugc_jobs/<slug>` in the current project; in a claude.ai chat use
`/mnt/user-data/outputs/ugc/<slug>`.

```bash
pip install -r "$SKILL_DIR/requirements.txt"     # add --break-system-packages if pip refuses
python3 "$SKILL_DIR/scripts/ugc.py" doctor        # checks Python libs, ffmpeg+libass, fonts, key, network
```

- **No fal.ai key.** Tell the user to create one at fal.ai (Dashboard → Keys) and add credit
  (US$10-20 covers a few videos). Then they store it themselves in one of three ways:
  a `.env` file containing `FAL_KEY=...` in the folder Claude runs in; running
  `python3 scripts/ugc.py setkey` in their own terminal; or, in a cloud session, an environment
  variable `FAL_KEY` in the environment settings.
- **Network blocked** (doctor shows "cannot reach fal.ai"). The sandbox needs to allow
  `queue.fal.run`, `rest.fal.ai`, `*.fal.media` and `storage.googleapis.com`, plus
  `api.elevenlabs.io` for the direct voice option. Tell the user exactly that. Where to change it
  is in `references/troubleshooting.md`.
- **ffmpeg missing.** See `references/troubleshooting.md`.
- **Try it for free.** `python3 "$SKILL_DIR/scripts/ugc.py" demo --out <folder>` runs the whole
  pipeline with offline stand-ins (`--mock`). It proves the installation works before any money is
  spent.

## Workflow

Run commands as `python3 "$SKILL_DIR/scripts/ugc.py" <command> --job <job folder>`. Every paid
result is cached in the job's `state.json`. Re-running a command never pays twice for the same
input, and an interrupted request is collected on the next run.

### 1. Intake

You need three inputs: the face image, the product image and the script. Ask in one message for
anything missing, plus whatever you can't infer:

- language: English, or Hindi/Hinglish
- the product's exact name
- target length (default: whatever the script naturally needs, within 20-60 s)
- the person's gender or voice preference
- any setting preference (default: a sunlit Indian apartment)

Confirm face consent here if it is unclear.

Then look at both images yourself:

- **Face.** Write `character.description`: apparent age, hair, skin tone, notable features and
  clothing. It reinforces identity in every prompt. If the photo is low-res, side-on or covered by
  sunglasses, hands or a mask, ask for a clear front-facing one, because lip-sync quality depends
  on it.
- **Product.** Check that the label is readable. Note whether the background is plain white or
  transparent (the end card can cut it out) or busy (the end card shows it as a card). If the user
  has a transparent PNG packshot, ask for it.

### 2. Script pass

Run `init` with `--face`, `--product`, `--script` (or `--text`), `--lang`, `--title` and
`--product-name`. Then run `check --job <job>`.

Rewrite the script for spoken UGC using `references/script-and-voice.md`:

- a hook in the first 2 seconds
- short spoken sentences
- one idea per segment
- a soft CTA

Fix every HIGH claim and keep the user's meaning. Length is about 2.5 words per second, so 20 s is
about 50 words and 60 s about 150. For Hindi, write `say` in Devanagari (English brand words can
stay in Latin script), because TTS pronounces it far better. Put a Roman-script `caption` alongside
if the user wants Hinglish captions.

### 3. Plan

Edit `plan.yaml`. The field reference is `references/plan-reference.md`; a full worked example is
`templates/plan.example.yaml`. What makes it feel real (details in `references/realism-playbook.md`):

- **2-3 setups in one home** (e.g. sofa medium, sofa close, kitchen product). It should look like
  one person filming a few takes, not a production.
- **Talk segments of 2-8 s.** Consecutive segments with the same setup get automatic jump-cut
  punch-ins.
- **One B-roll every 2-3 talk segments**: hands pouring, product on the counter, morning walk.
  B-roll hides cuts and shows the product properly. Use `with_person: false` for product close-ups
  so faces aren't generated twice.
- **The product is held in at most one setup** (`framing: product`). Products can warp while
  people gesture, so let B-roll and the end card carry the product.
- **Give each segment a short `performance` cue** that matches the line's emotion.
- **End card last.** The real product photo and real logo are composited there, so the label is
  always correct.
- **Voice.** Choose it with `references/script-and-voice.md`. fal's preset voices are mostly
  American or British. For an Indian accent, use `provider: elevenlabs` with an Indian voice from
  the ElevenLabs Voice Library, or `provider: file` with a real recording (the most realistic
  option of all).

Then run `validate` (fix all errors) and `estimate`.

**CHECKPOINT 1.** Send one message containing:

- the segment table (id, shot, setup, line)
- the claims that were flagged and what you changed
- the voice choice
- the setups in one line each
- the estimated length and cost

Ask "go?" and do not continue until the user says yes.

### 4. Voice and keyframes (cheap)

Run `voice`. Read the length table. If a "transcript matches only N%" warning appears, the TTS
mispronounced or skipped words: rewrite that line (spell out numbers, use Devanagari) and run
`voice --only <id> --force`. If the total is outside 20-60 s, trim the script or adjust
`voice.speed` (0.9-1.15).

Run `frames`, then open `work/frames/contact.jpg` and the full-size candidates in
`work/frames/<key>/`. Review each one against the keyframe checklist in
`references/realism-playbook.md`: identity matches the face photo, natural skin, correct hands, the
product label matches the product photo, a real home, phone-camera light. Set `pick:` to the best
candidate. If none passes, sharpen the scene or description and run
`frames --only <setup> --force`. Do at most 2 rounds per setup, then show the user what's wrong.

**CHECKPOINT 2.** Send `work/voice/vo_preview.mp3` and the contact sheet, say which candidates you
picked and why, and give the cost of the talking clips (the expensive part). Wait for OK.
Changing the voice later means re-making the talking clips.

### 5. Clips

Run `clips`. Talking clips take about 1-5 minutes each and run 3 at a time. If one fails, the
others are kept, so re-run `clips` to retry only the failures. Make sure no warning says a clip is
shorter than its audio.

### 6. Assemble and QA

Run `assemble`, then `qa`. Open `out/<slug>_contact.jpg` and check:

- no face drift between cuts
- no warped hands or product
- captions don't cover the mouth or the product label
- the end card text is readable

If one clip is bad, run `clips --only <id> --force`, then `assemble` again. Fix every FAIL that
QA reports; look into every CHECK.

### 7. Deliver

Send `out/<slug>.mp4` (and the contact sheet if useful). In 3-5 lines, give:

- length and estimated spend (`state.json` keeps the running total)
- any claim the user still needs their compliance owner to approve
- that the AI label is on
- the one or two tweaks most likely to improve the next video

To also produce a caption-free copy for editors, set `captions.clean_copy: true`.

## Quick fixes

| Symptom | Fix |
|---|---|
| Face doesn't look like the photo | richer `character.description`, `candidates: 3`, a clearer front-facing source photo |
| Plastic or beauty-filter skin | regenerate; avoid "beautiful/flawless" in scenes; keep `grain` ≥ 0.4 |
| Garbled product label | regenerate that keyframe, or drop the product from talk setups (end card + B-roll carry it) |
| Lips drift or mouth smears | shorter segment (≤ 6 s), front-facing keyframe with mouth visible, try the Kling Avatar model in `config/models.yaml` |
| Robotic voice | lower `stability` (0.35-0.45), commas for breaths, a real recording, or the eleven-v3 model |
| Too slow / too long | `finish.tighten_pauses: 0.22`, `voice.speed: 1.08`, cut words |
| B-roll looks fake | simpler motion (one action), `with_person: false`, or `motion: kenburns` on a good still |

More in `references/troubleshooting.md`.

## Reference files (read when needed)

- `references/realism-playbook.md`: what makes AI UGC read as real; keyframe and final-video review checklists. Read before planning setups and when reviewing images.
- `references/script-and-voice.md`: UGC script structure for a 45+ Indian audience, writing for TTS (Hindi/Hinglish), choosing and tuning voices, example scripts.
- `references/compliance-india.md`: likeness consent, AI disclosure, DMR Act / ASCI claim rules, a safe-wording table. Read when `check` flags anything.
- `references/plan-reference.md`: every `plan.yaml` field.
- `references/models-and-costs.md`: which model does what, prices, how to swap in newer models.
- `references/troubleshooting.md`: install, keys, network allowlists, API errors, fixes.
