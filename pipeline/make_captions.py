"""Step 3 — Word-by-word "pop" captions as an .ass subtitle file.

Style copied from the format of viral animated shorts:
  * 1–2 words on screen at a time, appearing exactly when spoken
  * heavy bold font, white fill, thick black outline + soft shadow
  * placed at ~62% of the height (below the faces, above the UI of the apps)
  * tiny scale "pop" (85% -> 100% in 80 ms)

Usage:
    python pipeline/make_captions.py rail_gaps [--max-words 2] [--font "Montserrat Black"]

Arabic: pass --font "Cairo Black" (or "Tajawal ExtraBold"); libass handles RTL
shaping automatically through fribidi/harfbuzz.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import load_episode, load_words, out_dir  # noqa: E402

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        text = " ".join(x["word"] for x in cur + [w])
        if cur and (len(cur) >= max_words or len(text) > max_chars):
            out.append(cur)
            cur = []
        cur.append(w)
        if w["word"].rstrip('"')[-1:] in ".!?,;:":  # never run a chunk across punctuation
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--max-words", type=int, default=2)
    ap.add_argument("--max-chars", type=int, default=14)
    ap.add_argument("--font", default="Montserrat Black")
    ap.add_argument("--size-ratio", type=float, default=0.042, help="font size as a fraction of height")
    ap.add_argument("--y", type=float, default=0.62, help="vertical position (0=top, 1=bottom)")
    a = ap.parse_args()

    ep = load_episode(a.episode)
    W, H = ep["resolution"]["final"]
    words = load_words(a.episode)
    size = round(H * a.size_ratio)
    lines = [HEADER.format(w=W, h=H, font=a.font, size=size, outline=round(size * 0.14),
                           shadow=round(size * 0.06))]
    chunks = chunk(words, a.max_words, a.max_chars)
    for i, c in enumerate(chunks):
        start = c[0]["start"]
        nxt = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else c[-1]["end"] + 0.6
        end = min(nxt, c[-1]["end"] + 0.6)
        text = " ".join(w["word"] for w in c).replace('"', "")
        pop = r"{\an5\pos(%d,%d)\fscx85\fscy85\t(0,80,\fscx100\fscy100)}" % (W // 2, round(H * a.y))
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Pop,,0,0,0,,{pop}{text}")
    p = out_dir(a.episode) / "captions.ass"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(chunks)} caption events -> {p}")


if __name__ == "__main__":
    main()
