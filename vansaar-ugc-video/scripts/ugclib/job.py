"""A job = one video. Loads plan.yaml (with defaults), configs, paths and state."""
import re
from pathlib import Path

from .util import CONFIG_DIR, SKILL_DIR, State, UGCError, deep_merge, load_yaml

SHOTS = ("talk", "broll", "endcard")
FRAMINGS = ("close", "medium", "product")

SETUP_DEFAULTS = {"scene": "", "framing": "medium", "with_product": False, "candidates": 2, "pick": 1}
VOICE_DEFAULTS = {"provider": "fal", "voice": "", "speed": 1.0, "stability": 0.45, "similarity_boost": 0.8,
                  "style": 0.15, "language_code": None, "file": None, "model": None}
FINISH_DEFAULTS = {"tighten_pauses": 0.30, "grain": 0.45, "handheld": 0.5, "phone_audio": True, "punch_in": True}


class Job:
    def __init__(self, job_dir, mock=False, force=False):
        self.dir = Path(job_dir).expanduser().resolve()
        self.plan_path = self.dir / "plan.yaml"
        if not self.plan_path.exists():
            raise UGCError(f"no plan.yaml in {self.dir}. Create the job first with: ugc.py init --job {self.dir} ...")
        self.raw_plan = load_yaml(self.plan_path)
        self.models = load_yaml(CONFIG_DIR / "models.yaml")
        if (self.dir / "models.yaml").exists():  # per-job model overrides
            self.models = deep_merge(self.models, load_yaml(self.dir / "models.yaml"))
        self.brand = deep_merge(load_yaml(CONFIG_DIR / "brand.yaml"), self.raw_plan.get("brand") or {})
        self.plan = normalize_plan(self.raw_plan, self.brand)
        self.mock = mock
        self.force = force
        self.work = self.dir / "work"
        self.out = self.dir / "out"
        for d in (self.work / "voice" / "src", self.work / "voice" / "seg", self.work / "frames",
                  self.work / "clips", self.work / "norm", self.work / "mix", self.out):
            d.mkdir(parents=True, exist_ok=True)
        self.state = State(self.dir / "state.json")
        self._fal = None

    @property
    def fal(self):
        if self.mock:
            raise UGCError("internal: real API used in mock mode")
        if self._fal is None:
            from .falapi import Fal
            self._fal = Fal(self.state)
        return self._fal

    @property
    def slug(self):
        return re.sub(r"[^a-z0-9]+", "_", (self.plan.get("title") or self.dir.name).lower()).strip("_")[:60] or "ugc"

    def path(self, rel):
        """Resolve a path from plan.yaml (relative to the job folder) or brand.yaml (relative to the skill)."""
        if rel is None:
            return None
        p = Path(rel).expanduser()
        if p.is_absolute():
            return p
        if (self.dir / p).exists():
            return self.dir / p
        if (SKILL_DIR / p).exists():
            return SKILL_DIR / p
        return self.dir / p

    @property
    def segments(self):
        return self.plan["segments"]

    def spend(self, stage, item, usd):
        self.state.add_spend(stage, item, usd, mock=self.mock)


def normalize_plan(raw, brand):
    p = dict(raw)
    p.setdefault("title", "Vansaar UGC")
    p["language"] = (p.get("language") or "en").lower()
    p["inputs"] = dict(p.get("inputs") or {})
    ch = dict(p.get("character") or {})
    ch.setdefault("description", "")
    ch.setdefault("pronoun", "she")
    p["character"] = ch
    p["voice"] = deep_merge(VOICE_DEFAULTS, p.get("voice") or {})
    setups = {}
    for name, s in (p.get("setups") or {}).items():
        setups[name] = deep_merge(SETUP_DEFAULTS, s or {})
    p["setups"] = setups
    segs = []
    for i, s in enumerate(p.get("segments") or [], 1):
        s = dict(s or {})
        s.setdefault("id", f"s{i:02d}")
        s["id"] = str(s["id"])
        s.setdefault("shot", "talk")
        s["say"] = (s.get("say") or "").strip()
        s.setdefault("caption", None)
        s.setdefault("performance", "")
        s.setdefault("zoom", None)
        s.setdefault("hold", None)
        if s["shot"] == "broll":
            b = dict(s.get("broll") or {})
            b.setdefault("scene", "")
            b.setdefault("motion", "")
            b.setdefault("with_person", False)
            b.setdefault("with_product", True)
            b.setdefault("image", None)
            b.setdefault("video", None)
            b.setdefault("candidates", 1)
            b.setdefault("pick", 1)
            s["broll"] = b
        segs.append(s)
    p["segments"] = segs
    caps = dict(brand.get("captions") or {})
    caps["enabled"] = True
    p["captions"] = deep_merge(caps, p.get("captions") or {})
    p["finish"] = deep_merge(FINISH_DEFAULTS, p.get("finish") or {})
    p["music"] = deep_merge({"file": None, "volume_db": -22}, p.get("music") or {})
    p["endcard"] = deep_merge(brand.get("endcard") or {}, p.get("endcard") or {})
    p["disclosure"] = deep_merge(brand.get("disclosure") or {}, p.get("disclosure") or {})
    return p
