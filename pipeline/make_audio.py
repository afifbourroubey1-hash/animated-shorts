"""Step 4 — Sound design + music + mix, all synthesised with numpy (no sample packs).

Layers (in the order a sound designer builds them):
  1. Voice-over (output/<id>/voice.wav)             -> loudest, everything ducks under it
  2. Ambience bed: desert wind for the whole short
  3. Spot SFX locked to story beats (saw, clank, ka-chunk, coin, groan, snap, boom...)
  4. Transition whooshes on every cut
  5. Music: plucked pentatonic loop, ducked under the voice, cut to silence
     before the climax so the final impact hits harder

Writes output/<id>/mix.wav (48 kHz stereo). Real sample libraries can replace
any synth: drop a WAV in assets/sfx/<name>.wav and it is used instead.

Usage: python pipeline/make_audio.py rail_gaps
"""
from __future__ import annotations

import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_episode, load_words, out_dir, shot_timings  # noqa: E402

SR = 48000
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- io helpers
def read_wav(path) -> np.ndarray:
    with wave.open(str(path)) as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        x = np.frombuffer(w.readframes(n), dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float32)
        x /= float(2 ** (8 * sw - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        t_old = np.arange(len(x)) / sr
        t_new = np.arange(int(len(x) * SR / sr)) / SR
        x = np.interp(t_new, t_old, x).astype(np.float32)
    return x


def write_wav(path, stereo: np.ndarray) -> None:
    y = np.clip(stereo, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


def t(n_sec: float) -> np.ndarray:
    return np.arange(int(n_sec * SR)) / SR


def env(n: int, a: float = 0.005, r: float = 0.2) -> np.ndarray:
    tt = np.arange(n) / SR
    return np.minimum(1, tt / max(a, 1e-4)) * np.exp(-tt / max(r, 1e-4))


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # one-pole; fine for short SFX
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def lowpass_fast(x: np.ndarray, cutoff: float) -> np.ndarray:
    """FFT brick-ish lowpass for long signals (wind bed)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, n=len(x)).astype(np.float32)


def sample(name: str):
    p = ROOT / "assets" / "sfx" / f"{name}.wav"
    return read_wav(p) if p.exists() else None


# ------------------------------------------------------------------- synths
def sfx_whoosh():
    n = int(0.35 * SR)
    x = rng.standard_normal(n).astype(np.float32)
    x = lowpass(x, 2500)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return x * e * 0.5


def sfx_saw():
    n = int(0.22 * SR)
    x = rng.standard_normal(n).astype(np.float32)
    rasp = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 90 * t(0.22)))
    return (x - lowpass(x, 1500)) * rasp * np.sin(np.linspace(0, np.pi, n)) * 0.45


def sfx_clank(freq=1800):
    tt = t(0.5)
    x = sum(np.sin(2 * np.pi * freq * k * tt) / k for k in (1, 2.76, 5.4))
    return (x * env(len(tt), 0.001, 0.08) * 0.5).astype(np.float32)


def sfx_kachunk():
    a = sfx_clank(420) * 0.9
    thump = np.sin(2 * np.pi * 70 * t(0.25)) * env(int(0.25 * SR), 0.002, 0.06)
    out = np.zeros(int(0.5 * SR), np.float32)
    out[:len(a)] += a[:len(out)]
    off = int(0.11 * SR)
    out[off:off + len(thump)] += thump[:len(out) - off] * 0.9
    out[off:off + len(a)] += (a * 0.7)[:len(out) - off]
    return out


def sfx_coin():
    tt = t(0.9)
    x = (np.sin(2 * np.pi * 2637 * tt) + 0.6 * np.sin(2 * np.pi * 3520 * tt)) * env(len(tt), 0.001, 0.25)
    return (x * 0.35).astype(np.float32)


def sfx_chaching():
    a = sfx_coin()
    out = np.zeros(int(1.0 * SR), np.float32)
    out[:len(a)] += a[:len(out)]
    out[int(0.12 * SR):] += a[:len(out) - int(0.12 * SR)] * 0.8
    return out


def sfx_boing(up=True):
    tt = t(0.6)
    f = 180 + (500 if up else -100) * (tt / tt[-1]) ** 0.7 + 25 * np.sin(2 * np.pi * 9 * tt)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * env(len(tt), 0.01, 0.35) * 0.45).astype(np.float32)


def sfx_rustle():
    n = int(0.6 * SR)
    x = rng.standard_normal(n).astype(np.float32)
    am = (rng.random(n // 400 + 1) > 0.6).repeat(400)[:n] * 1.0
    return (x - lowpass(x, 3000)) * lowpass(am.astype(np.float32), 40) * 0.35


def sfx_pop():
    tt = t(0.12)
    f = 900 - 600 * tt / tt[-1]
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.001, 0.03) * 0.5).astype(np.float32)


def sfx_groan(dur=3.0):
    tt = t(dur)
    f = 55 + 10 * np.sin(2 * np.pi * 0.7 * tt)
    mod = 1 + 0.8 * np.sin(2 * np.pi * (f * 1.41) * tt)
    x = np.sin(2 * np.pi * np.cumsum(f * mod) / SR) + 0.3 * rng.standard_normal(len(tt))
    x = lowpass_fast(x.astype(np.float32), 600)
    return x * np.sin(np.linspace(0, np.pi, len(tt))) ** 0.5 * 0.5


def sfx_snap():
    n = int(0.9 * SR)
    x = rng.standard_normal(n).astype(np.float32) * env(n, 0.001, 0.05)
    ring = sfx_clank(260)
    x[:len(ring)] += ring * 1.2
    return x * 0.8


def sfx_boom(dur=2.5):
    n = int(dur * SR)
    x = rng.standard_normal(n).astype(np.float32)
    x = lowpass_fast(x, 180) * 6 + lowpass_fast(x, 1500) * env(n, 0.002, 0.3)
    sub = np.sin(2 * np.pi * np.cumsum(60 - 35 * np.arange(n) / n) / SR) * env(n, 0.002, 0.6)
    return (x * env(n, 0.003, 0.7) + sub).astype(np.float32) * 0.8


def sfx_whistle(dur=1.4):
    tt = t(dur)
    x = sum(np.sin(2 * np.pi * f * tt) for f in (523, 659, 784)) / 3
    x += 0.15 * rng.standard_normal(len(tt))
    e = np.minimum(1, tt / 0.08) * np.minimum(1, (dur - tt) / 0.3)
    return (x * e * 0.25).astype(np.float32)


def sfx_chug(dur, bpm=180):
    out = np.zeros(int(dur * SR), np.float32)
    step = int(60 / bpm * SR)
    burst = rng.standard_normal(int(0.12 * SR)).astype(np.float32)
    burst = (burst - lowpass(burst, 400)) * env(len(burst), 0.003, 0.04) * 0.25
    for k, i in enumerate(range(0, len(out) - len(burst), step)):
        out[i:i + len(burst)] += burst * (1.0 if k % 2 == 0 else 0.6)
    return out


def sfx_cicadas(dur):
    tt = t(dur)
    x = np.sin(2 * np.pi * 4200 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 38 * tt)) ** 4
    x *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.6 * tt)
    return (x * 0.06).astype(np.float32)


def wind_bed(dur):
    n = int(dur * SR)
    x = rng.standard_normal(n).astype(np.float32)
    x = lowpass_fast(x, 350)
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.08 * np.arange(n) / SR)
    return x / (np.abs(x).max() + 1e-6) * swell * 0.12


def pluck(freq, dur=0.6):
    """Karplus-Strong plucked string."""
    n = int(dur * SR)
    p = int(SR / freq)
    buf = rng.uniform(-1, 1, p).astype(np.float32)
    out = np.empty(n, np.float32)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out


def music(dur, bpm=104):
    """Light, curious pizzicato loop (C major pentatonic, I–vi–IV–V)."""
    beat = 60 / bpm
    out = np.zeros(int(dur * SR) + SR, np.float32)
    prog = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
    cache = {}
    k, tt = 0, 0.0
    melody = [392.0, 440.0, 523.3, 440.0, 392.0, 329.6, 293.7, 329.6]
    while tt < dur:
        chord = prog[(k // 8) % 4]
        notes = [chord[0] / 2] if k % 2 == 0 else [chord[(k // 2) % 3]]
        if k % 4 == 3:
            notes.append(melody[(k // 4) % len(melody)])
        for f in notes:
            if f not in cache:
                cache[f] = pluck(f)
            s = int(tt * SR)
            seg = cache[f][:len(out) - s]
            out[s:s + len(seg)] += seg * (0.6 if f < 200 else 0.35)
        k += 1
        tt += beat / 2
    return out[:int(dur * SR)]


# -------------------------------------------------------------------- mixing
def place(bus: np.ndarray, clip: np.ndarray, at: float, gain_db: float = 0.0) -> None:
    s = int(max(0.0, at) * SR)
    if s >= len(bus):
        return
    seg = clip[:len(bus) - s] * (10 ** (gain_db / 20))
    bus[s:s + len(seg)] += seg


def word_time(shot, needle, default_frac=0.5):
    for w in shot["words"]:
        if w["word"].lower().strip('".,!?').startswith(needle):
            return w["start"]
    return shot["start"] + (shot["end"] - shot["start"]) * default_frac


def duck_envelope(voice: np.ndarray, depth_db=-9.0, attack=0.05, release=0.35) -> np.ndarray:
    """Sidechain-style ducking gain from the voice level."""
    hop = 480
    frames = np.sqrt(np.convolve(voice ** 2, np.ones(hop) / hop, mode="same")[::hop] + 1e-9)
    active = (20 * np.log10(frames) > -38).astype(np.float32)
    g = np.ones_like(active)
    cur = 1.0
    lo = 10 ** (depth_db / 20)
    for i, a in enumerate(active):
        target = lo if a else 1.0
        coef = attack if target < cur else release
        cur += (target - cur) * min(1.0, (hop / SR) / coef)
        g[i] = cur
    return np.repeat(g, hop)[:len(voice)]


def main() -> None:
    ep_id = sys.argv[1]
    ep = load_episode(ep_id)
    d = out_dir(ep_id)
    words = load_words(ep_id)
    shots = shot_timings(ep, words)
    dur = shots[-1]["end"] + 0.5
    n = int(dur * SR)

    voice = np.zeros(n, np.float32)
    vp = d / "voice.wav"
    if vp.exists():
        v = read_wav(vp)
        v = v / (np.abs(v).max() + 1e-6) * 0.9
        voice[:min(n, len(v))] = v[:n]
    else:
        print("no voice.wav: mixing SFX + music only")

    sfx = np.zeros(n, np.float32)
    S = {k: (sample(k) if sample(k) is not None else f()) for k, f in {
        "whoosh": sfx_whoosh, "saw": sfx_saw, "clank": sfx_clank, "kachunk": sfx_kachunk, "coin": sfx_coin,
        "chaching": sfx_chaching, "boing": sfx_boing, "rustle": sfx_rustle, "pop": sfx_pop, "snap": sfx_snap,
        "boom": sfx_boom, "whistle": sfx_whistle}.items()}
    place(sfx, wind_bed(dur), 0, -6)
    fps = ep["fps"]
    climax_start = dur
    for sh in shots:
        a, b, typ = sh["start"], sh["end"], sh["shot"]["type"]
        if sh is not shots[0]:
            place(sfx, S["whoosh"], a - 0.18, -14)
        if typ == "hook_saw":
            for k, x in enumerate(np.arange(a + 0.1, b - 0.1, 8 / fps)):
                place(sfx, S["saw"], x, -4 if k % 2 else -7)
            place(sfx, S["whistle"], a + 0.4, -16)
        elif typ == "station_banner":
            place(sfx, S["chaching"], word_time(sh, "wins", 0.4), -6)
        elif typ == "gap_macro_boss":
            place(sfx, S["boing"], word_time(sh, "purple", 0.85) - 0.1, -6)
        elif typ == "rival_lay":
            for x in np.arange(a + 0.2, b, 0.4):
                place(sfx, S["clank"], x, -10)
        elif typ == "window_rattle":
            for x in np.arange(a + 4 / fps, b - 4 / fps, int(0.45 * fps) / fps):
                place(sfx, S["kachunk"], x, -3)
        elif typ == "newspaper":
            place(sfx, S["rustle"], a + 0.1, -4)
            place(sfx, S["rustle"], a + (b - a) * 0.55, -6)
        elif typ == "calendar_heat":
            place(sfx, sfx_cicadas(b - a + 4), a, 0)
        elif typ == "gap_shrink":
            place(sfx, S["coin"], word_time(sh, "coin", 0.8) + 10 / fps, -4)
        elif typ == "science_diagram":
            for needle, frac in (("but", 0.0), ("hot", 0.3), ("seven", 0.6)):
                place(sfx, S["pop"], word_time(sh, needle, frac) + 4 / fps, -6)
        elif typ == "rail_glow":
            place(sfx, sfx_groan(b - a), a, -2)
            climax_start = min(climax_start, a)
        elif typ == "buckle":
            place(sfx, sfx_chug(b - a + 1), a, -4)
            place(sfx, S["whistle"], a + 0.5, -8)
            place(sfx, S["snap"], word_time(sh, "sideways", 0.55) + 2 / fps, 0)
        elif typ == "impact":
            place(sfx, S["boom"], a + 8 / fps, 2)

    mus = music(dur)
    # music fades out as the rails start groaning (silence before the hit)
    fade = np.ones(n, np.float32)
    cs = int(climax_start * SR)
    fade[cs:] = np.maximum(0, 1 - (np.arange(n - cs) / (1.5 * SR)))
    mus = mus[:n] * fade
    duck = duck_envelope(voice)
    mix = voice * 1.0 + sfx * 0.9 * (0.55 + 0.45 * duck) + mus * 0.22 * duck
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    stereo = np.stack([mix, mix], axis=1)
    write_wav(d / "mix.wav", stereo)
    print(f"mix.wav {dur:.1f}s -> {d}")


if __name__ == "__main__":
    main()
