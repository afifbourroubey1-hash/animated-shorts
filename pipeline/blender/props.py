"""Set dressing for the non-canyon shots: station, coach interior, calendar,
thermometer, newspaper, coin, saw, crane, physics diagram."""
from __future__ import annotations

import math

import geo
import toon

R90 = math.radians(90)


def station(collection, origin=(0, -200, 0), banner="FIRST LINE IN\nWINS THE MAIL!"):
    ox, oy, oz = origin
    c = collection
    geo.box("st_platform", (30, 26, 0.6), (ox, oy, oz + 0.3), mat=toon.wood("#b07a4a", "#7a4f2c", 2.5), collection=c)
    # checkered floor stripe
    for i in range(16):
        geo.box(f"st_tile{i}", (1.6, 1.6, 0.02), (ox - 12 + i * 1.6, oy + 4, oz + 0.61),
                mat="#2b56b8" if i % 2 else "#f0f0f0", collection=c)
    bld = geo.box("st_building", (34, 8, 18), (ox, oy + 18, oz + 9), mat="#b8453a", collection=c)
    toon.add_outline(bld, 0.08)
    for r in range(3):
        for k in range(9):
            geo.box(f"st_win{r}_{k}", (1.4, 0.1, 2.0), (ox - 14 + k * 3.5, oy + 13.9, oz + 5 + r * 4),
                    mat="#f4f1e6", collection=c)
    geo.box("st_tower", (6, 6, 8), (ox, oy + 17, oz + 22), mat="#a33a30", collection=c)
    clock = geo.cyl("st_clock", 2.2, 0.3, (ox, oy + 13.9, oz + 22), rot=(R90, 0, 0), mat="#f7f3e3",
                    collection=c, seg=40)
    toon.add_outline(clock, 0.1)
    geo.box("st_hand1", (0.15, 0.1, 1.6), (ox, oy + 13.6, oz + 22.7), mat="#111111", collection=c)
    geo.box("st_hand2", (1.2, 0.1, 0.15), (ox + 0.6, oy + 13.6, oz + 22), mat="#111111", collection=c)
    # banner
    geo.box("st_banner", (16, 0.2, 4.6), (ox, oy + 12, oz + 11), mat="#c0392b", collection=c)
    geo.box("st_banner_in", (15.2, 0.1, 3.9), (ox, oy + 11.85, oz + 11), mat="#f4d03f", collection=c)
    geo.text("st_banner_text", banner, size=1.45, loc=(ox, oy + 11.75, oz + 11), mat="#7b1111", collection=c)
    # glass roof arches
    for k in range(6):
        geo.torus(f"st_arch{k}", 15, 0.15, (ox, oy - 10 + k * 4, oz + 9), rot=(R90, 0, 0), mat="#1c2a44",
                  collection=c)
    # money bags
    for k, (dx, s) in enumerate(((-3.2, 0.7), (-4.2, 0.5), (3.4, 0.6))):
        bag = geo.sphere(f"st_bag{k}", s, (ox + dx, oy + 1.5, oz + 0.6 + s * 0.9), mat="#9b7a3c", collection=c,
                         scale=(1, 1, 1.1))
        toon.add_outline(bag, 0.03)
        geo.text(f"st_bag_sign{k}", "$", size=s * 1.1, loc=(ox + dx, oy + 1.5 - s * 1.02, oz + 0.6 + s * 0.9),
                 mat="#2b1d08", collection=c)
    return {"stand": (ox, oy + 2.5, oz + 0.6)}


def coach_interior(collection, origin=(300, 0, 0)):
    ox, oy, oz = origin
    c = collection
    geo.box("ci_floor", (4, 12, 0.2), (ox, oy, oz), mat="#5b1520", collection=c)
    geo.box("ci_ceiling", (4, 12, 0.2), (ox, oy, oz + 3.2), mat="#3a1d12", collection=c)
    for side in (-1, 1):
        geo.box(f"ci_wall{side}", (0.2, 12, 3.2), (ox + 2 * side, oy, oz + 1.6), mat="#8a1c2b", collection=c)
        for k in range(4):
            geo.box(f"ci_window{side}{k}", (0.05, 1.3, 1.2), (ox + 1.88 * side, oy - 4.5 + k * 3, oz + 1.9),
                    mat=toon.emission("#9fd0ff", 1.6), collection=c)
            geo.sphere(f"ci_lamp{side}{k}", 0.12, (ox + 1.7 * side, oy - 3 + k * 3, oz + 2.7),
                       mat=toon.emission("#ffd27a", 8), collection=c)
    geo.box("ci_backwall", (4, 0.2, 3.2), (ox, oy + 6, oz + 1.6), mat="#6e1622", collection=c)
    seat = geo.box("ci_seat", (1.6, 0.9, 0.5), (ox, oy + 1.0, oz + 0.45), mat="#b0182b", collection=c)
    toon.add_outline(seat, 0.03)
    back = geo.box("ci_seatback", (1.6, 0.25, 1.4), (ox, oy + 1.5, oz + 1.1), mat="#b0182b", collection=c)
    toon.add_outline(back, 0.03)
    geo.cyl("ci_table", 0.35, 0.05, (ox + 0.9, oy + 0.2, oz + 0.8), mat="#c9a227", collection=c)
    cup = geo.cyl("ci_cup", 0.07, 0.1, (ox + 0.9, oy + 0.2, oz + 0.88), mat="#ffffff", collection=c, seg=16)
    toon.add_outline(cup, 0.01)
    return {"seat": (ox, oy + 1.0, oz + 0.45), "cup": cup}


def calendar_board(collection, loc, months=("MAY", "JUNE", "JULY", "AUGUST")):
    x, y, z = loc
    c = collection
    board = geo.box("cal_board", (1.4, 0.1, 1.7), (x, y, z + 1.2), mat="#2e8b57", collection=c)
    toon.add_outline(board, 0.02)
    geo.box("cal_post", (0.12, 0.12, 1.2), (x, y + 0.05, z + 0.3), mat="#5e3a1f", collection=c)
    geo.box("cal_page", (0.8, 0.02, 0.9), (x + 0.2, y - 0.06, z + 1.25), mat="#fbf8ee", collection=c)
    geo.box("cal_head", (0.8, 0.02, 0.18), (x + 0.2, y - 0.07, z + 1.62), mat="#c0392b", collection=c)
    geo.text("cal_year", "1889", size=0.12, loc=(x + 0.2, y - 0.09, z + 1.62), mat="#ffffff", collection=c)
    texts = [geo.text(f"cal_{m}", m, size=0.2 if len(m) < 5 else 0.15, loc=(x + 0.2, y - 0.09, z + 1.2),
                      mat="#c0392b", collection=c) for m in months]
    # thermometer
    geo.box("thermo_back", (0.18, 0.04, 1.0), (x - 0.42, y - 0.06, z + 1.2), mat="#f4f1e6", collection=c)
    geo.sphere("thermo_bulb", 0.07, (x - 0.42, y - 0.1, z + 0.75), mat="#d4161b", collection=c, seg=12)
    fill = geo.box("thermo_fill", (0.05, 0.02, 1.0), (x - 0.42, y - 0.1, z + 0.75), mat="#d4161b", collection=c)
    # pivot the fill at its bottom: shift mesh up so scale grows upward
    for v in fill.data.vertices:
        v.co.z += 0.5
    fill.scale = (1, 1, 0.25)
    return {"months": texts, "fill": fill}


def newspaper(collection, name="paper", title="THE CANYON GAZETTE", headline="THE RATTLE\nLINE!"):
    c = collection
    root = geo.empty(f"{name}_root", collection=c)
    sheet = geo.box(f"{name}_sheet", (0.9, 0.01, 1.2), (0, 0, 0), mat="#f3ecd6", parent=root, collection=c)
    toon.add_outline(sheet, 0.01)
    geo.text(f"{name}_title", title, size=0.075, loc=(0, -0.01, 0.5), mat="#222222", parent=root, collection=c)
    geo.box(f"{name}_rule", (0.8, 0.005, 0.012), (0, -0.01, 0.44), mat="#222222", parent=root, collection=c)
    geo.text(f"{name}_head", headline, size=0.15, loc=(0, -0.012, 0.22), mat="#111111", parent=root, collection=c)
    geo.box(f"{name}_img", (0.6, 0.005, 0.35), (0, -0.01, -0.18), mat="#b7ad93", parent=root, collection=c)
    for i in range(5):
        geo.box(f"{name}_line{i}", (0.75, 0.005, 0.02), (0, -0.01, -0.42 - i * 0.04), mat="#8d8673",
                parent=root, collection=c)
    return root


def coin(collection, name="coin"):
    o = geo.cyl(name, 0.012, 0.0022, (0, 0, 0), rot=(0, R90, 0), mat="#e3b23c", collection=collection, seg=32)
    return o


def saw(collection, name="saw"):
    root = geo.empty(f"{name}_root", collection=collection)
    geo.box(f"{name}_blade", (0.02, 0.7, 0.12), (0, 0, 0), mat="#c7ccd1", parent=root, collection=collection)
    geo.box(f"{name}_handle", (0.05, 0.18, 0.16), (0, 0.42, 0.04), mat="#7a4b22", parent=root, collection=collection)
    return root


def crane(collection, loc):
    x, y, z = loc
    c = collection
    root = geo.empty("crane_root", (x, y, z), collection=c)
    geo.box("crane_base", (3, 4, 1.2), (0, 0, 0.6), mat="#2c4a8a", parent=root, collection=c)
    mast = geo.box("crane_mast", (0.5, 0.5, 9), (0, 0, 5.2), mat="#f1c40f", parent=root, collection=c)
    toon.add_outline(mast, 0.03)
    boom = geo.empty("crane_boom_pivot", (0, 0, 9.5), parent=root, collection=c)
    geo.box("crane_boom", (0.4, 9, 0.4), (0, -4.2, 0), mat="#f1c40f", parent=boom, collection=c)
    cable = geo.cyl("crane_cable", 0.03, 6, (0, -8.4, -3), mat="#111111", parent=boom, collection=c, seg=6)
    return {"root": root, "boom": boom, "cable": cable}


def physics_card(collection, origin=(600, 0, 0)):
    ox, oy, oz = origin
    c = collection
    geo.box("phys_bg", (6, 0.1, 10), (ox, oy + 1.5, oz + 2), mat=toon.toon("#fff6e0", 0.9), collection=c)
    f1 = geo.text("phys_formula", "ΔL = α · L · ΔT", size=0.55, loc=(ox, oy + 1.3, oz + 5.2), mat="#1b1b1b",
                  collection=c)
    f2 = geo.text("phys_numbers", "11.89 m × 0.000012 × 50°C", size=0.3, loc=(ox, oy + 1.3, oz + 4.2),
                  mat="#444444", collection=c)
    f3 = geo.text("phys_result", "≈ 7 mm", size=0.9, loc=(ox, oy + 1.3, oz + 3.0), mat="#d4161b", collection=c)
    return {"formula": f1, "numbers": f2, "result": f3, "origin": (ox, oy, oz)}
