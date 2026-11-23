"""Build the whole episode in Blender from episode.json + words.json and render it.

Run with Blender (recommended, uses your GPU):
    blender -b -P pipeline/blender/build_episode.py -- rail_gaps --final
or with the pip `bpy` module (CPU, headless servers):
    python pipeline/blender/build_episode.py rail_gaps --preview

Options:
    --preview          360x640, few samples (fast check of timing/cameras)
    --final            1080x1920, production quality
    --engine E         CYCLES (default) | EEVEE
    --samples N        override render samples
    --frames A-B       render only a frame range (e.g. 0-120)
    --shot ID          render only one shot (e.g. s05_gap)
    --step N           render every Nth frame (animatic)
    --stills           render one still per shot into output/<id>/stills/
    --no-render        only build and save output/<id>/scene.blend
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import characters  # noqa: E402
import geo  # noqa: E402
import props  # noqa: E402
import railroad  # noqa: E402
import shots  # noqa: E402
import toon  # noqa: E402
import train  # noqa: E402
import world  # noqa: E402
from common import load_episode, load_words, out_dir, quoted_flags, shot_timings  # noqa: E402


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    q = ap.add_mutually_exclusive_group()
    q.add_argument("--preview", action="store_true")
    q.add_argument("--final", action="store_true")
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--samples", type=int)
    ap.add_argument("--frames")
    ap.add_argument("--shot")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--stills", action="store_true", help="render the middle frame of every shot (contact sheet)")
    return ap.parse_args(argv)


def setup_scene(ep, args, end_frame):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = "LINEAR"
    sc = bpy.context.scene
    sc.render.fps = ep["fps"]
    res = ep["resolution"]["final" if args.final else "preview"]
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.frame_start, sc.frame_end = 0, end_frame
    sc.view_settings.view_transform = "Standard"   # saturated cartoon colours (AgX desaturates)
    sc.view_settings.look = "None"
    sc.render.film_transparent = False
    if args.engine.upper().startswith("EEVEE"):
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = args.samples or (16 if args.preview else 64)
    else:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "GPU" if args.final else "CPU"
        sc.cycles.samples = args.samples or (12 if args.preview else 96)
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 4
        sc.cycles.transparent_max_bounces = 16
        sc.cycles.use_adaptive_sampling = True
    sc.render.use_persistent_data = True  # keep BVH/shaders between frames (big speed-up)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    return sc


def all_fcurves():
    """Every F-curve in the file (Blender 4.4+ layered actions and older flat actions)."""
    for act in bpy.data.actions:
        if hasattr(act, "layers") and act.layers:
            for layer in act.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        yield from cb.fcurves
        elif hasattr(act, "fcurves"):
            yield from act.fcurves


def force_linear():
    """Shots are cut back-to-back; Bezier keys would overshoot between them.
    Easing is baked into the sampled keys instead (see shots.ease)."""
    n = 0
    for fc in all_fcurves():
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
            n += 1
    return n


def main():
    args = parse_args()
    ep = load_episode(args.episode)
    fps = ep["fps"]
    words = load_words(args.episode)
    timing = shot_timings(ep, words)
    end_frame = round(timing[-1]["end"] * fps)
    sc = setup_scene(ep, args, end_frame)
    t0 = time.time()

    ctx = shots.Ctx(sc, fps)
    w = world.build(sc)
    ctx.sun = w["sun"]

    def sun_energy(frame, e):
        ctx.sun.data.energy = e
        ctx.sun.data.keyframe_insert("energy", frame=frame)
    ctx.sun_energy = sun_energy

    rc = geo.coll("railroads")
    ctx.trackA = railroad.Track("A", world.LINE_A_X, world.Y0, world.Y1, gapped=True, collection=rc)
    ctx.trackB = railroad.Track("B", world.LINE_B_X, world.Y0, world.Y1, gapped=False, collection=rc)
    ctx.buckle_y = 150.0
    ctx.trackB.add_buckle(ctx.buckle_y)

    cc = geo.coll("characters")
    for name, spec in ep["characters"].items():
        ctx.chars[name] = characters.Character(name, spec, cc)
        ctx.chars[name].place((0, -500 - 5 * len(ctx.chars), 0))  # parking spot

    tc = geo.coll("trains")
    ctx.trainA = train.build_train("A", tc, coaches=2, body="#1d5c3a", coach_col="#7a1e1e")
    ctx.trainB = train.build_train("B", tc, coaches=3, body="#1a1a2e", trim="#d4af37", coach_col="#14213d")
    ctx.trainA["root"].location = (world.LINE_A_X, 400, 0)
    ctx.trainB["root"].location = (world.LINE_B_X, 400, 0)

    pc = geo.coll("props")
    ctx.props = {
        "station": props.station(pc),
        "interior": props.coach_interior(pc),
        "calendar": props.calendar_board(pc, (3.0, 100.6, 0.0)),
        "paper": props.newspaper(pc),
        "coin": props.coin(pc),
        "saw": props.saw(pc),
        "crane": props.crane(pc, (world.LINE_B_X + 4.5, 43, 0)),
        "physics": props.physics_card(pc),
    }
    lay = railroad.rail_mesh("lay_rail", railroad.RAIL_LEN)
    lay.data.materials.append(toon.toon("#9aa3ad", 0.3, 0.3))
    lay.location = (0, 0, -80)
    ctx.props["lay_rail"] = lay
    ox, oy, oz = ctx.props["physics"]["origin"]
    phys_steel = toon.hot_steel("steel_phys")
    pr = railroad.rail_mesh("phys_rail", 4.0)
    pr.data.materials.append(phys_steel)
    pr.location = (ox, oy - 1, oz + 1.2)
    pr.rotation_euler = (0, 0, math.radians(90))
    pr.scale = (1, 1, 1)
    ctx.props["phys_rail"], ctx.props["phys_steel"] = pr, phys_steel
    boom = []
    for i, col in enumerate(("#fff3b0", "#ffb020", "#ff5a1f")):
        b = geo.ico(f"boom{i}", 1.0, (ctx.trackB.x + i * 0.8, ctx.buckle_y + 10 - i, 2 + i * 0.6),
                    mat=toon.emission(col, 6 - i * 1.3), collection=pc, subdiv=2)
        b.scale = (0.001,) * 3
        boom.append(b)
    ctx.props["boom"] = boom

    def smoke_puffs(name, fn, f0, f1):
        return train.smoke(name, pc, fn, f0, f1)
    ctx.smoke_puffs = smoke_puffs

    # initial story state
    ctx.trackA.key_gap(0, 0.025)
    ctx.trackA.key_heat(0, 0.0)
    ctx.trackB.key_heat(0, 0.0)
    ctx.trackB.key_buckle(0, 0.0)
    sun_energy(0, 4.2)
    for m in ctx.props["calendar"]["months"]:
        m.hide_render = True

    # --------------------------------------------------------------- shots
    for t in timing:
        s = {"f0": round(t["start"] * fps), "f1": max(round(t["start"] * fps) + 1, round(t["end"] * fps) - 1),
             "words": t["words"], "shot": t["shot"],
             "quoted": quoted_flags(t["shot"]["text"])}
        # cast visibility first (recipes may override it, e.g. hide a body)
        cast = set(t["shot"].get("cast", []))
        for name, ch in ctx.chars.items():
            hide = name not in cast
            for o in ch.all_objects():
                o.hide_render = hide
                o.keyframe_insert("hide_render", frame=s["f0"])
        recipe = shots.RECIPES[t["shot"]["type"]]
        recipe(ctx, s)
        t["f0"], t["f1"] = s["f0"], s["f1"]
        if t["shot"]["type"] == "calendar_heat":
            months = ctx.props["calendar"]["months"]
            for i, m in enumerate(months):
                m.hide_render = i != 0
                m.keyframe_insert("hide_render", frame=0)
            months[0].hide_render = True
            months[0].keyframe_insert("hide_render", frame=s["f1"] - 15)
            months[2].hide_render = False
            months[2].keyframe_insert("hide_render", frame=s["f1"] - 15)

    n_keys = force_linear()
    d = out_dir(args.episode)
    print(f"{n_keys} keyframes set to LINEAR")
    print(f"built scene in {time.time() - t0:.1f}s, {len(bpy.data.objects)} objects, frames 0-{end_frame}")
    bpy.ops.wm.save_as_mainfile(filepath=str(d / "scene.blend"))
    if args.no_render:
        return

    if args.stills:
        sd = d / "stills"
        sd.mkdir(exist_ok=True)
        for t in timing:
            sc.frame_set((t["f0"] + t["f1"]) // 2)
            sc.render.filepath = str(sd / f"{t['id']}.png")
            bpy.ops.render.render(write_still=True)
        print(f"stills -> {sd}")
        return

    a, b = 0, end_frame
    if args.shot:
        t = next(t for t in timing if t["id"] == args.shot)
        a, b = t["f0"], t["f1"]
    if args.frames:
        a, b = (int(x) for x in args.frames.split("-"))
    frames_dir = d / "frames"
    frames_dir.mkdir(exist_ok=True)
    t1 = time.time()
    for f in range(a, b + 1, args.step):
        sc.frame_set(f)
        sc.render.filepath = str(frames_dir / f"{f:05d}.png")
        bpy.ops.render.render(write_still=True)
        if f % 30 == 0:
            el = time.time() - t1
            done = (f - a) // args.step + 1
            print(f"frame {f}/{b}  {el / done:.2f}s/frame", flush=True)
    print(f"rendered {a}-{b} in {time.time() - t1:.0f}s -> {frames_dir}")


if __name__ == "__main__":
    main()
