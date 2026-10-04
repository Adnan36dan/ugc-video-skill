"""Small shared helpers: paths, logging, ffmpeg/ffprobe, YAML/JSON, hashing, job state."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = SKILL_DIR / "config"
ASSETS_DIR = SKILL_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
TEMPLATES_DIR = SKILL_DIR / "templates"

W, H, FPS = 1080, 1920, 30
SR = 48000


class UGCError(Exception):
    """An error with a message meant for the person running the pipeline."""


_PRINT_LOCK = threading.Lock()


def log(msg=""):
    with _PRINT_LOCK:
        print(msg, flush=True)


def warn(msg):
    log(f"WARNING: {msg}")


def run(cmd, cwd=None, capture=False):
    """Run a command; on failure raise UGCError with the tail of stderr."""
    cmd = [str(c) for c in cmd]
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-25:])
        raise UGCError(f"command failed ({cmd[0]}):\n{' '.join(cmd)[:600]}\n--- stderr ---\n{tail}")
    return p.stdout if capture else p


def ffmpeg(*args, cwd=None):
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd)


def ffprobe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
              capture=True)
    return json.loads(out)


def duration(path):
    info = ffprobe(path)
    d = info.get("format", {}).get("duration")
    if d is None:
        for s in info.get("streams", []):
            if s.get("duration"):
                return float(s["duration"])
        raise UGCError(f"could not read duration of {path}")
    return float(d)


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(data, path):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=110)


def load_json(path, default=None):
    if not Path(path).exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def obj_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def hex_to_rgb(hexstr):
    s = hexstr.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def which_or_die(binary):
    if shutil.which(binary) is None:
        raise UGCError(f"'{binary}' is not installed. See references/troubleshooting.md (Installing ffmpeg).")


def deep_merge(base, override):
    """Return base updated recursively with override (override wins; None values in override are ignored)."""
    out = dict(base or {})
    for k, v in (override or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class State:
    """Per-job JSON record of what was generated (for caching/resume) and estimated spend."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = load_json(self.path, {}) or {}

    def get(self, section, key, default=None):
        with self.lock:
            return self.data.get(section, {}).get(key, default)

    def put(self, section, key, value):
        with self.lock:
            self.data.setdefault(section, {})[key] = value
            save_json(self.data, self.path)

    def add_spend(self, stage, item, usd, mock=False):
        with self.lock:
            self.data.setdefault("spend", []).append(
                {"stage": stage, "item": item, "usd": round(usd, 4), "mock": mock, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            save_json(self.data, self.path)

    def spent(self, include_mock=False):
        with self.lock:
            return sum(s["usd"] for s in self.data.get("spend", []) if include_mock or not s.get("mock"))


def print_table(rows, headers):
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    log(line)
    log("  ".join("-" * w for w in widths))
    for r in rows:
        log("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)
