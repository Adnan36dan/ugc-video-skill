# Vansaar UGC Video Skill

A Claude **skill** that turns three things into a realistic 20-60 second vertical video (Reels,
Shorts, Meta ads) for **Vansaar 45+**:

1. a **face photo** of your character
2. a **product photo**
3. a **script**

The result looks like a 45+ Indian customer talking to their phone at home. They hold the
product, and the video has cut-away shots, word-by-word captions (English, Hinglish or Hindi), a
small "AI-generated" label and a branded Vansaar end card.

```
script ──► natural voice ──► clean cuts ─┐
face + product ──► realistic phone-video stills ──► talking clips + product B-roll ─┐
                                           └──► edited like a real creator: jump cuts, handheld feel,
                                                phone audio, captions, end card ──► final.mp4 (1080×1920)
```

---

## New to all this? Start here

**What is a "skill"?** A folder of instructions and tools that teaches Claude a new job. This one
is `vansaar-ugc-video/`. Once it's installed, you just ask Claude in plain words, for example
*"Make a 30-second Hinglish UGC video for Vansaar Liquid Collagen with this face, product photo
and script"*, and Claude follows the skill step by step. It stops twice to show you the plan and
the cost before spending money.

**Can Claude make video by itself?** No. Claude is the director and editor. The faces, voices and
motion come from specialist AI models (ElevenLabs, Nano Banana Pro, OmniHuman, Kling), which the
skill calls through one service, **fal.ai**. You need a fal.ai account with some credit.

### What you need

| | Why | Cost |
|---|---|---|
| **Claude Code** (desktop app or terminal; recommended), or claude.ai with Skills and code execution | runs the skill | your Claude plan |
| **fal.ai account + API key** | the AI models | about **$5-8 per 30 s video**, $10-14 per 60 s (pay as you go) |
| ElevenLabs account (optional) | Indian-accent voices from their Voice Library | their plan |
| Python 3.9+ and ffmpeg | editing; Claude can install these for you | free |

### Step 1: Install the skill

- **Claude Code:** copy the `vansaar-ugc-video` folder into `~/.claude/skills/` (for you,
  everywhere) or into `.claude/skills/` inside a project folder.
- **claude.ai:** zip the `vansaar-ugc-video` folder (or use the packaged `.skill` file) and upload
  it in **Settings → Capabilities → Skills**. Code execution must be on, and the sandbox must be
  allowed to reach fal.ai (see Troubleshooting).

### Step 2: Free test run (no key, no cost)

Ask Claude: *"Run the vansaar-ugc-video demo so I can check everything is installed."*

Claude runs `python3 scripts/ugc.py demo --out demo_test`. It builds a complete test video from
placeholder pictures and beeps, so you can see the whole pipeline work.

### Step 3: Add your fal.ai key (keep it secret)

1. Sign up at **fal.ai**, open **Dashboard → Keys**, create a key, and add $10-20 credit.
2. In the folder where you run Claude, create a plain text file named `.env` containing one line:
   ```
   FAL_KEY=paste-your-key-here
   ```
   (Or run `python3 vansaar-ugc-video/scripts/ugc.py setkey` in your own terminal and paste it
   there.)
3. **Don't paste keys into the chat**, and never commit `.env` to GitHub (this repo's
   `.gitignore` already excludes it).

### Step 4: Make your first video

Put your files in a folder (e.g. `face.jpg`, `product.png`, `script.txt`), then ask Claude:

> Make a 30-second Hinglish UGC video for Vansaar Liquid Collagen using face.jpg, product.png and
> script.txt. The character is a 52-year-old woman from Delhi.

Claude will:
1. **Check the script** for risky health claims and rewrite it in natural spoken style.
2. **Plan** the shots (2-3 camera positions in one home, B-roll, end card) and show you the
   **script, plan and cost**. *You say "go".*
3. Make the **voice** and **still images** (cheap). It shows you the voice preview and the
   images. *You say OK.*
4. Make the **talking clips and B-roll** (the main cost), edit everything together and check the
   result.
5. Send you the final **MP4** and a contact sheet.

It takes about 10-25 minutes per video, mostly waiting for the AI models.

---

## Getting the most realistic results

- **Face photo:** front-facing, sharp, natural light, neutral expression, mouth visible, no
  sunglasses, at least 1000 px. Use an AI-generated character, or a real person who has signed
  permission for AI ads.
- **Product photo:** sharp, label readable, ideally a transparent PNG or a plain white background.
- **Voice:** the most real option is a real person (45+) reading the script into a phone in a
  quiet room. Give Claude the recording and it does the rest. Next best is an Indian voice from
  the ElevenLabs Voice Library.
- **Script:** short, spoken sentences; a hook in the first 2 seconds; talk about routine, taste
  and ingredients, not cures. Hindi lines work best written in Devanagari (captions can still be
  Roman Hinglish).
- **Own footage:** a real 5-second phone clip of the product being poured or opened makes the
  B-roll 100% real.

## Safety and compliance (important for an Ayurvedic brand)

- Every script is checked against Indian ad rules (Drugs & Magic Remedies Act, ASCI). Cure,
  guarantee, disease, sexual-performance and "stop your medicine" wording is flagged and
  rewritten.
- The AI character never claims personal health results ("my sugar came down"). That would be a
  fake testimonial.
- A small **"AI-generated"** label stays on the video by default, and the end card carries the
  disclaimer *"This product is not intended to diagnose, treat, cure or prevent any disease."*
- This is a safety net, not legal advice. Your compliance owner approves final claims.

## What's in this repository

```
vansaar-ugc-video/            ← the skill (install this folder)
  SKILL.md                    instructions Claude follows
  scripts/ugc.py              the engine's command line
  scripts/ugclib/             voice, keyframes, clips, captions, end card, assembly, QA, claims check
  config/models.yaml          which AI models are used + prices (easy to swap for newer ones)
  config/brand.yaml           Vansaar colours, fonts, logo, disclaimer, AI label
  references/                 realism playbook, script & voice guide, compliance, costs, troubleshooting
  templates/plan.example.yaml a complete worked example
  assets/                     brand fonts (OFL) and the official Vansaar 45+ logo
tests/fake_fal_test.py        tests the real code paths against a fake fal.ai (no cost)
```

## Troubleshooting

See `vansaar-ugc-video/references/troubleshooting.md`, or just ask Claude:
*"Run the ugc doctor and tell me what's missing."*
