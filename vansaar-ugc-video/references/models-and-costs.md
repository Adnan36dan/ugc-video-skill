# Models and costs

All models run on **fal.ai** with one key (`FAL_KEY`), billed per use. Prices were checked on
fal.ai in October 2026 and live in `config/models.yaml` (only used for estimates).

| Role | Default model (fal endpoint) | Why | Price |
|---|---|---|---|
| Voice | ElevenLabs Multilingual v2 (`fal-ai/elevenlabs/tts/multilingual-v2`) | natural, Hindi + English, speed/style controls, neighbour-sentence context | $0.10 / 1,000 chars |
| Word timings | ElevenLabs Scribe (`fal-ai/elevenlabs/speech-to-text`) | word-level timestamps in 99 languages | $0.03 / min |
| Keyframes | Nano Banana Pro edit (`fal-ai/nano-banana-pro/edit`) | strongest at keeping a face's identity and a product's label text from reference photos | $0.15 / image |
| Talking clips | OmniHuman v1.5 (`fal-ai/bytedance/omnihuman/v1.5`) | photo + audio → lip-synced person with natural head, hands and expressions; up to 30 s at 1080p | $0.16 / s |
| B-roll | Kling v3 Pro image-to-video (`fal-ai/kling-video/v3/pro/image-to-video`) | realistic motion, 3-15 s, native 9:16 from the still | $0.112 / s (audio off) |

## Typical cost per finished video (one clean pass)

| Length | Talking | B-roll | Keyframes (~7) | Voice + timings | Total | With re-dos |
|---|---|---|---|---|---|---|
| 20 s | ~$2.60 | ~$0.60 | ~$1.05 | ~$0.05 | ~$4.30 | ~$6 |
| 30 s | ~$3.80 | ~$0.70 | ~$1.05 | ~$0.06 | ~$5.60 | ~$8 |
| 60 s | ~$7.70 | ~$1.30 | ~$1.20 | ~$0.10 | ~$10.30 | ~$14 |

`ugc.py estimate --job …` gives the figure for a specific plan, and `state.json` keeps a running
total of estimated spend. fal's dashboard shows the real bill.

Ways to spend less:
- `candidates: 1` once a setup works
- `motion: kenburns` B-roll (free)
- your own B-roll footage (`broll.video`)
- shorter scripts
- iterating on voice and keyframes (cents) before clips (dollars)

## Swapping in a newer or different model

AI video models improve every few months. To try one:

1. Find it on fal.ai, open its **API** tab and look at the **Schema → Input** names.
2. Copy `config/models.yaml` to `<job>/models.yaml` (affects that job only) or edit the original.
3. Change `endpoint`, then map the inputs in `arg_names`. For example, if the new avatar model
   calls the photo `face_image_url`, write `arg_names: {image: face_image_url, audio: audio_url}`.
   Put fixed settings in `defaults` and update the price.
4. Run one short segment first, e.g. `clips --only s01 --force`.

Ready-to-use alternatives (commented in models.yaml):
- **Talking:** Kling AI Avatar v2 Pro (`fal-ai/kling-video/ai-avatar/v2/pro`, $0.115/s). Others
  worth testing: VEED Fabric 1.0, Creatify Aurora, HeyGen Avatar, MiniMax lip-sync, and for
  re-syncing existing footage, Sync Lipsync v3.
- **B-roll:** Veo 3.1 Fast image-to-video (`fal-ai/veo3.1/fast/image-to-video`). Also Seedance 2.x
  and Kling 2.5 Turbo (cheaper, $0.07/s).
- **Keyframes:** Nano Banana 2 edit (`fal-ai/nano-banana-2/edit`, $0.08/image), slightly weaker on
  label text.
- **Voice:** eleven-v3 (`fal-ai/elevenlabs/tts/eleven-v3`): more expressive, supports [laughs]
  tags, but no speed/style/context. Set `params: [text, voice, stability, language_code,
  apply_text_normalization]`.
