"""Shot recipes. One function per shot "type" in episode.json.

Each recipe receives (ctx, shot) where shot has:
    f0, f1      first/last frame of the shot
    words       aligned words spoken during the shot [{word,start,end}]
    shot        the raw dict from episode.json
and must: create a camera (ctx.camera), place/animate the cast, and key any
story state (gap width, heat, buckle...).

All keyframes are LINEAR (set in build_episode.py); smooth motion is made by
sampling an ease curve every few frames (see ctx.camera / ease()).
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

import geo
import toon
from railroad import RAIL_HALF, RAIL_Z, rail_mesh

R = math.radians


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def word_frame(ctx, s, needle: str, default_frac: float = 0.5) -> int:
    """Frame where a word (case-insensitive, prefix match) starts inside this shot."""
    for w in s["words"]:
        if w["word"].lower().strip('".,!?').startswith(needle.lower()):
            return round(w["start"] * ctx.fps)
    return int(s["f0"] + (s["f1"] - s["f0"]) * default_frac)


class Ctx:
    def __init__(self, scene, fps):
        self.scene, self.fps = scene, fps
        self.chars = {}
        self.cam_coll = geo.coll("cameras")
        self._cam_i = 0

    def camera(self, f0, f1, keys, lens=28.0, shake=0.0, seed=0, marker=True, step=3):
        """keys: [(frac, cam_location, look_at), ...] (frac 0..1 within [f0, f1]).

        Interpolates with smoothstep between consecutive keys, sampled every
        `step` frames, plus optional handheld shake (metres).
        """
        self._cam_i += 1
        cd = bpy.data.cameras.new(f"cam{self._cam_i}")
        cd.lens = lens
        cd.sensor_fit = "AUTO"
        cd.clip_start = 0.02
        cd.clip_end = 3000
        cam = bpy.data.objects.new(f"cam{self._cam_i}", cd)
        self.cam_coll.objects.link(cam)
        tgt = geo.empty(f"cam{self._cam_i}_target", collection=self.cam_coll)
        con = cam.constraints.new("TRACK_TO")
        con.target = tgt
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        rnd = random.Random(seed or self._cam_i)
        keys = sorted(keys, key=lambda k: k[0])
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        for f in frames:
            u = (f - f0) / max(1, f1 - f0)
            for (ua, ca, ta), (ub, cb, tb) in zip(keys, keys[1:] or keys):
                if ua <= u <= ub or ub == ua:
                    t = ease((u - ua) / (ub - ua)) if ub > ua else 0
                    loc, look = lerp(ca, cb, t), lerp(ta, tb, t)
                    break
            else:
                loc, look = Vector(keys[-1][1]), Vector(keys[-1][2])
            if shake:
                loc = loc + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * shake
            geo.key_loc(cam, f, loc)
            geo.key_loc(tgt, f, look)
        if marker:
            m = self.scene.timeline_markers.new(f"cut{self._cam_i}", frame=f0)
            m.camera = cam
        return cam

    def bump(self, cam, frame, amount=0.08, decay=6):
        """Impulse shake on a camera (ka-chunk, impacts). Uses delta_location."""
        for i, f in enumerate(range(frame, frame + decay)):
            a = amount * (1 - i / decay)
            cam.delta_location = (0, 0, -a if i % 2 == 0 else a * 0.6)
            cam.keyframe_insert("delta_location", frame=f)
        cam.delta_location = (0, 0, 0)
        cam.keyframe_insert("delta_location", frame=frame + decay)
        cam.delta_location = (0, 0, 0)
        cam.keyframe_insert("delta_location", frame=frame - 1)

    def cast(self, s, name, loc, look_at, mood="neutral", idle=True):
        ch = self.chars[name]
        ch.place(loc)
        ch.face_towards(look_at)
        for f in (s["f0"], s["f1"]):
            ch.root.keyframe_insert("location", frame=f)
            ch.root.keyframe_insert("rotation_euler", frame=f)
        ch.expression(s["f0"], mood)
        if idle:
            ch.idle(s["f0"], s["f1"])
        ch.blink([s["f0"] + 20 + k * 70 for k in range((s["f1"] - s["f0"] - 20) // 70 + 1)])
        return ch


# --------------------------------------------------------------------- recipes
def hook_saw(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    A = ctx.trackA
    jy = A.joint_y(7)
    rail_x = RAIL_HALF
    hero = ctx.cast(s, "hero", (rail_x + 0.55, jy - 0.15, RAIL_Z - 0.32), (rail_x, jy - 3, 1.0), mood="angry")
    hero.arm(1, f0, 20, fwd_deg=-70)
    hero.arm(-1, f0, 20, fwd_deg=-60)
    saw = ctx.props["saw"]
    for f in range(f0, f1 + 1, 4):
        k = (f // 4) % 2
        geo.key_loc(saw, f, (rail_x, jy + (0.12 if k else -0.12), RAIL_Z + 0.2))
        geo.key_rot(saw, f, (0, 0, 0))
    geo.key_loc(saw, f1 + 1, (0, 0, -50))  # put it away
    # train far away approaching
    tr = ctx.trainA
    geo.key_loc(tr["root"], f0, (0, jy + 95, 0))
    geo.key_loc(tr["root"], f1, (0, jy + 70, 0))
    ctx.camera(f0, f1, [(0, (rail_x + 0.9, jy - 3.2, 0.9), (rail_x + 0.2, jy + 6, 1.4)),
                        (1, (rail_x + 0.7, jy - 2.2, 0.85), (rail_x + 0.2, jy + 6, 1.4))], lens=24, shake=0.006)


def canyon_flyover(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    ctx.camera(f0, f1, [(0, (-20, -40, 45), (-20, 120, -40)),
                        (1, (-20, 10, 28), (-20, 160, -90))], lens=20)


def station_banner(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    st = ctx.props["station"]
    sx, sy, sz = st["stand"]
    t = ctx.cast(s, "tycoon", (sx, sy, sz), (sx, sy - 10, 1.5), mood="happy")
    mid = (f0 + f1) // 2
    t.arm(1, f0, 15)
    t.arm(1, mid, 130)
    t.arm(-1, f0, 15)
    t.arm(-1, mid, 130)
    ctx.camera(f0, f1, [(0, (sx, sy - 12, sz + 2.5), (sx, sy + 6, sz + 7)),
                        (1, (sx, sy - 6.5, sz + 1.8), (sx, sy + 4, sz + 3.5))], lens=24)


def character_intro(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    y = 60.0
    h = ctx.cast(s, "hero", (0.0, y, RAIL_Z), (1.5, y - 4, 1.3), mood="happy")
    h.arm(1, f0, 10)
    h.arm(1, f0 + 12, 150)
    for k, f in enumerate(range(f0 + 16, f1 - 6, 8)):
        h.arm(1, f, 150 + (15 if k % 2 else -15))
    ctx.camera(f0, f1, [(0, (2.6, y - 3.8, 0.8), (0.0, y, 1.5)),
                        (1, (1.4, y - 2.6, 1.3), (0.0, y, 1.55))], lens=26)


def gap_macro_boss(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    A = ctx.trackA
    jy = A.joint_y(9)
    fx = RAIL_HALF
    boss = ctx.cast(s, "foreman", (fx + 0.15, jy + 1.3, RAIL_Z), (fx, jy, 0.5), mood="neutral")
    boss.rig.rotation_euler = (R(-12), 0, 0)
    fp = word_frame(ctx, s, "purple", 0.85)
    boss.skin(f0, "#fbfbf7")
    boss.skin(fp - 4, "#fbfbf7")
    boss.skin(fp + 6, "#7b3fc4")
    boss.expression(fp - 2, "neutral")
    boss.expression(fp + 4, "angry")
    ctx.camera(f0, f1, [(0.0, (fx + 0.28, jy - 0.45, RAIL_Z + 0.24), (fx, jy, RAIL_Z + 0.15)),
                        (0.45, (fx + 0.35, jy - 0.6, RAIL_Z + 0.3), (fx, jy, RAIL_Z + 0.15)),
                        (0.75, (fx + 0.3, jy - 1.5, 1.4), (fx + 0.15, jy + 1.3, 1.7)),
                        (1.0, (fx + 0.25, jy - 1.0, 1.75), (fx + 0.15, jy + 1.3, 1.85))], lens=30)


def two_shot_argue(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    mood = s["shot"].get("mood", "angry")
    y = 80.0 if mood == "angry" else 100.0
    boss = ctx.cast(s, "foreman", (-0.2, y, RAIL_Z), (1.0, y, 1.4),
                    mood="angry" if mood == "angry" else "smug")
    hero = ctx.cast(s, "hero", (1.15, y + 0.15, RAIL_Z), (-0.2, y, 1.4),
                    mood="neutral" if mood == "angry" else "worried")
    boss.root.rotation_euler.z += R(-25)
    hero.root.rotation_euler.z += R(25)
    for ch in (boss, hero):
        ch.root.keyframe_insert("rotation_euler", frame=f0)
        ch.root.keyframe_insert("rotation_euler", frame=f1)
    if mood == "angry":
        boss.skin(f0, "#7b3fc4")
        boss.skin(f1, "#7b3fc4")
        boss.arm(1, f0, 30)
        boss.arm(1, f0 + 6, 120)
        boss.arm(-1, f0, 30)
        boss.arm(-1, f0 + 6, 120)
        boss.arm(1, f1, 120)
        boss.arm(-1, f1, 120)
        # hero shakes her head on "doesn't"
        fh = word_frame(ctx, s, "doesn", 0.6)
        head = hero.parts["head"]
        for i, f in enumerate(range(fh, min(f1, fh + 30), 5)):
            head.rotation_euler = (0, 0, R(18 if i % 2 else -18))
            head.keyframe_insert("rotation_euler", frame=f)
        head.rotation_euler = (0, 0, 0)
        head.keyframe_insert("rotation_euler", frame=min(f1, fh + 32))
        hero.expression(fh, "smug")
    else:
        boss.skin(f0, "#fbfbf7")
        boss.arm(1, f0, 20, fwd_deg=-30)
    talking = [w for w, q in zip(s["words"], s["quoted"]) if q]
    boss.talk(talking, ctx.fps)
    ctx.camera(f0, f1, [(0, (0.45, y - 3.4, 1.5), (0.45, y, 1.3)),
                        (1, (0.45, y - 2.7, 1.45), (0.45, y, 1.35))], lens=28, shake=0.004)


def rival_lay(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    B = ctx.trackB
    y = 40.0
    rv = ctx.cast(s, "rival", (B.x + 1.9, y + 1.0, 0.0), (B.x, y + 3, 0.5), mood="happy")
    cr = ctx.props["crane"]
    geo.key_loc(cr["root"], f0, (B.x + 4.5, y + 3, 0))
    geo.key_loc(cr["root"], f1, (B.x + 4.5, y + 3, 0))
    geo.key_rot(cr["root"], f0, (0, 0, R(-60)))
    geo.key_rot(cr["root"], f1, (0, 0, R(-80)))
    rail = ctx.props["lay_rail"]
    top = Vector((B.x + RAIL_HALF, y + 6, RAIL_Z + 4))
    geo.key_loc(rail, f0, top)
    geo.key_loc(rail, f0 + int((f1 - f0) * 0.6), (B.x + RAIL_HALF, y + 6, RAIL_Z + 0.02))
    geo.key_loc(rail, f1, (B.x + RAIL_HALF, y + 6, RAIL_Z + 0.02))
    geo.key_loc(rail, f1 + 1, (0, 0, -80))
    # hammering
    for k, f in enumerate(range(f0, f1, 6)):
        rv.arm(1, f, 150 if k % 2 else 60)
    ctx.camera(f0, f1, [(0, (B.x + 4, y - 6, 2.6), (B.x, y + 5, 0.8)),
                        (1, (B.x + 3, y - 3, 1.8), (B.x, y + 6, 0.8))], lens=24)


def coach_interior(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    ci = ctx.props["interior"]
    x, y, z = ci["seat"]
    t = ctx.cast(s, "tycoon", (x, y - 0.1, z - 0.18), (x, y - 5, 1.4), mood="smug", idle=False)
    t.arm(1, f0, 40, fwd_deg=-50)
    t.blink([f0 + 25, f0 + 70])
    ctx.camera(f0, f1, [(0, (x - 0.6, y - 4.5, z + 1.4), (x, y, z + 1.0)),
                        (1, (x - 0.2, y - 3.3, z + 1.3), (x, y, z + 1.1))], lens=24)


def window_rattle(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    tr = ctx.trainA
    ystart, yend = 140.0, 120.0
    geo.key_loc(tr["root"], f0, (0, ystart, 0))
    geo.key_loc(tr["root"], f1, (0, yend, 0))
    win_local = Vector((1.25, 9.5 - 0.75, RAIL_Z + 0.17 + 2.4 - 1.42))  # head pokes out of coach 0 window
    p = ctx.chars["passenger"]
    p.expression(f0, "shocked")
    keep = ("head_", "eye_", "brow_", "mouth_", "glass_", "bowler", "stache_", "char_", "rig_")
    for o in p.all_objects():  # only the head pokes out of the window
        if not o.name.startswith(keep):
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=f0)
    p.place((win_local.x, ystart + win_local.y, win_local.z))
    p.face_towards((5, ystart + win_local.y, 3))
    p.root.keyframe_insert("location", frame=f0)
    p.root.keyframe_insert("rotation_euler", frame=f0)
    p.root.location = (win_local.x, yend + win_local.y, win_local.z)
    p.root.keyframe_insert("location", frame=f1)
    p.root.keyframe_insert("rotation_euler", frame=f1)
    off = Vector((3.2, -0.5, 3.0))
    cam = ctx.camera(f0, f1, [(0, Vector((0, ystart + 9.0, 0)) + off, (1.3, ystart + 8.75, 3.0)),
                              (1, Vector((0, yend + 9.0, 0)) + off, (1.3, yend + 8.75, 3.0))], lens=30, step=1)
    # ka-chunk every ~0.45 s: jolt camera and passenger
    for f in range(f0 + 4, f1 - 4, int(0.45 * ctx.fps)):
        ctx.bump(cam, f, 0.05, 5)
        p.rig.location = (0, 0, 0.0)
        p.rig.keyframe_insert("location", frame=f - 1)
        p.rig.location = (0, 0, 0.12)
        p.rig.keyframe_insert("location", frame=f + 1)
        p.rig.location = (0, 0, 0.0)
        p.rig.keyframe_insert("location", frame=f + 4)


def newspaper(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    st = ctx.props["station"]
    sx, sy, sz = st["stand"]
    p = ctx.cast(s, "passenger", (sx + 1.5, sy - 2, sz), (sx + 1.5, sy - 8, 1.4), mood="smug")
    paper = ctx.props["paper"]
    head = Vector((sx + 1.5, sy - 2 - 0.5, sz + 1.3))
    mid = f0 + int((f1 - f0) * 0.55)
    geo.key_loc(paper, f0, head)
    geo.key_loc(paper, mid, head)
    geo.key_loc(paper, mid + 10, head - Vector((0, 0, 0.75)))
    geo.key_loc(paper, f1, head - Vector((0, 0, 0.75)))
    geo.key_loc(paper, f1 + 1, (0, 0, -60))
    ctx.camera(f0, f1, [(0, (sx + 1.5, sy - 4.2, sz + 1.4), (sx + 1.5, sy - 2, sz + 1.3)),
                        (0.5, (sx + 1.5, sy - 3.6, sz + 1.4), (sx + 1.5, sy - 2, sz + 1.3)),
                        (1, (sx + 2.6, sy - 6.5, sz + 1.6), (sx + 1.2, sy, sz + 1.6))], lens=28)


def calendar_heat(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    y = 100.0
    cal = ctx.props["calendar"]
    h = ctx.cast(s, "hero", (1.2, y - 0.4, RAIL_Z), (1.8, y - 4, 1.3), mood="worried")
    h.arm(1, f0, 20)
    h.arm(1, f0 + 15, 160, fwd_deg=-40)  # wipe forehead
    fill = cal["fill"]
    geo.key_scale(fill, f0, (1, 1, 0.3))
    geo.key_scale(fill, f1, (1, 1, 0.9))
    ctx.sun_energy(f0, 4.2)
    ctx.sun_energy(f1, 5.5)
    ctx.camera(f0, f1, [(0, (2.3, y - 4.4, 1.5), (2.4, y + 0.2, 1.3)),
                        (1, (2.4, y - 3.3, 1.45), (2.4, y + 0.2, 1.3))], lens=26)


def gap_shrink(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    A = ctx.trackA
    jy = A.joint_y(9)
    fx = RAIL_HALF
    fj = word_frame(ctx, s, "june", 0.2)
    fa = word_frame(ctx, s, "august", 0.6)
    fc = word_frame(ctx, s, "coin", 0.8)
    A.key_gap(f0, 0.025)
    A.key_gap(fj + 12, 0.0125)
    A.key_gap(fa, 0.0125)
    A.key_gap(fa + 15, 0.004)
    A.key_heat(f0, 0.15)
    A.key_heat(f1, 0.5)
    coin = ctx.props["coin"]
    geo.key_loc(coin, fc - 1, (fx, jy, RAIL_Z + 0.6))
    geo.key_loc(coin, fc + 10, (fx, jy, RAIL_Z + 0.175))
    geo.key_loc(coin, f1, (fx, jy, RAIL_Z + 0.165))
    geo.key_loc(coin, f1 + 1, (0, 0, -60))
    ctx.camera(f0, f1, [(0, (fx + 0.2, jy - 0.32, RAIL_Z + 0.24), (fx, jy, RAIL_Z + 0.16)),
                        (1, (fx + 0.13, jy - 0.22, RAIL_Z + 0.22), (fx, jy, RAIL_Z + 0.16))], lens=35)


def science_diagram(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    pc = ctx.props["physics"]
    ox, oy, oz = pc["origin"]
    rail = ctx.props["phys_rail"]
    fh = word_frame(ctx, s, "hot", 0.3)
    fs = word_frame(ctx, s, "seven", 0.6)
    geo.key_scale(rail, f0, (1, 1, 1))
    geo.key_scale(rail, fh, (1, 1, 1))
    geo.key_scale(rail, fs + 10, (1, 1.12, 1))
    toon.key_heat(ctx.props["phys_steel"], f0, 0.0)
    toon.key_heat(ctx.props["phys_steel"], fs + 10, 0.9)
    for obj, fpop in ((pc["formula"], f0 + 4), (pc["numbers"], fh + 6), (pc["result"], fs)):
        geo.key_scale(obj, f0, (0.001,) * 3)
        geo.key_scale(obj, fpop, (0.001,) * 3)
        geo.key_scale(obj, fpop + 5, (1.15,) * 3)
        geo.key_scale(obj, fpop + 9, (1, 1, 1))
    ctx.camera(f0, f1, [(0, (ox, oy - 9.5, oz + 3.0), (ox, oy, oz + 3.4)),
                        (1, (ox, oy - 8.5, oz + 3.0), (ox, oy, oz + 3.4))], lens=35)


def rail_glow(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    A, B = ctx.trackA, ctx.trackB
    fcut = word_frame(ctx, s, "seamless", 0.5) - 4
    jy = A.joint_y(9)
    A.key_gap(f0, 0.004)
    A.key_gap(fcut, 0.002)
    A.key_heat(f0, 0.5)
    A.key_heat(fcut, 0.65)
    ctx.camera(f0, fcut - 1, [(0, (RAIL_HALF + 0.5, jy - 1.4, RAIL_Z + 0.5), (RAIL_HALF, jy + 1, RAIL_Z + 0.1)),
                              (1, (RAIL_HALF + 0.35, jy - 0.8, RAIL_Z + 0.35), (RAIL_HALF, jy + 1, RAIL_Z + 0.1))],
               lens=28)
    B.key_heat(f0, 0.2)
    B.key_heat(fcut, 0.35)
    B.key_heat(f1, 0.95)
    # groaning: tiny wobble of the buckle shape before it lets go
    B.key_buckle(fcut, 0.0)
    for i, f in enumerate(range(fcut + 6, f1, 6)):
        B.key_buckle(f, 0.03 * (1 if i % 2 else -0.4) * (1 + i * 0.15))
    B.key_buckle(f1, 0.0)
    ctx.camera(fcut, f1, [(0, (B.x + 0.9, 135, RAIL_Z + 0.45), (B.x + 0.3, 160, RAIL_Z + 0.2)),
                          (1, (B.x + 0.7, 138, RAIL_Z + 0.4), (B.x + 0.3, 160, RAIL_Z + 0.2))], lens=24,
               shake=0.003)


def _trainB_path(ctx, f0, f1, y0, y1):
    tr = ctx.trainB

    def pos(f):
        u = (f - f0) / max(1, f1 - f0)
        y = y0 + (y1 - y0) * u
        return (ctx.trackB.x, y, 0)
    geo.key_loc(tr["root"], f0, pos(f0))
    geo.key_loc(tr["root"], f1, pos(f1))
    return pos


def buckle(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    B = ctx.trackB
    yb = ctx.buckle_y
    fk = word_frame(ctx, s, "sideways", 0.55)
    pos = _trainB_path(ctx, f0, f1, yb + 95, yb + 24)
    ctx.trainB_pos = pos
    B.key_heat(f0, 0.95)
    B.key_buckle(f0, 0.0)
    B.key_buckle(fk - 2, 0.02)
    B.key_buckle(fk + 4, 1.18)
    B.key_buckle(fk + 9, 0.95)
    B.key_buckle(fk + 13, 1.0)
    stack = ctx.trainB["stack_local"]
    ctx.smoke_puffs("smokeB", lambda f: Vector(pos(f)) + stack, f0, f1 + 60)
    cam = ctx.camera(f0, f1, [(0, (B.x + 9, yb - 32, 30), (B.x, yb + 14, 0)),
                              (1, (B.x + 7, yb - 24, 22), (B.x, yb + 8, 0))], lens=24)
    ctx.bump(cam, fk + 2, 0.15, 8)


def impact(ctx, s):
    f0, f1 = s["f0"], s["f1"]
    yb = ctx.buckle_y
    tr = ctx.trainB["root"]
    B = ctx.trackB
    fhit = f0 + 8
    geo.key_loc(tr, f0, (B.x, yb + 24, 0))
    geo.key_loc(tr, fhit, (B.x, yb + 12, 0))
    geo.key_rot(tr, f0, (0, 0, 0))
    geo.key_rot(tr, fhit, (0, 0, 0))
    geo.key_loc(tr, fhit + 12, (B.x + 3.5, yb + 6, -1.5))
    geo.key_rot(tr, fhit + 12, (R(-8), R(35), R(25)))
    geo.key_loc(tr, f1, (B.x + 4.5, yb + 4, -2.5))
    geo.key_rot(tr, f1, (R(-12), R(55), R(32)))
    boom = ctx.props["boom"]
    ctx.smoke_puffs("smokeBoom", lambda f: Vector((B.x + 1, yb + 9, 2.5)), fhit + 4, f1 + 30)
    for i, b in enumerate(boom):
        geo.key_scale(b, fhit + i, (0.001,) * 3)
        geo.key_scale(b, fhit + 6 + i * 2, (2.5 + i * 0.8,) * 3)
        geo.key_scale(b, f1, (4 + i * 1.2,) * 3)
    cam = ctx.camera(f0, f1, [(0, (B.x + 10, yb - 8, 4.0), (B.x, yb + 10, 2.0)),
                              (1, (B.x + 13, yb - 12, 5.0), (B.x, yb + 9, 3.0))], lens=22)
    ctx.bump(cam, fhit, 0.4, 14)


RECIPES = {f.__name__: f for f in (hook_saw, canyon_flyover, station_banner, character_intro, gap_macro_boss,
                                   two_shot_argue, rival_lay, coach_interior, window_rattle, newspaper,
                                   calendar_heat, gap_shrink, science_diagram, rail_glow, buckle, impact)}
