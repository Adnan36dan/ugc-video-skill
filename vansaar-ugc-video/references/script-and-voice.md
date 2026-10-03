# Scripts and voice

## Contents
1. UGC structure that works for a 45+ Indian audience
2. Length math
3. Writing for text-to-speech (English, Hinglish, Hindi)
4. Choosing a voice
5. Voice settings
6. Example scripts (pass the claims check)

## 1. Structure

A 20-60 s UGC video is a conversation, not an ad. The shape that works:

| Beat | Seconds | Job | Example |
|---|---|---|---|
| Hook | 0-3 | stop the scroll; speak to *them* | "If you're past fifty, you'll get this." |
| Relatable moment | 3-10 | everyday life, no disease | "Mornings used to start slow for me." |
| Discovery / routine | 10-25 | what they do, when, how | "Now I start with a small glass of this." |
| Why they like it | 25-40 | ingredients, taste, ease, ritual | "Sea buckthorn and amla, and it's easy to keep up." |
| Responsible line | optional | builds trust | "Ask your doctor before starting any supplement." |
| Soft CTA | last 3-5 | where to find it | "Link's below, vansaar dot com." |

Formats that suit the brand (from safest):
- **My routine after 50** (morning ritual, before a walk, after yoga)
- **What's inside**, an ingredient spotlight in plain words, using only what's on the label
- **My son / daughter ordered this for me**, a family angle that is very relatable in India
- **First impressions / unboxing**: taste, texture, packaging, how to take it
- **Things I started doing after 45**, a list where the product is one item among walks, sleep
  and water

Tone for 45+: warm, respectful ("aap"), unhurried, a little humour about age, no Gen-Z slang
overload, no hard selling. Talk about energy for the day, routine, family, staying active and
taste. Do not talk about diseases or results (see compliance-india.md).

## 2. Length math

About 2.5 spoken words per second in English and about 2.7 in Hindi (shorter words), at
`speed: 1.0`.

| Target | English words | Hindi/Hinglish words |
|---|---|---|
| 20 s | 45-50 | 50-55 |
| 30 s | 70-75 | 75-80 |
| 45 s | 105-110 | 115-120 |
| 60 s | 140-145 | 150-160 |

The end card adds about 0.8 s after its line. The real length is printed after the `voice` step.

## 3. Writing for TTS

- **Hindi words in Devanagari, English words in Latin script.** For example:
  "मैं रोज़ सुबह अपनी routine में Vansaar लेती हूँ।" Roman-script Hindi ("main roz subah") is read
  with an English accent and sounds wrong. Show Roman captions with `caption:`.
- **Brand name.** If "Vansaar" comes out as "van-sar", write वनसार in `say` (the caption can
  still say Vansaar).
- **Numbers and URLs.** Write "fifty" / "पचास", "vansaar dot com". Avoid digits and symbols (%,
  ₹, &) in `say`.
- **Pauses.** A comma is a short breath, a full stop or । a longer one, and "—" a thinking pause.
  The engine trims pauses over 0.3 s anyway.
- **Natural fillers, sparingly:** "honestly", "you know", "dekho", "sach bataun", "na?". One or
  two per video.
- **One sentence per segment** where possible; it makes clean cut points.
- **eleven-v3 only:** audio tags like `[laughs]`, `[sighs]` and `[whispers]` are supported. Use
  at most one or two (switch model in `config/models.yaml`).

## 4. Choosing a voice

Options, from most to least real:

1. **A real recording** (`voice.provider: file`, `voice.file: inputs/recording.m4a`). Someone
   45+ reads the script into a phone in a quiet, soft-furnished room, about 20-30 cm from the
   mouth. Any format works. The engine finds the words, cuts the pauses and slices it per segment.
   The words must follow the script order; small ad-libs are fine.
2. **An ElevenLabs Voice Library voice with an Indian accent** (`voice.provider: elevenlabs`).
   1. In ElevenLabs, open Voices → Voice Library and filter by Language Hindi or accent Indian,
      age middle-aged or old, use case conversational or social media.
   2. Add the voice to "My Voices" and copy its Voice ID into `voice.voice`.
   3. Store the API key as `ELEVENLABS_API_KEY` in `.env` (or run `ugc.py setkey --elevenlabs`).
   ElevenLabs bills this directly. Check that your plan includes a commercial licence.
3. **ElevenLabs through fal** (`voice.provider: fal`, the default; one key, simplest). The preset
   names (Aria, Sarah, Laura, Alice, Matilda, Jessica, Lily, Roger, George, Charlie, Callum,
   Liam, Will, Eric, Chris, Brian, Daniel, Bill, River, Charlotte) are mostly American or British.
   They are fine for English scripts aimed at urban audiences, but weaker for Hindi. A Voice
   Library ID may also work here; if fal rejects it, use option 2.

Match the voice to the face: age, gender and energy. A 55-year-old face with a 25-year-old
voice is the fastest way to look fake.

## 5. Voice settings

| Setting | Range | Effect |
|---|---|---|
| `stability` | 0.35-0.5 | lower = more expressive and human; below 0.3 can wobble |
| `similarity_boost` | 0.75-0.85 | how closely it sticks to the voice |
| `style` | 0-0.3 | more character; too high sounds performed |
| `speed` | 0.95-1.1 | UGC is slightly brisk; 45+ audiences like clarity, so don't exceed 1.1 |

Each segment is generated separately with its neighbours as context, so one line can be
regenerated (`voice --only s03 --force`) without touching the others.

## 6. Example scripts (they pass `check` with no HIGH flags)

**English, about 30 s, routine format (Liquid Collagen)**
1. (close) "If you're past fifty, you'll understand this one."
2. (medium) "My mornings used to start slow. Now I start with a small glass of this."
3. (B-roll: pouring) "It's Vansaar Liquid Collagen, made with sea buckthorn and amla."
4. (product) "Honestly, the taste is nice, and it's easy to keep up every day."
5. (medium) "Just one thing: talk to your doctor before starting any supplement."
6. (end card) "The link is below. Vansaar dot com."

**Hinglish, about 30 s, family format (Sea Buckthorn Juice)**
1. (close) say: "मेरे बेटे ने ये मेरे लिए order किया था… और सच बताऊँ, अब ये मेरी routine है।"
   caption: "Mere bete ne ye mere liye order kiya tha… aur sach bataun, ab ye meri routine hai."
2. (medium) say: "सुबह walk से पहले एक छोटा सा glass।" caption: "Subah walk se pehle ek chhota sa glass."
3. (B-roll: bottle on counter, steel glass) say: "इसमें sea buckthorn berry का pulp है, और taste भी अच्छा है।"
   caption: "Isme sea buckthorn berry ka pulp hai, aur taste bhi achha hai."
4. (product) say: "बस, डॉक्टर से पूछ कर ही कोई भी supplement शुरू करिए।"
   caption: "Bas, doctor se pooch kar hi koi bhi supplement shuru kariye."
5. (end card) say: "Link नीचे है — वनसार dot com।" caption: "Link neeche hai — vansaar.com"

Every ingredient or benefit line must match the product's actual label. When in doubt, describe
the ritual, not the result.
