"""Cartoon characters: big white round head, tiny bean body, black stick limbs.

Every character is a hierarchy:
    char_<name>            (root empty at the feet — move/rotate this)
      └ rig_<name>         (bob/lean empty, animated by idle())
          ├ body, collar, buttons
          ├ head_<name>    (sphere with animated colour material)
          │   ├ eyes, brows, mouth, hair, hat ...
          ├ arm pivots (shoulders) -> arm + hand
          └ legs + feet

Faces are built on the head's -Y side, so a character "looks" down -Y.
Use face_towards() to turn them toward the camera or another character.
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

import geo
import toon

HEAD_R = 0.34
HEAD_Z = 1.42
BLACK = "#111111"


class Character:
    def __init__(self, name: str, spec: dict, collection):
        self.name = name
        self.spec = spec
        self.c = collection
        self.root = geo.empty(f"char_{name}", collection=collection)
        self.rig = geo.empty(f"rig_{name}", parent=self.root, collection=collection)
        self.head_mat = toon.animated_toon(f"skin_{name}", "#ffffff", flat=0.8)
        self.parts: dict[str, bpy.types.Object] = {}
        self._build()

    # ------------------------------------------------------------------ build
    def _p(self, key, obj, outline=0.0):
        self.parts[key] = obj
        if outline:
            toon.add_outline(obj, outline)
        return obj

    def _build(self):
        s, c, rig = self.spec, self.c, self.rig
        body_col = s.get("body", "#1f9e89")
        accent = s.get("accent", "#c0392b")
        # legs + feet
        for side in (-1, 1):
            self._p(f"leg{side}", geo.cyl(f"leg_{self.name}{side}", 0.022, 0.62, (0.09 * side, 0, 0.33),
                                         mat=BLACK, parent=rig, collection=c, seg=8))
            self._p(f"foot{side}", geo.sphere(f"foot_{self.name}{side}", 0.06, (0.09 * side, -0.04, 0.03),
                                             mat=BLACK, parent=rig, collection=c, scale=(1, 1.5, 0.6), seg=12))
        # bean body
        body = geo.sphere(f"body_{self.name}", 0.3, (0, 0, 0.88), mat=body_col, parent=rig,
                          collection=c, scale=(0.95, 0.75, 1.15))
        self._p("body", body, 0.018)
        self._p("collar", geo.sphere(f"collar_{self.name}", 0.09, (0, -0.19, 1.16), mat=accent,
                                     parent=rig, collection=c, scale=(1.2, 0.5, 0.6), seg=16))
        for i in range(3):
            geo.sphere(f"btn_{self.name}{i}", 0.022, (0, -0.225, 0.98 - i * 0.12), mat="#f2d16b",
                       parent=rig, collection=c, seg=10)
        # arms (pivot at shoulder so we can rotate for gestures)
        for side in (-1, 1):
            piv = geo.empty(f"shoulder_{self.name}{side}", (0.27 * side, 0, 1.05), parent=rig, collection=c)
            arm = geo.cyl(f"arm_{self.name}{side}", 0.02, 0.5, (0, 0, -0.25), mat=BLACK, parent=piv,
                          collection=c, seg=8)
            geo.sphere(f"hand_{self.name}{side}", 0.045, (0, 0, -0.5), mat=BLACK, parent=piv, collection=c, seg=12)
            piv.rotation_euler = (0, math.radians(-12 * side), 0)
            self.parts[f"shoulder{side}"] = piv
            self.parts[f"arm{side}"] = arm
        # head
        head = geo.sphere(f"head_{self.name}", HEAD_R, (0, 0, HEAD_Z), mat=None, parent=rig, collection=c)
        head.data.materials.append(self.head_mat)
        self._p("head", head, 0.022)
        fz = 0  # face features are children of the head (local coords)
        y = -HEAD_R * 0.93
        for side in (-1, 1):
            eye = geo.sphere(f"eye_{self.name}{side}", 0.035, (0.11 * side, y, 0.04 + fz), mat=BLACK,
                             parent=head, collection=c, scale=(1, 0.5, 1.5), seg=12)
            self.parts[f"eye{side}"] = eye
            brow = geo.box(f"brow_{self.name}{side}", (0.11, 0.03, 0.025), (0.11 * side, y - 0.01, 0.15),
                           mat=BLACK, parent=head, collection=c)
            self.parts[f"brow{side}"] = brow
        mouth = geo.sphere(f"mouth_{self.name}", 0.07, (0, y + 0.02, -0.13), mat="#3a0d0d", parent=head,
                           collection=c, scale=(1.0, 0.35, 0.18), seg=16)
        self.parts["mouth"] = mouth
        if s.get("mustache"):
            for side in (-1, 1):
                geo.sphere(f"stache_{self.name}{side}", 0.06, (0.055 * side, y - 0.01, -0.07), mat="#3b2a1a",
                           parent=head, collection=c, scale=(1.3, 0.5, 0.45), seg=12)
        if s.get("glasses"):
            for side in (-1, 1):
                geo.torus(f"glass_{self.name}{side}", 0.06, 0.008, (0.11 * side, y - 0.02, 0.04),
                          rot=(math.radians(90), 0, 0), mat=BLACK, parent=head, collection=c)
        if s.get("hair"):
            for side in (-1, 1):
                geo.sphere(f"hair_{self.name}{side}", 0.16, (0.26 * side, 0.06, 0.02), mat=s["hair"],
                           parent=head, collection=c, scale=(0.45, 0.9, 1.0), seg=16)
            if s.get("bun"):
                self._p("bun", geo.sphere(f"bun_{self.name}", 0.1, (0, 0.3, 0.12), mat=s["hair"], parent=head,
                                          collection=c, seg=16), 0.012)
        self._hat(s.get("hat"), head)

    def _hat(self, kind, head):
        c, n = self.c, self.name
        if kind == "striped_cap":
            crown = geo.sphere(f"cap_{n}", 0.36, (0, 0.02, 0.17), mat=toon.stripes("#2d3e8c", "#e8ecf5", 18),
                               parent=head, collection=c, scale=(1.05, 1.08, 0.55))
            self._p("hat", crown, 0.018)
            self._p("brim", geo.sphere(f"capbrim_{n}", 0.2, (0, -0.32, 0.17), mat="#2d3e8c", parent=head,
                                       collection=c, scale=(1.0, 0.8, 0.12), seg=16), 0.012)
        elif kind == "bowler":
            dome = geo.sphere(f"bowler_{n}", 0.28, (0, 0, 0.3), mat="#1c1c1c", parent=head, collection=c,
                              scale=(1, 1, 0.75))
            self._p("hat", dome, 0.015)
            brim = geo.cyl(f"bowlerbrim_{n}", 0.4, 0.03, (0, 0, 0.24), mat="#1c1c1c", parent=head, collection=c,
                           seg=32)
            self._p("brim", brim, 0.012)
        elif kind == "top_hat":
            self._p("hat", geo.cyl(f"tophat_{n}", 0.22, 0.42, (0, 0, 0.5), mat="#151515", parent=head,
                                   collection=c, seg=32), 0.015)
            geo.cyl(f"tophatband_{n}", 0.225, 0.07, (0, 0, 0.34), mat="#8b1a1a", parent=head, collection=c, seg=32)
            self._p("brim", geo.cyl(f"tophatbrim_{n}", 0.38, 0.03, (0, 0, 0.29), mat="#151515", parent=head,
                                    collection=c, seg=32), 0.012)
        elif kind == "conductor":
            self._p("hat", geo.cyl(f"cond_{n}", 0.3, 0.2, (0, 0, 0.32), mat="#22305e", parent=head, collection=c,
                                   seg=32, radius2=0.34), 0.015)
            geo.cyl(f"condband_{n}", 0.305, 0.04, (0, 0, 0.25), mat="#f1c40f", parent=head, collection=c, seg=32)
            self._p("brim", geo.sphere(f"condbrim_{n}", 0.18, (0, -0.3, 0.24), mat="#111111", parent=head,
                                       collection=c, scale=(1, 0.8, 0.1), seg=16), 0.01)

    # -------------------------------------------------------------- animation
    def place(self, loc, face_to=None, frame=None):
        self.root.location = loc
        if face_to is not None:
            self.face_towards(face_to)
        if frame is not None:
            self.root.keyframe_insert("location", frame=frame)
            self.root.keyframe_insert("rotation_euler", frame=frame)

    def face_towards(self, target, frame=None):
        d = Vector(target) - Vector(self.root.location)
        # face is on -Y; rotate so -Y points at target
        self.root.rotation_euler = (0, 0, math.atan2(d.x, -d.y))
        if frame is not None:
            self.root.keyframe_insert("rotation_euler", frame=frame)

    def idle(self, f0: int, f1: int, amp=0.025, speed=0.18, seed=0):
        """Gentle bob + sway, keyed every 3 frames (no drivers needed)."""
        rnd = random.Random(seed or hash(self.name) & 0xFFFF)
        ph = rnd.random() * 6.28
        for f in range(f0, f1 + 1, 3):
            t = f * speed + ph
            self.rig.location = (0, 0, abs(math.sin(t)) * amp)
            self.rig.rotation_euler = (math.sin(t * 0.5) * 0.03, math.sin(t * 0.7) * 0.04, 0)
            self.rig.keyframe_insert("location", frame=f)
            self.rig.keyframe_insert("rotation_euler", frame=f)

    def expression(self, frame: int, mood: str = "neutral"):
        """Key brows/eyes/mouth for a mood at `frame`."""
        brow_rot = {"neutral": 0, "angry": 22, "smug": -10, "happy": -15, "shocked": -25, "worried": -20}[mood]
        brow_z = {"neutral": 0.15, "angry": 0.12, "smug": 0.16, "happy": 0.17, "shocked": 0.2, "worried": 0.17}[mood]
        eye_s = {"neutral": 1.5, "angry": 1.0, "smug": 0.7, "happy": 1.2, "shocked": 2.2, "worried": 1.6}[mood]
        mouth_w = {"neutral": 1.0, "angry": 1.4, "smug": 1.3, "happy": 1.6, "shocked": 0.8, "worried": 0.8}[mood]
        for side in (-1, 1):
            b = self.parts[f"brow{side}"]
            r = brow_rot if mood != "smug" or side == 1 else 4
            b.rotation_euler = (0, math.radians(r * side), 0)
            b.location.z = brow_z
            b.keyframe_insert("rotation_euler", frame=frame)
            b.keyframe_insert("location", frame=frame)
            e = self.parts[f"eye{side}"]
            e.scale = (1, 0.5, eye_s)
            e.keyframe_insert("scale", frame=frame)
        m = self.parts["mouth"]
        m.scale = (mouth_w, 0.35, m.scale.z)
        m.keyframe_insert("scale", frame=frame)

    def talk(self, words: list[dict], fps: int, open_amt=0.9):
        """Lip-flap: open on each word start, close at its end (fast, readable at 30fps)."""
        m = self.parts["mouth"]
        base = (m.scale.x, m.scale.y)
        for w in words:
            a, b = round(w["start"] * fps), round(w["end"] * fps)
            m.scale = (*base, 0.18)
            m.keyframe_insert("scale", frame=max(0, a - 1))
            m.scale = (*base, open_amt)
            m.keyframe_insert("scale", frame=a + 1)
            m.scale = (*base, 0.18)
            m.keyframe_insert("scale", frame=max(a + 2, b))

    def blink(self, frames: list[int]):
        for f in frames:
            for side in (-1, 1):
                e = self.parts[f"eye{side}"]
                z = e.scale.z
                e.keyframe_insert("scale", frame=f - 1)
                e.scale = (1, 0.5, 0.15)
                e.keyframe_insert("scale", frame=f + 1)
                e.scale = (1, 0.5, z)
                e.keyframe_insert("scale", frame=f + 3)

    def skin(self, frame: int, color: str):
        toon.key_color(self.head_mat, frame, color)

    def arm(self, side: int, frame: int, angle_deg: float, fwd_deg: float = 0):
        """Raise an arm: angle 0 = hanging, 90 = horizontal sideways, fwd = forward swing."""
        p = self.parts[f"shoulder{side}"]
        p.rotation_euler = (math.radians(fwd_deg), math.radians(-angle_deg * side), 0)
        p.keyframe_insert("rotation_euler", frame=frame)

    def all_objects(self):
        return [self.root, *self.root.children_recursive]
