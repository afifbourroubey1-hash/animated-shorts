"""Sky, sun, canyon walls, ledges and the blue abyss.

Layout (metres, +Y = along the canyon):
    x = +9  ........ right canyon wall (rises above line A)
    x = 0   ........ LINE A  (hero's railroad, with expansion gaps) on a ledge
    x = -5  ........ cliff edge -> drop into the abyss
    x = -35 ........ cliff edge of the opposite ledge
    x = -40 ........ LINE B  (rival's "perfect" seamless railroad)
    x = -47 ........ left canyon wall
    z = -160 ....... abyss floor (blue haze)
"""
from __future__ import annotations

import math
import random

import bpy

import geo
import toon

LINE_A_X = 0.0
LINE_B_X = -40.0
Y0, Y1 = -60.0, 260.0


def sky(scene):
    w = bpy.data.worlds.new("sky")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = toon.hex_rgba("#bfe3ff")
    cr.elements[1].position = 0.55
    cr.elements[1].color = toon.hex_rgba("#1f5fd6")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 4.2
    sun_data.angle = math.radians(4)
    sun_data.color = (1.0, 0.93, 0.82)
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48), math.radians(12), math.radians(-35))
    return sun


def clouds(collection, seed=3):
    rnd = random.Random(seed)
    mat = toon.toon("#ffffff", flat=0.8)
    for i in range(14):
        x = rnd.uniform(-250, 250)
        y = rnd.uniform(150, 500)
        z = rnd.uniform(70, 140)
        for k in range(4):
            geo.sphere(f"cloud{i}_{k}", rnd.uniform(8, 16), (x + k * 9 + rnd.uniform(-3, 3), y, z + rnd.uniform(-2, 3)),
                       mat=mat, collection=collection, scale=(1.4, 1, 0.55), seg=16)


def _wall(name, x, z0, z1, facing, collection, seed):
    h = z1 - z0
    length = Y1 - Y0 + 120
    o = geo.grid(name, (h, length), (max(8, int(h / 2.5)), 160),
                 loc=(x, (Y0 + Y1) / 2, (z0 + z1) / 2),
                 rot=(0, math.radians(-90 if facing < 0 else 90), 0),
                 mat=toon.canyon_rock(), collection=collection)
    tex = bpy.data.textures.new(f"{name}_tex", "CLOUDS")
    tex.noise_scale = 6.0
    tex.noise_depth = 3
    d = o.modifiers.new("rock", "DISPLACE")
    d.texture = tex
    d.strength = 3.5
    d.texture_coords = "GLOBAL"
    tex2 = bpy.data.textures.new(f"{name}_tex2", "STUCCI")
    tex2.noise_scale = 1.2
    d2 = o.modifiers.new("rock_fine", "DISPLACE")
    d2.texture = tex2
    d2.strength = 0.4
    d2.texture_coords = "GLOBAL"
    return o


def sand_material():
    m = bpy.data.materials.new("sand")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.3
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = toon.hex_rgba("#d9773a")
    ramp.color_ramp.elements[1].color = toon.hex_rgba("#f0a35e")
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    return m


def build(scene):
    c = geo.coll("world")
    sun = sky(scene)
    clouds(c)
    sand = sand_material()
    # line A side
    _wall("wallA", 9.0, -2, 70, -1, c, 1)
    _wall("cliffA", -5.5, -165, 0.5, -1, c, 2)
    geo.box("ledgeA", (14.5, Y1 - Y0 + 120, 3), (1.75, (Y0 + Y1) / 2, -1.5), mat=sand, collection=c)
    # line B side
    _wall("wallB", -48.0, -2, 70, 1, c, 3)
    _wall("cliffB", -34.5, -165, 0.5, 1, c, 4)
    geo.box("ledgeB", (14.5, Y1 - Y0 + 120, 3), (-41.25, (Y0 + Y1) / 2, -1.5), mat=sand, collection=c)
    # abyss floor: emissive blue haze
    geo.plane("abyss", (400, 800), (-20, 100, -160), mat=toon.emission("#2437a8", 1.2), collection=c)
    # far mesas on the horizon for depth
    rnd = random.Random(7)
    for i in range(10):
        geo.box(f"mesa{i}", (rnd.uniform(30, 80), rnd.uniform(20, 40), rnd.uniform(10, 25)),
                (rnd.uniform(-200, 200), rnd.uniform(420, 520), 0), mat=toon.toon("#c86a3c", 0.6), collection=c)
    return {"sun": sun, "collection": c}
