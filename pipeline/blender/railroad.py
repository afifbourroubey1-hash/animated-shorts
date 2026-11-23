"""Railroad builder: ballast, sleepers, I-profile rails, fishplates.

Two flavours:
  * gapped=True  -> rails are separate segments with expansion gaps. The gap
                    width is animated with key_gap(frame, metres).
  * gapped=False -> rails are one continuous mesh (the "perfect" railroad).
                    A "buckle" shape key moves rails+sleepers sideways like a
                    snake; key it with key_buckle(frame, value).

Thermal expansion used in the story:  dL = alpha * L * dT
  11.89 m rail * 0.000012 /°C * 50 °C ≈ 7.1 mm
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import geo
import toon

GAUGE = 1.435
RAIL_HALF = GAUGE / 2 + 0.035
BALLAST_TOP = 0.30
SLEEPER_H = 0.16
RAIL_Z = BALLAST_TOP + SLEEPER_H
SLEEPER_PITCH = 0.65
RAIL_LEN = 11.89  # 39 ft

# I-shaped rail profile (x, z) in metres
PROFILE = [(-0.07, 0), (0.07, 0), (0.07, 0.015), (0.01, 0.03), (0.01, 0.125), (0.036, 0.132),
           (0.036, 0.172), (-0.036, 0.172), (-0.036, 0.132), (-0.01, 0.125), (-0.01, 0.03), (-0.07, 0.015)]


def _extrude_profile(bm, profile, ys, x_off=0.0, z_off=0.0):
    rings = []
    for y in ys:
        rings.append([bm.verts.new((x + x_off, y, z + z_off)) for x, z in profile])
    n = len(profile)
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def rail_mesh(name, length, step=None, x_off=0.0):
    """Rail centred on its origin along Y. `step` = resolution for deformation."""
    bm = bmesh.new()
    n = 1 if step is None else max(1, int(length / step))
    ys = [-length / 2 + length * i / n for i in range(n + 1)]
    _extrude_profile(bm, PROFILE, ys, x_off=x_off)
    return geo.mesh_obj(name, bm)


def ballast_mesh(name, y0, y1):
    bm = bmesh.new()
    prof = [(-1.9, 0), (1.9, 0), (1.25, BALLAST_TOP), (-1.25, BALLAST_TOP)]
    _extrude_profile(bm, prof, [y0, y1])
    return geo.mesh_obj(name, bm)


def sleepers_mesh(name, y0, y1):
    bm = bmesh.new()
    y = y0 + SLEEPER_PITCH / 2
    while y < y1:
        m = Matrix.Translation((0, y, BALLAST_TOP + SLEEPER_H / 2)) @ Matrix.Diagonal((2.6, 0.24, SLEEPER_H, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
        y += SLEEPER_PITCH
    return geo.mesh_obj(name, bm)


class Track:
    def __init__(self, name, x, y0, y1, gapped, collection, gap=0.025):
        self.name, self.x, self.y0, self.y1, self.gapped = name, x, y0, y1, gapped
        self.c = collection
        self.root = geo.empty(f"track_{name}", (x, 0, 0), collection=collection)
        self.steel = toon.hot_steel(f"steel_{name}")
        self.segments: list[bpy.types.Object] = []
        self.gap0 = gap
        b = ballast_mesh(f"ballast_{name}", y0, y1)
        b.data.materials.append(toon.gravel())
        b.parent = self.root
        self._link(b)
        s = sleepers_mesh(f"sleepers_{name}", y0, y1)
        s.data.materials.append(toon.wood("#6e4b30", "#563923", 2))
        s.parent = self.root
        self._link(s)
        self.sleepers = s
        if gapped:
            self._gapped_rails()
        else:
            self._seamless_rails()

    def _link(self, o):
        for col in o.users_collection:
            col.objects.unlink(o)
        self.c.objects.link(o)

    def _gapped_rails(self):
        pitch = RAIL_LEN + self.gap0
        n = int((self.y1 - self.y0) / pitch)
        plate = toon.toon("#3b3f45", 0.2, 0.5)
        for i in range(n):
            cy = self.y0 + (i + 0.5) * pitch
            for side in (-1, 1):
                r = rail_mesh(f"railA_{self.name}_{i}_{side}", RAIL_LEN)
                r.data.materials.append(self.steel)
                r.location = (RAIL_HALF * side, cy, RAIL_Z)
                r.parent = self.root
                self._link(r)
                self.segments.append(r)
                # fishplates + bolts at the joint (start of each segment)
                jy = cy - pitch / 2
                for s2 in (-1, 1):
                    p = geo.box(f"plate_{self.name}_{i}_{side}_{s2}", (0.018, 0.6, 0.09),
                                (RAIL_HALF * side + 0.022 * s2, jy, RAIL_Z + 0.075), mat=plate,
                                parent=self.root, collection=self.c)
                    for k in (-1, 1):
                        geo.cyl(f"bolt_{self.name}_{i}_{side}_{s2}_{k}", 0.014, 0.03,
                                (RAIL_HALF * side + 0.035 * s2, jy + 0.15 * k, RAIL_Z + 0.075),
                                rot=(0, math.radians(90), 0), mat=plate, parent=self.root,
                                collection=self.c, seg=6)
        self.pitch = pitch

    def _seamless_rails(self):
        length = self.y1 - self.y0
        self.rails = []
        for side in (-1, 1):
            r = rail_mesh(f"railB_{self.name}_{side}", length, step=0.5, x_off=RAIL_HALF * side)
            r.data.materials.append(self.steel)
            r.location = (0, (self.y0 + self.y1) / 2, RAIL_Z)
            r.parent = self.root
            self._link(r)
            self.rails.append(r)

    # ------------------------------------------------------------ animation
    def key_gap(self, frame: int, gap: float):
        """Visible gap width (m) between segments; segments grow around their centre."""
        for r in self.segments:
            r.scale = (1, (self.pitch - gap) / RAIL_LEN, 1)
            r.keyframe_insert("scale", frame=frame)

    def key_heat(self, frame: int, heat: float):
        toon.key_heat(self.steel, frame, heat)

    def add_buckle(self, y_center: float, amp=1.6, wavelength=22.0, width=9.0):
        """Snake-like lateral kink as a shape key on rails and sleepers."""
        def offset(y_world):
            u = (y_world - y_center)
            win = math.exp(-(u / width) ** 2)
            return amp * win * math.sin(2 * math.pi * u / wavelength + 0.6)

        self.buckle_objs = []
        for o in [*self.rails, self.sleepers]:
            o.shape_key_add(name="Basis")
            k = o.shape_key_add(name="buckle")
            oy = o.matrix_world.translation.y if o.parent is None else (o.location.y + o.parent.location.y)
            for v, kv in zip(o.data.vertices, k.data):
                yw = v.co.y + oy
                d = offset(yw)
                kv.co = v.co + Vector((d, 0, 0.12 * abs(d) / amp))
            self.buckle_objs.append(k)

    def key_buckle(self, frame: int, value: float):
        for k in self.buckle_objs:
            k.value = value
            k.keyframe_insert("value", frame=frame)

    def rail_top(self, y: float, side: int = 1) -> Vector:
        return Vector((self.x + RAIL_HALF * side, y, RAIL_Z + 0.172))

    def joint_y(self, index: int) -> float:
        return self.y0 + index * self.pitch
