"""Shared helpers: paths, episode loading, tokenising narration, shot timing.

Every stage of the pipeline reads `episodes/<id>/episode.json` and writes into
`output/<id>/`. Nothing here depends on Blender, so it can be imported both by
normal Python scripts and by the Blender build script.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
OUTPUT = ROOT / "output"

# A "word" for captions and timing: keep apostrophes / hyphens inside words.
WORD_RE = re.compile(r"[\w'’\-]+[.,!?;:…]*\"?|\"[\w'’\-]+[.,!?;:…]*\"?", re.UNICODE)


def load_episode(ep_id: str) -> dict:
    return json.loads((EPISODES / ep_id / "episode.json").read_text(encoding="utf-8"))


def out_dir(ep_id: str) -> Path:
    d = OUTPUT / ep_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def tokenize(text: str) -> list[str]:
    """Split narration into display words, keeping punctuation glued to them."""
    return [m.group(0) for m in WORD_RE.finditer(text)]


def clean(word: str) -> str:
    return re.sub(r"[^\w'’\-]", "", word.lower())


def full_script(ep: dict) -> str:
    return " ".join(s["text"] for s in ep["shots"] if s["text"]).strip()


def shot_tokens(ep: dict) -> list[tuple[str, list[str]]]:
    return [(s["id"], tokenize(s["text"])) for s in ep["shots"]]


def quoted_flags(text: str) -> list[bool]:
    """For each token of `text`, True if it is inside a "quoted" line (dialogue)."""
    flags, inside = [], False
    for tok in tokenize(text):
        starts = tok.startswith('"')
        ends = tok.endswith('"') and not (starts and len(tok) == 1)
        if starts:
            inside = True
        flags.append(inside)
        if ends:
            inside = False
    return flags


def load_words(ep_id: str) -> list[dict]:
    return json.loads((out_dir(ep_id) / "words.json").read_text(encoding="utf-8"))


def shot_timings(ep: dict, words: list[dict]) -> list[dict]:
    """Map every shot to [start, end] seconds using the aligned word list.

    The narration of shot N starts at its first word; the cut happens a few
    frames *before* the word (CUT_LEAD) so the picture leads the voice, which
    is what makes fast-cut shorts feel snappy.
    """
    CUT_LEAD = 0.12
    out, i = [], 0
    toks = shot_tokens(ep)
    total = sum(len(t) for _, t in toks)
    if total != len(words):
        raise ValueError(f"script has {total} words but words.json has {len(words)}; re-run align")
    for (sid, t), shot in zip(toks, ep["shots"]):
        if t:
            start = max(0.0, words[i]["start"] - (CUT_LEAD if i else 0.0))
            w = words[i:i + len(t)]
            i += len(t)
        else:
            start = words[i - 1]["end"] if i else 0.0
            w = []
        out.append({"id": sid, "start": start, "words": w, "shot": shot})
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]
    last = out[-1]
    last["end"] = (words[-1]["end"] if words else 0) + last["shot"].get("pad_after", 0.8)
    return out
