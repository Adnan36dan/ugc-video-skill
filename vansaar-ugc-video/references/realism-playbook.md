# Realism playbook: what makes AI UGC read as "real"

Viewers decide in about one second whether something is an ad or a person. What they read is lots
of small cues. Each item below either adds a cue of reality or removes an AI tell. The engine
already handles the editing and audio cues; this file is mostly for the parts Claude controls: the
plan, the prompts and the review.

## Contents
1. The real-person look (setups and keyframes)
2. Performance
3. Voice and audio
4. Editing
5. Captions and graphics
6. Keyframe review checklist
7. Final-video review checklist
8. AI tells and their fixes

## 1. The real-person look

**Location.** An ordinary, lived-in Indian home: a 2BHK living room, bedroom corner, kitchen
counter, balcony with plants, or dining table. Name 2-3 concrete objects per scene: a steel
tumbler, a money plant, a framed family photo, a cushion with a slight crease, a wall calendar, a
pressure cooker on the stove, a jute rug. Concrete beats generic ("cozy room" is generic).

**One home, several angles.** A real creator films in one place. Give every setup the same
apartment and change only the spot or the closeness: "same sofa, closer to the window". Changing
city or house between cuts reads fake.

**Light.** Window daylight (morning or late afternoon), from one side, with soft shadows. Avoid
studio, ring light, neon or "golden hour cinematic". Say *where* the window is.

**Camera.** A front phone camera held at arm's length, slightly above eye level, with a mild
wide-angle look. Framing is imperfect: the head a little high or off-centre is fine. Avoid
portrait-mode bokeh; real phone backgrounds are fairly sharp.

**People 45+.** Real age texture: fine lines, pores, some grey, slight under-eye shadows,
age-appropriate clothes (cotton kurta, salwar, polo shirt, simple saree, reading glasses on a cord,
a steel watch). Never ask for "beautiful", "flawless", "glowing" or "young-looking". Those words
produce the AI beauty-filter face.

**Wardrobe continuity.** Put clothes and hair in `character.description` so every setup matches.
Changing clothes between cuts is the most common accidental tell.

**The product in hand.** Show it in at most one setup, held at chest height beside the face,
label to the camera, fingers off the logo. Everywhere else it appears on a table in B-roll, and
pixel-perfect on the end card.

## 2. Performance

The `performance` cue goes to the lip-sync model. Short and human beats long and theatrical.

Good cues:
- "leans in slightly with a knowing smile, eyebrows up on the hook"
- "relaxed, matter-of-fact, small open-hand gesture"
- "sincere, slower, slight nod"
- "laughs softly at herself, shakes head"

Avoid: big arm movements, pointing at the camera, "excited", "energetic", "presenter". Those
produce infomercial energy and more hand artifacts.

## 3. Voice and audio

- **Voice is half of the realism.** A slightly imperfect, warm, conversational voice beats a
  polished narrator. The best option is `voice.provider: file`, a real person reading the script
  on a phone in a quiet room. Next best is an Indian voice from the ElevenLabs Voice Library with
  `stability` 0.35-0.45.
- **Write for speech:** contractions, "honestly", "dekho", "na?", short sentences, a comma where a
  breath belongs. See `script-and-voice.md`.
- **What the engine does automatically (`finish.phone_audio`):** a gentle phone-mic EQ, very short
  small-room reflections, and a faint room tone under everything. Studio-clean TTS is a tell; this
  removes it.
- **Music:** none, or very low (-22 dB, ducked under the voice). Real UGC rarely has a soundtrack.
  Use only tracks the brand is licensed to use.

## 4. Editing (automatic, tune in `finish`)

- **Tightened pauses** (`tighten_pauses: 0.30`): gaps longer than 0.3 s are cut, like a creator
  trimming dead air. Use 0.22 for punchier, 0.4 for calmer.
- **Jump-cut punch-ins** (`punch_in: true`): consecutive segments from the same setup alternate
  1.0 and 1.12 zoom (1.07 for close framing).
- **Handheld drift** (`handheld: 0.5`): slow multi-frequency sway of a few pixels. Use 0 for a
  tripod look, 0.8 for walking.
- **Phone grade and grain** (`grain: 0.45`): slight contrast and saturation lift, mild sharpening,
  and fine temporal luma grain. It hides AI smoothness and makes AI clips match each other.
- **Cuts at sentence boundaries:** each segment is a slice of speech that starts and ends in a
  natural micro-pause.

## 5. Captions and graphics

- Word-by-word captions with the current word in saffron, 2-3 words per card, placed at 70 %
  height: below the face, above the Reels UI. Edit `captions.position` if they cover the product.
- Keep captions in the language people will read. Hinglish audiences often prefer Roman script:
  use `caption:` per segment.
- The "AI-generated" label is small at top-left for the whole video.
- No stickers, emojis or animated arrows. They are fine for brand ads but fight the "real
  person" read.

## 6. Keyframe review checklist (`work/frames/contact.jpg` + full-size files)

Open the face photo and the product photo next to the candidates. A keyframe passes only if all
of these are true:

1. **Same person.** Face shape, eyes, nose, lips, hairline, skin tone and age all match the
   source. If a friend would say "that's a different auntie", reject it.
2. **Real skin.** Pores, lines and unevenness are present; no waxy or airbrushed look; age is not
   reduced.
3. **Hands.** Five fingers each, a natural grip, no fused or extra fingers. If hands are bad and
   not needed, pick a framing that hides them.
4. **Product.** Shape, colours, cap and logo match the product photo, and the label text is the
   real text, not gibberish. If it's close but not exact, it's only acceptable when the label is
   small or turned slightly; otherwise regenerate.
5. **Lip-sync ready.** Face toward the camera, mouth visible and relaxed, nothing in front of the
   mouth, eyes open.
6. **Real home, phone light.** Lived-in background, window light, no studio look, no visible
   phone, no mirror, no other people, no text or watermark.
7. **Consistency.** Same clothes, hair and accessories as the other setups.

## 7. Final-video review checklist (`out/<slug>_contact.jpg`, then watch it)

- Every cut: same face and clothes; no flash of a different person.
- The first 2 seconds: the face appears immediately and the hook line starts within 0.5 s.
- Product shots: the label doesn't morph; hands don't melt.
- Captions: readable, not on the mouth, not on the label, correct spelling.
- End card: real logo, real product, CTA and disclaimer readable on a phone.
- Audio: no clicks at cuts, consistent voice, nothing clipped (QA reports true peak).
- AI label present.

## 8. AI tells and their fixes

| Tell | Fix |
|---|---|
| Beauty-filter skin, too young | remove flattering words; say "real, unretouched skin, age NN"; keep grain |
| Perfect symmetric framing, studio light | "phone held at arm's length", "window light from the left" |
| Busy, perfect show-home background | name 2-3 ordinary objects; "slightly imperfect tidiness" |
| Morphing product or text | product only in one short setup; B-roll with one simple action; rely on the end card |
| Mouth smears on long lines | segments ≤ 6 s; front-facing keyframe; no hand near the mouth |
| Head-bob loop, frozen eyes | add a specific performance cue; regenerate that clip |
| Robotic, even pacing | lower stability; commas; real recording; tighten_pauses 0.25 |
| Silent, airless audio | keep phone_audio on; no music, or very low music |
