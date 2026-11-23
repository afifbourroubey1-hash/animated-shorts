"""Materials and the cartoon "ink outline" used by every object.

Look of the reference style: flat-ish colours, soft sun shadows, thick black
outlines around characters only, very saturated sky/canyon colours.

Works in both Cycles and EEVEE (no Shader-to-RGB, which Cycles lacks).
"""
from __future__ import annotations

import bpy

_cache: dict[str, bpy.types.Material] = {}


def hex_rgba(h: str, a: float = 1.0) -> tuple[float, float, float, float]:
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


def _new(name: str) -> tuple[bpy.types.Material, bpy.types.NodeTree]:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt


def _out(nt, shader_socket):
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(shader_socket, o.inputs["Surface"])
    return o


def toon(color: str, flat: float = 0.45, rough: float = 0.8, name: str | None = None) -> bpy.types.Material:
    """Diffuse + a little emission so shadows never go muddy (cartoon look)."""
    key = name or f"toon_{color}_{flat}_{rough}"
    if key in _cache:
        return _cache[key]
    m, nt = _new(key)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_rgba(color)
    bsdf.inputs["Roughness"].default_value = rough
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(color)
    em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = flat
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    m.diffuse_color = hex_rgba(color)
    _cache[key] = m
    return m


def animated_toon(name: str, color: str, flat: float = 0.45) -> bpy.types.Material:
    """A toon material whose colour can be keyframed (face turning purple...).

    Key `mat.node_tree.nodes["RGB"].outputs[0].default_value`.
    """
    m, nt = _new(name)
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.name = "RGB"
    rgb.outputs[0].default_value = hex_rgba(color)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.8
    em = nt.nodes.new("ShaderNodeEmission")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = flat
    nt.links.new(rgb.outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(rgb.outputs[0], em.inputs["Color"])
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    return m


def key_color(mat: bpy.types.Material, frame: int, color: str) -> None:
    sock = mat.node_tree.nodes["RGB"].outputs[0]
    sock.default_value = hex_rgba(color)
    sock.keyframe_insert("default_value", frame=frame)


def emission(color: str, strength: float = 4.0, name: str | None = None) -> bpy.types.Material:
    key = name or f"emit_{color}_{strength}"
    if key in _cache:
        return _cache[key]
    m, nt = _new(key)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(color)
    em.inputs["Strength"].default_value = strength
    _out(nt, em.outputs[0])
    _cache[key] = m
    return m


def outline_material() -> bpy.types.Material:
    """Black where the inverted hull faces the camera, transparent elsewhere."""
    if "ink_outline" in _cache:
        return _cache["ink_outline"]
    m, nt = _new("ink_outline")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    black = nt.nodes.new("ShaderNodeEmission")
    black.inputs["Color"].default_value = (0.005, 0.005, 0.005, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    nt.links.new(black.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    m.use_backface_culling = True
    try:  # Blender 4.2+
        m.surface_render_method = "DITHERED"
    except AttributeError:
        pass
    _cache["ink_outline"] = m
    return m


def add_outline(obj: bpy.types.Object, thickness: float = 0.025) -> None:
    """Inverted-hull outline: Solidify with flipped normals + outline material."""
    if obj.type != "MESH":
        return
    mats = obj.data.materials
    if not mats:
        mats.append(toon("#ffffff"))
    mats.append(outline_material())
    mod = obj.modifiers.new("ink", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(mats) - 1


def canyon_rock() -> bpy.types.Material:
    """Layered sandstone: horizontal bands distorted by noise, fading to blue at depth."""
    if "canyon_rock" in _cache:
        return _cache["canyon_rock"]
    m, nt = _new("canyon_rock")
    pos = nt.nodes.new("ShaderNodeNewGeometry")  # world-space position: bands stay horizontal
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.04
    noise.inputs["Detail"].default_value = 6
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 9.0
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 0.06
    wave.inputs["Distortion"].default_value = 2.5
    wave.inputs["Detail"].default_value = 3
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cols = ["#7a1f12", "#c4441b", "#e8772e", "#f3b26b", "#b8361a", "#5e1810"]
    while len(cr.elements) < len(cols):
        cr.elements.new(0.5)
    for i, c in enumerate(cols):
        cr.elements[i].position = i / (len(cols) - 1)
        cr.elements[i].color = hex_rgba(c)
    # depth fade to blue haze: z from +20 (rock) to -120 (blue)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 5
    mr.inputs["From Max"].default_value = -110
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.inputs["B"].default_value = hex_rgba("#2b3fbf")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.95
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.35
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.4
    L = nt.links.new
    L(pos.outputs["Position"], noise.inputs["Vector"])
    L(pos.outputs["Position"], sep.inputs[0])
    L(noise.outputs["Fac"], add.inputs[0])
    L(sep.outputs["Z"], add.inputs[2])
    L(pos.outputs["Position"], wave.inputs["Vector"])
    L(wave.outputs["Fac"], ramp.inputs["Fac"])
    L(sep.outputs["Z"], mr.inputs["Value"])
    L(mr.outputs["Result"], mixc.inputs["Factor"])
    L(ramp.outputs["Color"], mixc.inputs["A"])
    L(mixc.outputs["Result"], bsdf.inputs["Base Color"])
    L(mixc.outputs["Result"], em.inputs["Color"])
    L(bsdf.outputs[0], mix.inputs[1])
    L(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    _cache["canyon_rock"] = m
    return m


def gravel() -> bpy.types.Material:
    """Ballast: voronoi cells coloured from a pebble palette."""
    if "gravel" in _cache:
        return _cache["gravel"]
    m, nt = _new("gravel")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 9
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cols = ["#6e4a3a", "#b98a6e", "#8f5f48", "#d8b9a0", "#5a3a2e"]
    while len(cr.elements) < len(cols):
        cr.elements.new(0.5)
    for i, c in enumerate(cols):
        cr.elements[i].position = i / (len(cols) - 1)
        cr.elements[i].color = hex_rgba(c)
    cr.interpolation = "CONSTANT"
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 1.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(vor.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    _out(nt, bsdf.outputs[0])
    _cache["gravel"] = m
    return m


def hot_steel(name: str) -> bpy.types.Material:
    """Rail steel whose heat (0..1) is keyed on node "Heat": grey -> yellow -> magenta glow.

    Mirrors the reference's trick of colouring rails as they heat up so the
    audience *sees* temperature.
    """
    m, nt = _new(name)
    heat = nt.nodes.new("ShaderNodeValue")
    heat.name = "Heat"
    heat.outputs[0].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].color = hex_rgba("#5b5f66")
    cr.elements[1].position = 1.0
    cr.elements[1].color = hex_rgba("#ff2bd6")
    mid = cr.elements.new(0.55)
    mid.color = hex_rgba("#ffd21f")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.8
    bsdf.inputs["Roughness"].default_value = 0.35
    em = nt.nodes.new("ShaderNodeEmission")
    strength = nt.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 3.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    L = nt.links.new
    L(heat.outputs[0], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    L(ramp.outputs["Color"], em.inputs["Color"])
    L(heat.outputs[0], strength.inputs[0])
    L(strength.outputs[0], em.inputs["Strength"])
    L(heat.outputs[0], mix.inputs["Fac"])
    L(bsdf.outputs[0], mix.inputs[1])
    L(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    return m


def key_heat(mat: bpy.types.Material, frame: int, value: float) -> None:
    s = mat.node_tree.nodes["Heat"].outputs[0]
    s.default_value = value
    s.keyframe_insert("default_value", frame=frame)


def wood(color_a="#8a5a33", color_b="#5e3a1f", scale=3.0) -> bpy.types.Material:
    key = f"wood_{color_a}_{color_b}_{scale}"
    if key in _cache:
        return _cache[key]
    m, nt = _new(key)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 4
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hex_rgba(color_b)
    ramp.color_ramp.elements[1].color = hex_rgba(color_a)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.85
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    _out(nt, bsdf.outputs[0])
    _cache[key] = m
    return m


def stripes(color_a: str, color_b: str, scale: float = 14.0) -> bpy.types.Material:
    """Vertical stripes (railroad engineer cap / circus umbrella)."""
    key = f"stripes_{color_a}_{color_b}_{scale}"
    if key in _cache:
        return _cache[key]
    m, nt = _new(key)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_profile = "SAW"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = scale
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = hex_rgba(color_a)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = hex_rgba(color_b)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.8
    em = nt.nodes.new("ShaderNodeEmission")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.4
    nt.links.new(tc.outputs["Generated"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    _out(nt, mix.outputs[0])
    _cache[key] = m
    return m
