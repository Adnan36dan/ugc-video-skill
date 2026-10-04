"""fal.ai access: API key handling, uploads, queued requests that survive crashes, downloads.

Every paid request is recorded in the job's state.json *before* we wait for it. If the run is
interrupted, the next run collects the already-paid result instead of paying again.
"""
import base64
import os
import time
from pathlib import Path

import requests

from .util import UGCError, file_hash, log, obj_hash

KEY_FILE = Path.home() / ".config" / "vansaar-ugc" / "fal.key"
ELEVEN_KEY_FILE = Path.home() / ".config" / "vansaar-ugc" / "elevenlabs.key"
UPLOAD_TTL = 12 * 3600  # re-use an uploaded file URL for 12 hours


def _key_from_dotenv(name):
    for d in [Path.cwd(), *Path.cwd().parents]:
        env = d / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get_key(env_name, key_file):
    key = os.environ.get(env_name) or _key_from_dotenv(env_name)
    if not key and key_file.exists():
        key = key_file.read_text().strip()
    return key or None


def save_key(key, key_file):
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key.strip() + "\n")
    os.chmod(key_file, 0o600)
    return key_file


def fal_key():
    return get_key("FAL_KEY", KEY_FILE)


def elevenlabs_key():
    return get_key("ELEVENLABS_API_KEY", ELEVEN_KEY_FILE)


class Fal:
    def __init__(self, state):
        key = fal_key()
        if not key:
            raise UGCError(
                "No fal.ai API key found. Create one at https://fal.ai/dashboard/keys, then run:\n"
                "  python3 scripts/ugc.py setkey      (paste the key, press Enter)\n"
                "or set the FAL_KEY environment variable.")
        os.environ["FAL_KEY"] = key
        try:
            import fal_client  # noqa: WPS433 (imported lazily so --mock works without it)
        except ImportError as e:
            raise UGCError("Python package 'fal-client' is missing. Run: pip install -r requirements.txt") from e
        self.fc = fal_client
        self.state = state

    def upload(self, path):
        """Upload a local file to fal storage (cached by content hash)."""
        h = file_hash(path)
        cached = self.state.get("uploads", h)
        if cached and time.time() - cached["t"] < UPLOAD_TTL:
            return cached["url"]
        for attempt in range(3):
            try:
                url = self.fc.upload_file(Path(path))
                self.state.put("uploads", h, {"url": url, "t": time.time(), "name": Path(path).name})
                return url
            except Exception as e:  # network hiccup
                if attempt == 2:
                    raise UGCError(f"upload of {Path(path).name} failed: {e}") from e
                time.sleep(3 * (attempt + 1))

    def run(self, endpoint, args, key, label=""):
        """Submit (or resume) a queued request and wait for its result."""
        ahash = obj_hash({"endpoint": endpoint, "args": args})
        pending = self.state.get("requests", key)
        if pending and pending.get("hash") == ahash:
            log(f"  [{label}] resuming earlier request {pending['request_id'][:8]}…")
            try:
                res = self.fc.result(endpoint, pending["request_id"])
                self.state.put("requests", key, None)
                return res
            except Exception as e:
                log(f"  [{label}] could not resume ({str(e)[:120]}); submitting again")
        last_err = None
        for attempt in range(3):
            try:
                handle = self.fc.submit(endpoint, arguments=args)
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status and 400 <= status < 500 and status not in (408, 429):
                    raise UGCError(f"{endpoint} rejected the request (HTTP {status}): {str(e)[:900]}") from e
                last_err = e
                time.sleep(5 * (attempt + 1))
                continue
            self.state.put("requests", key, {"request_id": handle.request_id, "hash": ahash,
                                             "endpoint": endpoint, "t": time.time()})
            t0 = time.time()
            try:
                res = handle.get(interval=2.0)
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status and 400 <= status < 500 and status not in (408, 429):
                    self.state.put("requests", key, None)
                    raise UGCError(f"{endpoint} failed for [{label}] (HTTP {status}): {str(e)[:900]}") from e
                raise UGCError(
                    f"[{label}] lost contact while waiting ({str(e)[:200]}). The request is still recorded; "
                    f"re-run the same command to collect it without paying twice.") from e
            self.state.put("requests", key, None)
            log(f"  [{label}] done in {time.time() - t0:.0f}s")
            return res
        raise UGCError(f"could not submit to {endpoint}: {last_err}")


def download(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        dest.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        return dest
    for attempt in range(4):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                os.replace(tmp, dest)
                return dest
        except Exception as e:
            if attempt == 3:
                raise UGCError(f"download failed for {url[:80]}: {e}") from e
            time.sleep(3 * (attempt + 1))


def elevenlabs_tts(text, voice_id, model_id, settings, dest, previous_text=None, next_text=None, language_code=None):
    """Direct ElevenLabs text-to-speech (gives access to the full Voice Library incl. Indian voices)."""
    key = elevenlabs_key()
    if not key:
        raise UGCError("voice.provider is 'elevenlabs' but no ElevenLabs key was found. Run:\n"
                       "  python3 scripts/ugc.py setkey --elevenlabs\nor set ELEVENLABS_API_KEY.")
    body = {"text": text, "model_id": model_id, "voice_settings": settings}
    if previous_text:
        body["previous_text"] = previous_text
    if next_text:
        body["next_text"] = next_text
    if language_code:
        body["language_code"] = language_code
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    for attempt in range(3):
        r = requests.post(url, json=body, headers={"xi-api-key": key, "accept": "audio/mpeg"}, timeout=180)
        if r.status_code == 200:
            Path(dest).write_bytes(r.content)
            return dest
        if 400 <= r.status_code < 500 and r.status_code != 429:
            raise UGCError(f"ElevenLabs rejected the request (HTTP {r.status_code}): {r.text[:600]}")
        time.sleep(4 * (attempt + 1))
    raise UGCError(f"ElevenLabs TTS failed: HTTP {r.status_code} {r.text[:300]}")
