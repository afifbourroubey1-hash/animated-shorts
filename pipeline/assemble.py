"""Step 5 — Frames + mix + captions -> final vertical MP4, mastered for Shorts/Reels/TikTok.

    python pipeline/assemble.py rail_gaps [--fps-in 30] [--out name.mp4] [--no-captions]

What it does:
  * reads output/<id>/frames/%05d.png (whatever range was rendered; with
    --step N renders, pass --fps-in 30/N and it is retimed to 30 fps)
  * scales to 1080x1920 (lanczos) so preview renders still give a full-size file
  * burns captions.ass (libass)
  * audio: EBU R128 loudness to -14 LUFS / -1 dBTP (YouTube/TikTok/Instagram target)
  * H.264 High, CRF 18, yuv420p, +faststart (instant playback on phones)
  * 0.25 s fade-out at the end
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_episode, out_dir  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--fps-in", default=None, help="input frame rate (auto-detected from frame numbering)")
    ap.add_argument("--out")
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()

    ep = load_episode(a.episode)
    d = out_dir(a.episode)
    frames = sorted((d / "frames").glob("*.png"))
    if not frames:
        sys.exit("no frames rendered yet (run pipeline/blender/build_episode.py)")
    first = int(frames[0].stem)
    fps = ep["fps"]
    # auto-detect --step renders (00000, 00002, ... -> 15 fps input)
    nums = [int(f.stem) for f in frames]
    step = min((b - a for a, b in zip(nums, nums[1:])), default=1) or 1
    fps_in = a.fps_in or (str(fps) if step == 1 else f"{fps}/{step}")
    W, H = ep["resolution"]["final"]
    out = d / (a.out or f"{a.episode}.mp4")
    start_t = first / fps

    vf = [f"scale={W}:{H}:flags=lanczos", f"fps={fps}"]
    if not a.no_captions and (d / "captions.ass").exists():
        fonts = ROOT / "assets" / "fonts"
        # shift captions when only a part of the timeline was rendered
        vf.append(f"setpts=PTS+{start_t}/TB")
        vf.append(f"ass={d / 'captions.ass'}:fontsdir={fonts}")
        vf.append("setpts=PTS-STARTPTS")
    n_frames = len(frames)
    dur = n_frames / float(eval(fps_in))
    vf.append(f"fade=t=out:st={max(0, dur - 0.25):.2f}:d=0.25")

    cmd = ["ffmpeg", "-v", "error", "-y",
           "-framerate", fps_in, "-pattern_type", "glob", "-i", str(d / "frames" / "*.png")]
    mix = d / "mix.wav"
    if mix.exists():
        cmd += ["-ss", f"{start_t:.3f}", "-i", str(mix)]
    cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if mix.exists():
        cmd += ["-af", f"loudnorm=I=-14:TP=-1:LRA=11,afade=t=out:st={max(0, dur - 0.25):.2f}:d=0.25",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.3f}"]
    cmd += [str(out)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
    print(f"-> {out}\n{re.sub(r'\\s+', ' ', probe)}")


if __name__ == "__main__":
    main()
