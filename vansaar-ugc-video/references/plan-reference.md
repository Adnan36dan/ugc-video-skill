# plan.yaml field reference

Paths are relative to the job folder. Anything left out uses the default shown. Brand-level
defaults (captions, end card, disclosure) come from `config/brand.yaml`; any of them can be
overridden per video under the same key in plan.yaml.

## Top level
| Field | Default | Notes |
|---|---|---|
| `title` | "Vansaar UGC" | also names the output file |
| `product_name` | "" | used in prompts ("the product (Vansaar Liquid Collagen)") |
| `language` | en | `en` or `hi` (Hinglish = hi). Sets transcription language and caption font |
| `inputs.face` | - | character photo: front-facing, sharp, even light, mouth visible |
| `inputs.product` | - | product photo; a transparent PNG gives the best end card |

## character
| Field | Default | Notes |
|---|---|---|
| `pronoun` | she | she / he / they (used in prompts) |
| `description` | "" | age, hair, skin, clothes, accessories; repeated in every prompt for identity and wardrobe continuity |

## voice
| Field | Default | Notes |
|---|---|---|
| `provider` | fal | `fal` (ElevenLabs via fal), `elevenlabs` (direct, needs ELEVENLABS_API_KEY), `file` |
| `voice` | "" | fal: preset name (or a voice ID); elevenlabs: voice ID |
| `model` | null | override the TTS endpoint (fal) or model_id (elevenlabs) |
| `speed` | 1.0 | 0.7-1.2 |
| `stability` | 0.45 | 0-1, lower is livelier |
| `similarity_boost` | 0.8 | 0-1 |
| `style` | 0.15 | 0-1 |
| `language_code` | null | force a language (ISO 639-1); leave empty normally |
| `file` | null | recording for `provider: file` (any audio format) |

## setups (map of name → setup)
A setup is one "camera position" for talking shots. Each one gets its own keyframe image.

| Field | Default | Notes |
|---|---|---|
| `scene` | - | **required.** Where they are, 2-3 concrete objects, window direction |
| `framing` | medium | `close` (head and shoulders), `medium` (chest up), `product` (holds product by face) |
| `with_product` | false | put the product in a close/medium frame too |
| `candidates` | 2 | images generated (1-4); you pick one |
| `pick` | 1 | which candidate to animate (v1, v2…) |

## segments (list, in order)
| Field | Default | Notes |
|---|---|---|
| `id` | s01, s02… | unique; used in file names and `--only` |
| `shot` | talk | `talk`, `broll` or `endcard` |
| `setup` | - | talk only: name of a setup |
| `say` | "" | the spoken words (TTS input). Hindi in Devanagari |
| `caption` | null | on-screen text if different from `say` (e.g. Roman Hinglish) |
| `performance` | "" | talk only: short acting cue for the lip-sync model |
| `zoom` | auto | talk/broll: force a zoom (1.0-1.2); auto gives jump-cut punch-ins |
| `hold` | null | seconds for a segment with no `say` (silent B-roll or end card) |
| `broll.scene` | "" | what the cut-away still shows (generated) |
| `broll.with_person` | false | include the character (uses the face reference) |
| `broll.with_product` | true | include the product (uses the product reference) |
| `broll.motion` | "" | what moves in the clip (image-to-video); `kenburns` = slow zoom on the still, free |
| `broll.image` | null | use your own photo as the still instead of generating |
| `broll.video` | null | use your own real footage (best realism; any aspect, cropped to 9:16) |
| `broll.candidates` / `pick` | 1 / 1 | as for setups |

## captions
| Field | Default | Notes |
|---|---|---|
| `enabled` | true | |
| `words_per_card` | 3 | 2-4 |
| `max_chars` | 22 | per card |
| `position` | 0.70 | vertical centre, 0 = top, 1 = bottom |
| `size` | 76 | px at 1080 wide |
| `highlight_color` / `text_color` / `outline_color` | brand | hex |
| `clean_copy` | false | also export a version without captions |

## finish
| Field | Default | Notes |
|---|---|---|
| `tighten_pauses` | 0.30 | max pause in seconds; null = keep natural pauses |
| `punch_in` | true | jump-cut zoom between same-setup talk segments |
| `handheld` | 0.5 | 0-1 camera drift |
| `grain` | 0.45 | 0-1 film or sensor grain |
| `phone_audio` | true | phone-mic EQ, small-room reflections, room tone |

## endcard / disclosure / music
| Field | Default | Notes |
|---|---|---|
| `endcard.cta` | "Shop at vansaar.com" | big line |
| `endcard.accent` | "Rooted in Ayurveda" | serif italic line above it |
| `endcard.theme` | dark | `dark` (forest + gold logo) or `light` (ivory + deep-gold logo) |
| `endcard.hold` | 2.5 | seconds when the end card has no `say` |
| `endcard.hold_after_voice` | 0.8 | seconds after the last word |
| `disclosure.show` / `label` | true / "AI-generated" | small top-left label for the whole video |
| `music.file` / `volume_db` | null / -22 | optional licensed track, ducked under the voice |
| `brand.*` | - | override anything from config/brand.yaml for this video only |
