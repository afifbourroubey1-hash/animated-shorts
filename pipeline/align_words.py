"""Step 1b — Word timings when the voice did NOT come from tts_elevenlabs.py.

Three modes (pick the best one you can run):

  --whisper voice.wav   Most accurate. Uses faster-whisper word timestamps and
                        maps them onto the script tokens (the script text always
                        wins, whisper only supplies the times).
                        pip install faster-whisper
  --audio voice.wav     No ML. Finds speech regions with ffmpeg silencedetect and
                        spreads the words over them, weighted by word length.
                        Good enough for captions; check pauses by eye.
  --estimate            No audio at all. 2.7 words/s plus punctuation pauses.
                        Use it to block out the animatic before recording.

Writes output/<id>/words.json and, with --audio/--whisper, copies the audio to
output/<id>/voice.wav (48 kHz mono).
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import load_episode, out_dir, full_script, tokenize, clean  # noqa: E402

PAUSE = {",": 0.18, ";": 0.25, ":": 0.25, ".": 0.38, "!": 0.38, "?": 0.38, "…": 0.45}


def estimate(tokens: list[str], wps: float = 2.7, t0: float = 0.15) -> list[dict]:
    t, out = t0, []
    for tok in tokens:
        core = clean(tok)
        dur = max(0.16, (len(core) / 5.2) / wps * 1.0)
        out.append({"word": tok, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur + PAUSE.get(tok.rstrip('"')[-1:], 0.02)
    return out


def speech_regions(wav: str, noise_db: int = -32, min_sil: float = 0.12) -> list[tuple[float, float]]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af",
                        f"silencedetect=n={noise_db}dB:d={min_sil}", "-f", "null", "-"],
                       capture_output=True, text=True)
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr).groups()
    dur = int(h) * 3600 + int(m) * 60 + float(s)
    s_starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    s_ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    regions, cur = [], 0.0
    for a, b in zip(s_starts, s_ends + [dur] * (len(s_starts) - len(s_ends))):
        if a - cur > 0.05:
            regions.append((cur, a))
        cur = b
    if dur - cur > 0.05:
        regions.append((cur, dur))
    return regions


def from_audio(tokens: list[str], wav: str) -> list[dict]:
    """Phrase-aware heuristic aligner (no ML).

    1. Speech regions come from silencedetect.
    2. Every punctuation mark in the script should land on a pause: phrase
       boundaries are snapped (monotonically) to the pause whose position in
       "speech time" is closest to the boundary's position in "text length".
    3. Inside each stretch, words are spread by length.
    """
    regions = speech_regions(wav)
    weights = [len(clean(t)) + 1.5 for t in tokens]
    total_w = sum(weights)
    # speech-time axis: cumulative speech duration at the end of each region
    cum, acc = [], 0.0
    for a, b in regions:
        acc += b - a
        cum.append(acc)
    total_s = acc

    def speech_to_clock(x: float) -> float:
        prev = 0.0
        for (a, b), c in zip(regions, cum):
            if x <= c + 1e-9:
                return a + (x - prev)
            prev = c
        return regions[-1][1]

    # phrase boundaries (index of the last token of a phrase)
    bounds = [i for i, t in enumerate(tokens[:-1]) if t.rstrip('"')[-1:] in PAUSE]
    snapped, gi = {}, 0
    gaps = cum[:-1]  # speech-time position of each pause
    cw = 0.0
    for i, w in enumerate(weights):
        cw += w
        if i in bounds and gi < len(gaps):
            target = cw / total_w * total_s
            best = min(range(gi, len(gaps)), key=lambda g: abs(gaps[g] - target))
            if abs(gaps[best] - target) < 0.12 * total_s:
                snapped[i] = best
                gi = best + 1
    # walk phrases between snapped anchors
    out, start_i, start_s = [], 0, 0.0
    anchors = sorted(snapped.items()) + [(len(tokens) - 1, None)]
    for end_i, g in anchors:
        end_s = gaps[g] if g is not None else total_s
        seg = range(start_i, end_i + 1)
        sw = sum(weights[k] for k in seg)
        x = start_s
        for k in seg:
            d = weights[k] / sw * (end_s - start_s)
            a, b = speech_to_clock(x + 1e-6), speech_to_clock(x + d)
            out.append({"word": tokens[k], "start": round(a, 3), "end": round(max(b, a + 0.05), 3)})
            x += d
        start_i, start_s = end_i + 1, end_s
    return out


def from_whisper(tokens: list[str], wav: str, model: str = "small") -> list[dict]:
    from faster_whisper import WhisperModel  # type: ignore
    m = WhisperModel(model, device="auto", compute_type="int8")
    segs, _ = m.transcribe(wav, word_timestamps=True)
    hyp = [w for s in segs for w in s.words]
    a = [clean(t) for t in tokens]
    b = [clean(w.word) for w in hyp]
    out: list[dict | None] = [None] * len(tokens)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("equal", "replace") and j2 > j1:
            for k in range(i1, i2):  # spread the matched span evenly over script words
                f0 = (k - i1) / (i2 - i1)
                f1 = (k - i1 + 1) / (i2 - i1)
                s0 = hyp[j1].start + f0 * (hyp[j2 - 1].end - hyp[j1].start)
                s1 = hyp[j1].start + f1 * (hyp[j2 - 1].end - hyp[j1].start)
                out[k] = {"word": tokens[k], "start": round(s0, 3), "end": round(s1, 3)}
    for k, w in enumerate(out):  # script words whisper missed: squeeze between neighbours
        if w is None:
            prev_end = out[k - 1]["end"] if k else 0.0
            out[k] = {"word": tokens[k], "start": prev_end, "end": prev_end + 0.15}
    return out  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--whisper", metavar="WAV")
    g.add_argument("--audio", metavar="WAV")
    g.add_argument("--estimate", action="store_true")
    ap.add_argument("--wps", type=float, default=2.7, help="words/second for --estimate")
    a = ap.parse_args()

    ep = load_episode(a.episode)
    d = out_dir(a.episode)
    tokens = tokenize(full_script(ep))
    src = a.whisper or a.audio
    if src:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "48000", "-ac", "1",
                        str(d / "voice.wav")], check=True)
        src = str(d / "voice.wav")
    words = (from_whisper(tokens, src) if a.whisper else
             from_audio(tokens, src) if a.audio else estimate(tokens, a.wps))
    (d / "words.json").write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(words)} words, narration ends at {words[-1]['end']:.2f}s -> {d / 'words.json'}")


if __name__ == "__main__":
    main()
