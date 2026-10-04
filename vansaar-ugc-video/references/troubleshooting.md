# Troubleshooting

## Installing ffmpeg (with libass, for captions)
- **macOS:** install Homebrew from brew.sh, then `brew install ffmpeg`
- **Windows:** `winget install Gyan.FFmpeg`, then open a new terminal
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

Check it with `python3 scripts/ugc.py doctor`; it should say "ffmpeg has libass".

## Python packages
`pip install -r requirements.txt`. If pip says "externally managed environment", add
`--break-system-packages` or use a virtual environment (`python3 -m venv .venv && source
.venv/bin/activate`).

## API keys (never paste them into the chat)
The engine looks, in order, at:
1. the environment variables `FAL_KEY` / `ELEVENLABS_API_KEY`
2. a `.env` file in the current folder or any parent folder, with lines like `FAL_KEY=...`
3. `~/.config/vansaar-ugc/fal.key`, written by `python3 scripts/ugc.py setkey` run in your own
   terminal

In a Claude Code cloud session, add `FAL_KEY` as an environment variable in the environment's
settings (the environment menu in the session title bar → Edit), then start a new session.
If you put a key in `.env` inside a git repository, make sure `.env` is in `.gitignore`.

## "cannot reach fal.ai" (network blocked)
The sandbox must allow `queue.fal.run`, `rest.fal.ai`, `*.fal.media` and
`storage.googleapis.com`, plus `api.elevenlabs.io` if you use direct ElevenLabs.
- **Claude Code on your own computer:** normally works. Check any VPN or firewall.
- **Claude Code cloud session:** environment settings → Network access → Custom → add the
  domains above (keep the package-manager defaults).
- **claude.ai chat with code execution:** Settings → Capabilities: allow network access for these
  domains (or all domains) if your plan offers it. If it doesn't, run the skill in Claude Code.

## API errors
| Message | Meaning / fix |
|---|---|
| `rejected the request (HTTP 422)` | an input is invalid: wrong input name after a model swap, image too small or wrong aspect, or audio too long. The message names the field |
| `HTTP 401/403` | key wrong, revoked or out of credit: check the fal dashboard |
| `HTTP 429` / timeouts | busy: the engine retries; re-run the same command later (no double billing) |
| image model "returned no image" | the prompt was refused, often because of words implying a real famous person or unsafe content; rephrase the scene |
| "lost contact while waiting" | the request is still recorded; just re-run the same command |

## Output problems
| Problem | Fix |
|---|---|
| Face changes between setups | richer `character.description` (with clothes), same home in every scene, `candidates: 3` |
| Different clothes in B-roll with the person | put the clothes in `character.description`; or `with_person: false` |
| Label gibberish in a talking shot | pick another candidate; or remove the product from that setup |
| Lip-sync slightly late or early | check that `voice.provider: file` recordings have no long silence at the start; otherwise re-run that clip |
| End of a clip freezes | QA flags it; re-run `clips --only <id> --force` |
| Captions wrong at a Hindi word | the transcript differs from the script there; fine-tune `caption:` or split the segment |
| Video longer than 60 s | trim `say` lines, `tighten_pauses: 0.22`, `voice.speed: 1.08`, re-run voice |
| End card shows the product in a box | the photo's background isn't plain white; use a transparent PNG |
| Fonts look wrong | run `doctor`; the assets/fonts folder must be next to scripts/ |

## Start over or redo one thing
- Redo one voice line: `voice --only s03 --force` (its clip is redone automatically on the next `clips`)
- Redo one setup's images: `frames --only sofa_close --force`
- Redo one clip: `clips --only s04 --force`
- Re-edit only (free): `assemble`
- Everything cached lives in `<job>/work` and `<job>/state.json`. Deleting them starts fresh, and
  you pay again.
