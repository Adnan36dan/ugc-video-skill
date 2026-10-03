"""Exercise the REAL (non-mock) code paths against a fake fal.ai that validates every request
against the model input schemas published on fal.ai (checked Oct 2026). No network, no cost.

    python3 tests/fake_fal_test.py /tmp/somewhere
"""
import base64
import hashlib
import itertools
import shutil
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "vansaar-ugc-video"
sys.path.insert(0, str(ROOT / "scripts"))

from ugclib import mock  # noqa: E402
from ugclib.util import ffmpeg  # noqa: E402

SCHEMAS = {  # endpoint -> (allowed input keys, required keys)
    "fal-ai/elevenlabs/tts/multilingual-v2": (
        {"text", "voice", "stability", "similarity_boost", "style", "speed", "timestamps", "previous_text",
         "next_text", "language_code", "apply_text_normalization"}, {"text"}),
    "fal-ai/elevenlabs/speech-to-text": ({"audio_url", "language_code", "tag_audio_events", "diarize"}, {"audio_url"}),
    "fal-ai/nano-banana-pro/edit": (
        {"prompt", "num_images", "seed", "aspect_ratio", "output_format", "safety_tolerance", "sync_mode",
         "image_urls", "system_prompt", "resolution", "limit_generations", "enable_web_search"}, {"prompt", "image_urls"}),
    "fal-ai/bytedance/omnihuman/v1.5": ({"prompt", "image_url", "mask_url", "audio_url", "turbo_mode", "resolution"},
                                        {"image_url", "audio_url"}),
    "fal-ai/kling-video/v3/pro/image-to-video": (
        {"prompt", "multi_prompt", "start_image_url", "duration", "generate_audio", "end_image_url", "elements",
         "shot_type", "negative_prompt", "cfg_scale"}, {"start_image_url"}),
}
ENUMS = {("fal-ai/nano-banana-pro/edit", "aspect_ratio"): {"auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5",
                                                            "3:4", "2:3", "9:16"},
         ("fal-ai/nano-banana-pro/edit", "resolution"): {"1K", "2K", "4K"},
         ("fal-ai/bytedance/omnihuman/v1.5", "resolution"): {"720p", "1080p"},
         ("fal-ai/kling-video/v3/pro/image-to-video", "duration"): {str(i) for i in range(3, 16)}}

WORK = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/fake_fal").resolve()
UPLOADS, CALLS, TTS_WORDS, ids = {}, [], {}, itertools.count(1)


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def upload_file(path):
    url = f"https://fake.fal.media/{len(UPLOADS)}_{Path(path).name}"
    UPLOADS[url] = Path(path)
    return url


def respond(endpoint, args):
    allowed, required = SCHEMAS[endpoint]
    unknown, missing = set(args) - allowed, required - set(args)
    assert not unknown, f"{endpoint}: unknown inputs {unknown}"
    assert not missing, f"{endpoint}: missing inputs {missing}"
    for (ep, key), values in ENUMS.items():
        if ep == endpoint and key in args:
            assert args[key] in values, f"{endpoint}: {key}={args[key]!r} not in {values}"
    for k, v in args.items():
        if k.endswith("_url"):
            assert v in UPLOADS, f"{endpoint}: {k} is not an uploaded file"
        if k.endswith("_urls"):
            assert all(u in UPLOADS for u in v), f"{endpoint}: {k} has non-uploaded files"
    CALLS.append(endpoint)
    tmp = WORK / "fake_out"
    tmp.mkdir(parents=True, exist_ok=True)
    n = next(ids)
    if "tts" in endpoint:
        wav = mock.tts(args["text"], tmp / f"tts{n}.wav")
        mp3 = tmp / f"tts{n}.mp3"
        ffmpeg("-i", wav, mp3)
        TTS_WORDS[hashlib.sha1(mp3.read_bytes()).hexdigest()] = mock.stt(wav)
        return {"audio": {"url": data_uri(mp3, "audio/mpeg")}}
    if "speech-to-text" in endpoint:
        src = UPLOADS[args["audio_url"]]          # .../voice/src/s01.wav, converted from s01.mp3
        mp3 = src.with_suffix(".mp3")
        words = TTS_WORDS.get(hashlib.sha1(mp3.read_bytes()).hexdigest(), []) if mp3.exists() else []
        assert words, "speech-to-text got audio the fake TTS never produced"
        out = [{"text": w["text"], "start": w["start"], "end": w["end"], "type": "word"} for w in words]
        out.insert(1, {"text": " ", "start": None, "end": None, "type": "spacing"})
        return {"text": " ".join(w["text"] for w in words), "language_code": "eng", "language_probability": 1.0,
                "words": out}
    if "nano-banana" in endpoint:
        imgs = []
        for i in range(args.get("num_images", 1)):
            p = mock.image("fake", tmp / f"img{n}_{i}.png", face=UPLOADS[args["image_urls"][0]], variant=i + 1)
            imgs.append({"url": data_uri(p, "image/png")})
        return {"images": imgs, "description": ""}
    if "omnihuman" in endpoint:
        p = mock.avatar(UPLOADS[args["image_url"]], UPLOADS[args["audio_url"]], tmp / f"av{n}.mp4")
        return {"video": {"url": data_uri(p, "video/mp4")}, "duration": 1.0}
    if "kling" in endpoint:
        p = mock.i2v(UPLOADS[args["start_image_url"]], float(args["duration"]), tmp / f"i2v{n}.mp4")
        return {"video": {"url": data_uri(p, "video/mp4")}}
    raise AssertionError(endpoint)


class Handle:
    def __init__(self, endpoint, args):
        self.request_id = f"req-{next(ids)}"
        self._res = respond(endpoint, args)

    def get(self, interval=0.1):
        return self._res


fake = types.ModuleType("fal_client")
fake.upload_file = upload_file
fake.submit = lambda endpoint, arguments: Handle(endpoint, arguments)
fake.result = lambda endpoint, rid: (_ for _ in ()).throw(RuntimeError("no such request"))
sys.modules["fal_client"] = fake

if __name__ == "__main__":
    import os
    import yaml
    os.environ["FAL_KEY"] = "fake-key-for-tests"
    import ugc  # noqa: E402
    job = WORK / "job"
    shutil.rmtree(WORK, ignore_errors=True)
    (job / "inputs").mkdir(parents=True)
    mock.demo_inputs(job / "inputs")
    plan = yaml.safe_load((ROOT / "templates" / "plan.example.yaml").read_text())
    plan["voice"]["voice"] = "Aria"
    plan["setups"]["sofa_close"]["candidates"] = 1
    (job / "plan.yaml").write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False))
    code = ugc.main(["all", "--job", str(job)])
    print("\nendpoints called:", {e: CALLS.count(e) for e in sorted(set(CALLS))})
    first = len(CALLS)
    code2 = ugc.main(["all", "--job", str(job)])
    assert len(CALLS) == first, f"second run made {len(CALLS) - first} paid calls; cache is broken"
    print(f"second run: 0 paid calls (cache OK); exit codes {code}, {code2}")
    sys.exit(code or code2)
