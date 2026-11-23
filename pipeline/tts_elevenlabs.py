"""Step 1 — Voice-over with ElevenLabs, including per-character timestamps.

Usage:
    export ELEVENLABS_API_KEY=...            # never commit this key
    python pipeline/tts_elevenlabs.py rail_gaps [--voice VOICE_ID]

Produces output/<id>/voice.wav and output/<id>/words.json
([{"word", "start", "end"}], one entry per token of the script).

The `/with-timestamps` endpoint returns the start/end time of every character,
so we get exact word timings for captions, cuts and lip-flaps with no extra
alignment step.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from common import load_episode, out_dir, full_script, tokenize, clean  # noqa: E402

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"


def char_alignment_to_words(script: str, align: dict) -> list[dict]:
    chars = align["characters"]
    starts = align["character_start_times_seconds"]
    ends = align["character_end_times_seconds"]
    text = "".join(chars)
    words, pos = [], 0
    for tok in tokenize(script):
        core = clean(tok)
        j = text.lower().find(core, pos) if core else -1
        idx = j if j != -1 else min(pos, len(chars) - 1)
        k_end = min(len(chars) - 1, idx + max(1, len(core)) - 1)
        words.append({"word": tok, "start": round(starts[idx], 3), "end": round(ends[k_end], 3)})
        pos = k_end + 1
    return words


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--voice", help="ElevenLabs voice_id (overrides episode.json)")
    a = ap.parse_args()

    ep = load_episode(a.episode)
    v = ep["voice"]
    voice_id = a.voice or v["voice_id"]
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or voice_id.startswith("REPLACE"):
        sys.exit("Set ELEVENLABS_API_KEY and a real voice_id (episode.json or --voice).")

    # Quotes are kept out of the TTS text (they only steer the captions/lip-sync).
    script = full_script(ep).replace('"', "")
    body = {
        "text": script,
        "model_id": v.get("model_id", "eleven_multilingual_v2"),
        "voice_settings": {k: v[k] for k in ("stability", "similarity_boost", "style", "speed") if k in v},
    }
    req = urllib.request.Request(
        API.format(voice=voice_id), data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())

    d = out_dir(a.episode)
    mp3 = d / "voice.mp3"
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1",
                    str(d / "voice.wav")], check=True)
    words = char_alignment_to_words(full_script(ep), data["alignment"])
    (d / "words.json").write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"voice.wav + {len(words)} timed words -> {d}")


if __name__ == "__main__":
    main()
