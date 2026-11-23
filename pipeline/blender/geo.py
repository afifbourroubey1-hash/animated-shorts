"""Tiny primitive helpers so scene code reads like a description, not like bpy.ops noise."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from toon import toon


def coll(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def _finish(obj, mat, parent, collection, smooth):
    if mat is not None:
        obj.data.materials.append(mat if not isinstance(mat, str) else toon(mat))
    if parent is not None:
        obj.parent = parent
    if collection is not None:
        for c in obj.users_collection:
            c.objects.unlink(obj)
        collection.objects.link(obj)
    if smooth and obj.type == "MESH":
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def mesh_obj(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def box(name, size=(1, 1, 1), loc=(0, 0, 0), mat=None, parent=None, collection=None, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    o = mesh_obj(name, bm)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, parent, collection, False)


def sphere(name, radius=0.5, loc=(0, 0, 0), mat=None, parent=None, collection=None, scale=(1, 1, 1), seg=32):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=radius)
    o = mesh_obj(name, bm)
    o.location = loc
    o.scale = scale
    return _finish(o, mat, parent, collection, True)


def ico(name, radius=0.5, loc=(0, 0, 0), mat=None, parent=None, collection=None, subdiv=1):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    o = mesh_obj(name, bm)
    o.location = loc
    return _finish(o, mat, parent, collection, False)


def cyl(name, radius=0.5, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, parent=None,
        collection=None, seg=24, radius2=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radius,
                          radius2=radius if radius2 is None else radius2, depth=depth)
    o = mesh_obj(name, bm)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, parent, collection, smooth)


def torus(name, major=0.5, minor=0.1, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, parent=None, collection=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    M, m_ = 32, 12
    verts = []
    for i in range(M):
        a = 2 * math.pi * i / M
        ring = []
        for j in range(m_):
            b = 2 * math.pi * j / m_
            r = major + minor * math.cos(b)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), minor * math.sin(b))))
        verts.append(ring)
    for i in range(M):
        for j in range(m_):
            bm.faces.new((verts[i][j], verts[(i + 1) % M][j], verts[(i + 1) % M][(j + 1) % m_],
                          verts[i][(j + 1) % m_]))
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, parent, collection, True)


def plane(name, size=(1, 1), loc=(0, 0, 0), rot=(0, 0, 0), mat=None, parent=None, collection=None, cuts=0):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=max(1, cuts), y_segments=max(1, cuts), size=0.5)
    bmesh.ops.scale(bm, vec=Vector((size[0], size[1], 1)), verts=bm.verts)
    o = mesh_obj(name, bm)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, parent, collection, False)


def grid(name, size, segs, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=segs[0], y_segments=segs[1], size=0.5)
    bmesh.ops.scale(bm, vec=Vector((size[0], size[1], 1)), verts=bm.verts)
    o = mesh_obj(name, bm)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, None, collection, True)


_font = None


def font():
    global _font
    if _font is None:
        for p in ("assets/fonts/Montserrat-Black.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                import os
                from common import ROOT  # type: ignore
                full = p if os.path.isabs(p) else str(ROOT / p)
                if os.path.exists(full):
                    _font = bpy.data.fonts.load(full)
                    break
            except Exception:
                continue
    return _font


def text(name, body, size=1.0, loc=(0, 0, 0), rot=(math.radians(90), 0, 0), mat="#111111",
         parent=None, collection=None, extrude=0.02, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    f = font()
    if f:
        cu.font = f
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return _finish(o, mat, parent, collection, False)


def empty(name, loc=(0, 0, 0), parent=None, collection=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if parent:
        o.parent = parent
    if collection:
        for c in o.users_collection:
            c.objects.unlink(o)
        collection.objects.link(o)
    return o


def move_tree_to(root: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for o in [root, *root.children_recursive]:
        for c in o.users_collection:
            c.objects.unlink(o)
        collection.objects.link(o)


def key_loc(obj, frame, loc):
    obj.location = loc
    obj.keyframe_insert("location", frame=frame)


def key_rot(obj, frame, rot):
    obj.rotation_euler = rot
    obj.keyframe_insert("rotation_euler", frame=frame)


def key_scale(obj, frame, s):
    obj.scale = s
    obj.keyframe_insert("scale", frame=frame)


def set_visible_range(obj_or_coll_objs, f0: int, f1: int) -> None:
    """Show objects only between f0 and f1 (inclusive)."""
    objs = obj_or_coll_objs if isinstance(obj_or_coll_objs, (list, tuple)) else [obj_or_coll_objs]
    for o in objs:
        for f, hide in ((0, True), (f0, False), (f1 + 1, True)):
            if f < 0:
                continue
            o.hide_render = hide
            o.hide_viewport = hide
            o.keyframe_insert("hide_render", frame=f)
            o.keyframe_insert("hide_viewport", frame=f)
