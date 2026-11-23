"""Steam locomotive + coaches built from primitives, and keyframed smoke puffs.

The train's nose points to -Y. Move the root empty along Y (key_loc).
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

import geo
import toon
from railroad import RAIL_Z


def build_train(name, collection, coaches=2, body="#1d5c3a", trim="#c9a227", coach_col="#7a1e1e"):
    root = geo.empty(f"train_{name}", collection=collection)
    c = collection
    z = RAIL_Z + 0.17
    # chassis
    geo.box(f"{name}_frame", (2.2, 9.0, 0.3), (0, 2.5, z + 0.55), mat="#1a1a1a", parent=root, collection=c)
    # boiler + smokebox
    boiler = geo.cyl(f"{name}_boiler", 0.95, 5.2, (0, 1.4, z + 1.75), rot=(math.radians(90), 0, 0), mat=body,
                     parent=root, collection=c, seg=32)
    toon.add_outline(boiler, 0.04)
    geo.cyl(f"{name}_smokebox", 1.0, 1.0, (0, -1.6, z + 1.75), rot=(math.radians(90), 0, 0), mat="#222222",
            parent=root, collection=c, seg=32)
    for i, y in enumerate((-0.6, 1.0, 2.6)):
        geo.cyl(f"{name}_band{i}", 0.97, 0.12, (0, y, z + 1.75), rot=(math.radians(90), 0, 0), mat=trim,
                parent=root, collection=c, seg=32)
    stack = geo.cyl(f"{name}_stack", 0.32, 1.2, (0, -1.3, z + 3.1), mat="#1a1a1a", parent=root, collection=c,
                    radius2=0.5, seg=20)
    geo.sphere(f"{name}_dome", 0.45, (0, 0.8, z + 2.7), mat=trim, parent=root, collection=c, scale=(1, 1, 0.8))
    lamp = geo.cyl(f"{name}_lamp", 0.3, 0.4, (0, -2.0, z + 2.8), rot=(math.radians(90), 0, 0), mat="#222222",
                   parent=root, collection=c, seg=16)
    geo.cyl(f"{name}_lamp_glass", 0.24, 0.05, (0, -2.22, z + 2.8), rot=(math.radians(90), 0, 0),
            mat=toon.emission("#fff1b0", 12), parent=root, collection=c, seg=16)
    # cab
    cab = geo.box(f"{name}_cab", (2.3, 2.4, 2.4), (0, 5.0, z + 2.1), mat=body, parent=root, collection=c)
    toon.add_outline(cab, 0.04)
    geo.box(f"{name}_roof", (2.6, 2.8, 0.15), (0, 5.0, z + 3.35), mat="#1a1a1a", parent=root, collection=c)
    # cow catcher
    geo.box(f"{name}_catcher", (2.0, 0.9, 0.6), (0, -2.6, z + 0.35), rot=(math.radians(-35), 0, 0), mat="#8b1a1a",
            parent=root, collection=c)
    # wheels
    for i, y in enumerate((-0.4, 1.6, 3.6)):
        for side in (-1, 1):
            geo.cyl(f"{name}_wheel{i}{side}", 0.62, 0.15, (0.72 * side, y, z + 0.62), rot=(0, math.radians(90), 0),
                    mat="#b3261e", parent=root, collection=c, seg=24)
    # coaches
    for k in range(coaches):
        y = 9.5 + k * 11
        car = geo.box(f"{name}_coach{k}", (2.6, 10, 2.8), (0, y, z + 2.0), mat=coach_col, parent=root, collection=c)
        toon.add_outline(car, 0.04)
        geo.box(f"{name}_coachroof{k}", (2.8, 10.2, 0.2), (0, y, z + 3.5), mat="#2a2a2a", parent=root, collection=c)
        for w in range(6):
            for side in (-1, 1):
                geo.box(f"{name}_win{k}_{w}{side}", (0.02, 0.9, 0.9), (1.31 * side, y - 3.75 + w * 1.5, z + 2.4),
                        mat=toon.emission("#ffe7a3", 2.5), parent=root, collection=c)
        for side in (-1, 1):
            for wy in (-3.5, 3.5):
                geo.cyl(f"{name}_cw{k}{side}{wy}", 0.45, 0.12, (0.72 * side, y + wy, z + 0.45),
                        rot=(0, math.radians(90), 0), mat="#222222", parent=root, collection=c, seg=16)
    return {"root": root, "stack_local": Vector((0, -1.3, z + 3.8))}


def smoke(name, collection, path_fn, f0: int, f1: int, every: int = 3, life: int = 40, seed: int = 1,
          color="#4b3b33"):
    """Keyframed smoke puffs. path_fn(frame) -> world position of the chimney top."""
    rnd = random.Random(seed)
    mat = toon.toon(color, flat=0.35)
    puffs = []
    for i, f in enumerate(range(f0 - life, f1, every)):
        p = geo.sphere(f"{name}_puff{i}", 1.0, (0, 0, 0), mat=mat, collection=collection, seg=12)
        start = Vector(path_fn(f))
        drift = Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(1.0, 2.0), rnd.uniform(5, 8)))
        for fk, frac in ((f - 1, None), (f, 0.0), (f + life // 2, 0.5), (f + life, 1.0)):
            if frac is None:
                p.scale = (0.001,) * 3
                p.location = start
            else:
                p.location = start + drift * frac
                s = 0.6 + 2.2 * frac if frac < 1 else 0.001
                p.scale = (s, s, s * 0.85)
            p.keyframe_insert("location", frame=fk)
            p.keyframe_insert("scale", frame=fk)
        puffs.append(p)
    return puffs
