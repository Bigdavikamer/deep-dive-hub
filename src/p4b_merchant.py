"""Phase 4b -- Merchant Row and plaza enclosure.

Merchant Row's curved arcade with all four bays, the inn frontage, two
warehouse gables, the boat shed, the net loft, a salt house, the merchant
cart, the gamepass display wall, all ten NPC anchor Empties, and
out/npc_anchors.json.

WHY THE ENCLOSURE SITS INSIDE THE PLAZA. "Back 55% of the plaza's outer rim
with built mass" cannot be done from outside it: beyond PLAZA_OUTER_R the plot
pockets occupy +/-15.5 deg around each of the seven plot angles (217 deg of the
circle), leaving only ~10.6-deg verges between them. So the enclosing mass
stands on the plaza deck at its periphery, the way Merchant Row already does
at ROW_RADIUS=112 -- buildings backing the rim from within, with the eight lane
corridors left open as the doorways.

Coverage is measured, not asserted: enclosure_report() sums each building's
angular span at the rim, subtracts anything overlapping a lane, and the build
prints the result against ENCLOSURE_COVERAGE. Heights stay inside
ENCLOSURE_H_MIN..ENCLOSURE_H_MAX so the spire at Z=95 always wins the skyline.

MOOD DIRECTIVE, applied from the start rather than retrofitted:
  1. Light is scarce. This phase builds exactly one lit site --
     DD_Lamp_InnFrontage, the inn marking spawn. The four Merchant Row bay
     lanterns are modelled identically but their glass goes to the dark slot.
  2. Warm colour is rationed. Every awning, pennant and painted sign asks
     lib.mood.WarmBudget before taking cloth_red / lantern_gold, capped at
     WARM_ACCENT_MAX_PER_DISTRICT per plaza quarter. Refused ones fall through
     to cloth_blue, which is the default rather than the exception.
  3. Depth darkens. The arcade undercroft -- back walls, counters and shelves
     shaded by the roof -- takes a flat multiply, so the colonnade reads as
     genuinely recessed with scene lighting off.

Deferred on purpose: the four to six demountable stalls. The brief describes
them here, but the Phase 7a prop library specifies "Temporary stall, 3
variants" placed by linked instance, and building them twice would fork the
mesh data and break validate.py check 17.

Idempotent: purges its own prefixes before rebuilding.
"""
import json
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bmesh
import bpy

import config
from lib import mesh as dd_mesh
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import scene as dd_scene

DECK_Z = config.PLAZA_LIFT

# lane corridors that must stay open: seven plot lanes plus the gate
LANE_ANGLES = [0.0] + list(config.PLOT_ANGLES_DEG)
LANE_CLEAR_DEG = math.degrees(
    (config.TRAFFIC_LANE_WIDTH + 2 * config.LANE_CLEARANCE) / config.PLAZA_OUTER_R)

# (name, centre angle, arc span, radius, depth, wall height, ridge height)
# Spans are tuned against the lane corridors, not eyeballed: each entry sits
# wholly inside one of the eight gaps between lanes. SaltHouse was 124/22,
# which ran 0.84 deg into the Plot 3 lane; Cooperage fills the 180-221.6 gap,
# which was the one stretch of rim with no built mass at all and left coverage
# a shade under the 55% floor.
ENCLOSURE = [
    ("InnFrontage",  159.0, 30.0, 118.0, 20.0, 20.0, 27.0),
    ("WarehouseA",    76.0, 26.0, 118.0, 20.0, 22.0, 29.0),
    ("WarehouseB",   283.0, 26.0, 118.0, 20.0, 21.0, 28.0),
    ("BoatShed",     331.0, 30.0, 116.0, 22.0, 18.0, 24.0),
    ("NetLoft",      242.0, 26.0, 118.0, 18.0, 19.0, 26.0),
    ("SaltHouse",    122.0, 20.0, 118.0, 18.0, 18.0, 25.0),
    ("Cooperage",    200.0, 29.0, 118.0, 20.0, 19.0, 26.0),
]

ROW_SPAN_DEG = math.degrees(config.ROW_LENGTH / config.ROW_RADIUS)

OWNED_PREFIXES = [
    "DD_Struct_Row",
    "DD_UI_RowChalkboard",
    "DD_Lamp_RowBay",
    "DD_Struct_Inn",
    "DD_Lamp_InnFrontage",
    "DD_Struct_Warehouse",
    "DD_Struct_BoatShed",
    "DD_Struct_NetLoft",
    "DD_Struct_SaltHouse",
    "DD_Struct_Cooperage",
    "DD_Struct_MerchantCart",
    "DD_UI_GamepassWall",
    "DD_Marker_NPC_",
]


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def _finish(obj, collection="Structures"):
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, collection)
    return obj


def _emit(name, bm, collection="Structures"):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return _finish(dd_mesh.bm_to_object(name, bm), collection)


def _add_box(bm, center, size, yaw=0.0):
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    corners = [(x * cos_y - y * sin_y, x * sin_y + y * cos_y) for x, y in corners]
    lo = [bm.verts.new((cx + x, cy + y, cz - hz)) for x, y in corners]
    hi = [bm.verts.new((cx + x, cy + y, cz + hz)) for x, y in corners]
    bm.verts.ensure_lookup_table()
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def _add_gable(bm, center, width, depth, base_z, wall_h, ridge_h, yaw=0.0):
    """Closed gable prism: rectangular walls with a ridge running along local X.
    Roof-line variation is what stops the enclosure reading as one long wall."""
    cx, cy = center
    hx, hy = width / 2.0, depth / 2.0
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    def place(x, y, z):
        return (cx + x * cos_y - y * sin_y, cy + x * sin_y + y * cos_y, z)

    v = [bm.verts.new(place(*p)) for p in (
        (-hx, -hy, base_z), (hx, -hy, base_z), (hx, hy, base_z), (-hx, hy, base_z),
        (-hx, -hy, base_z + wall_h), (hx, -hy, base_z + wall_h),
        (hx, hy, base_z + wall_h), (-hx, hy, base_z + wall_h),
        (-hx, 0.0, base_z + ridge_h), (hx, 0.0, base_z + ridge_h),
    )]
    bm.verts.ensure_lookup_table()
    bm.faces.new((v[0], v[3], v[2], v[1]))                 # floor
    bm.faces.new((v[0], v[1], v[5], v[4]))                 # -Y wall
    bm.faces.new((v[2], v[3], v[7], v[6]))                 # +Y wall
    bm.faces.new((v[0], v[4], v[8]))                       # gable end -X
    bm.faces.new((v[0], v[8], v[7], v[3]))
    bm.faces.new((v[1], v[9], v[5]))                       # gable end +X
    bm.faces.new((v[1], v[2], v[6], v[9]))
    bm.faces.new((v[4], v[5], v[9], v[8]))                 # roof -Y
    bm.faces.new((v[7], v[8], v[9], v[6]))                 # roof +Y


def _polar(angle_deg, radius, z=0.0):
    a = math.radians(angle_deg)
    return (radius * math.cos(a), radius * math.sin(a), z)


def _tangent_yaw(angle_deg):
    """Yaw so a box's local X follows the arc at this angle."""
    return math.radians(angle_deg + 90.0)


# ---- Merchant Row ----------------------------------------------------------

def _bay_angles():
    """Centre angle of each of the ROW_BAYS bays along the arc."""
    step = math.degrees((config.ROW_BAY_W + config.ROW_PIER_W) / config.ROW_RADIUS)
    first = config.ROW_ANGLE_DEG - step * (config.ROW_BAYS - 1) / 2.0
    return [first + step * i for i in range(config.ROW_BAYS)]


def build_row_shell():
    """Curved colonnade: stone piers, timber lintel at ROW_ARCADE_H, slate roof
    to ROW_ROOF_Z, and a shuttered upper storey above -- storage over shops,
    which is both the correct medieval arrangement and the vertical layer."""
    objs = []
    r = config.ROW_RADIUS
    back_r = r + config.ROW_DEPTH / 2.0
    half = ROW_SPAN_DEG / 2.0
    a0, a1 = config.ROW_ANGLE_DEG - half, config.ROW_ANGLE_DEG + half

    # piers, one between each pair of bays plus the two ends
    bm = bmesh.new()
    step = math.degrees((config.ROW_BAY_W + config.ROW_PIER_W) / r)
    first = config.ROW_ANGLE_DEG - step * config.ROW_BAYS / 2.0
    for i in range(config.ROW_BAYS + 1):
        ang = first + step * i
        x, y, _ = _polar(ang, r)
        _add_box(bm, (x, y, DECK_Z + config.ROW_ARCADE_H / 2.0),
                 (config.ROW_PIER_W + 1.0, 4.0, config.ROW_ARCADE_H),
                 yaw=_tangent_yaw(ang))
    objs.append(_emit("DD_Struct_RowPiers", bm))

    # lintel following the arc
    obj = dd_mesh.annulus_sector_solid(
        "DD_Struct_RowLintel", inner_radius=r - 2.0, outer_radius=r + 2.0,
        angle_start_deg=a0, angle_end_deg=a1, thickness=2.0, segments=12,
        base_z=DECK_Z + config.ROW_ARCADE_H + 2.0)
    objs.append(_finish(obj))

    # back wall and the upper storey, both following the arc
    obj = dd_mesh.annulus_sector_solid(
        "DD_Struct_RowBackWall", inner_radius=back_r - 1.5, outer_radius=back_r + 1.5,
        angle_start_deg=a0, angle_end_deg=a1,
        thickness=config.ROW_ARCADE_H + 2.0, segments=12,
        base_z=DECK_Z + config.ROW_ARCADE_H + 2.0)
    objs.append(_finish(obj))

    obj = dd_mesh.annulus_sector_solid(
        "DD_Struct_RowUpper", inner_radius=r - 3.0, outer_radius=back_r + 1.5,
        angle_start_deg=a0, angle_end_deg=a1,
        thickness=config.ROW_ROOF_Z - config.ROW_ARCADE_H - 4.0, segments=12,
        base_z=DECK_Z + config.ROW_ROOF_Z - 2.0)
    objs.append(_finish(obj))

    # slate roof: a slightly oversailing arc slab, ridge at ROW_ROOF_Z
    obj = dd_mesh.annulus_sector_solid(
        "DD_Struct_RowRoof", inner_radius=r - 5.0, outer_radius=back_r + 3.5,
        angle_start_deg=a0 - 1.5, angle_end_deg=a1 + 1.5, thickness=1.6, segments=14,
        base_z=DECK_Z + config.ROW_ROOF_Z)
    objs.append(_finish(obj))

    # shuttered windows and window boxes on the upper storey
    bm = bmesh.new()
    for ang in _bay_angles():
        x, y, _ = _polar(ang, r - 2.0)
        yaw = _tangent_yaw(ang)
        _add_box(bm, (x, y, DECK_Z + config.ROW_ROOF_Z - 6.0), (6.0, 1.0, 4.0), yaw=yaw)
        _add_box(bm, (x, y, DECK_Z + config.ROW_ROOF_Z - 8.4), (6.6, 2.0, 1.2), yaw=yaw)
    objs.append(_emit("DD_Struct_RowShutters", bm))

    # hoist beam and pulley on the end gable
    bm = bmesh.new()
    x, y, _ = _polar(a1, r + 1.0)
    yaw = _tangent_yaw(a1)
    _add_box(bm, (x, y, DECK_Z + config.ROW_ROOF_Z - 3.0), (2.0, 12.0, 1.6), yaw=yaw)
    _add_box(bm, (x, y, DECK_Z + config.ROW_ROOF_Z - 5.6), (1.6, 1.6, 2.0), yaw=yaw)
    _add_box(bm, (x, y, DECK_Z + config.ROW_ROOF_Z - 9.0), (0.4, 0.4, 5.0), yaw=yaw)
    objs.append(_emit("DD_Struct_RowHoist", bm))
    return objs


def build_row_bays(warm):
    """Every bay gets the same kit -- counter with a cyan inlay, back shelf,
    hanging trade sign, chalk board, lantern, stool -- dressed differently.
    Bay 4 is deliberately bare: the Traveller is only sometimes here, and a
    visibly vacant stall makes the town feel like it has a schedule."""
    objs = []
    r = config.ROW_RADIUS
    for i, ang in enumerate(_bay_angles(), start=1):
        yaw = _tangent_yaw(ang)
        vacant = (i == config.ROW_BAYS)

        # counter -- interactable, so it keeps the DD_Struct_RowCounter name
        # validate.py already allowlists for biolume_cyan
        bm = bmesh.new()
        x, y, _ = _polar(ang, r + 3.0)
        _add_box(bm, (x, y, DECK_Z + config.ROW_COUNTER_H / 2.0),
                 (config.ROW_BAY_W - 2.0, 3.0, config.ROW_COUNTER_H), yaw=yaw)
        xi, yi, _ = _polar(ang, r + 1.4)
        _add_box(bm, (xi, yi, DECK_Z + config.ROW_COUNTER_H - 0.3),
                 (config.ROW_BAY_W - 2.0, 0.8, 0.6), yaw=yaw)   # cyan inlay strip
        counter = _emit(f"DD_Struct_RowCounter_{i}", bm)
        dd_mood.apply_flat_darken(counter, 1.0 - config.DEPTH_DARKEN_STRENGTH * 0.6)
        objs.append(counter)

        # back shelf wall with bay-specific goods (bare in the vacant bay)
        bm = bmesh.new()
        xb, yb, _ = _polar(ang, r + config.ROW_DEPTH / 2.0 - 3.0)
        _add_box(bm, (xb, yb, DECK_Z + 4.0), (config.ROW_BAY_W - 2.0, 1.4, 8.0), yaw=yaw)
        if not vacant:
            for k in range(3):
                gx, gy, _ = _polar(ang + (k - 1) * 1.9, r + config.ROW_DEPTH / 2.0 - 4.4)
                _add_box(bm, (gx, gy, DECK_Z + 3.0 + k * 1.6),
                         (2.6, 1.6, 1.2 + 0.3 * k), yaw=yaw)
        shelf = _emit(f"DD_Struct_RowShelf_{i}", bm)
        dd_mood.apply_flat_darken(shelf, 1.0 - config.DEPTH_DARKEN_STRENGTH)
        objs.append(shelf)

        # hanging trade sign on an iron bracket, carved icon, no text
        bm = bmesh.new()
        xs, ys, _ = _polar(ang, r - 3.5)
        _add_box(bm, (xs, ys, DECK_Z + config.ROW_ARCADE_H - 1.0), (0.5, 5.0, 0.5), yaw=yaw)
        _add_box(bm, (xs, ys, DECK_Z + config.ROW_ARCADE_H - 4.0), (4.5, 0.6, 3.4), yaw=yaw)
        for k in range(i):      # carved bars, a different count per bay
            _add_box(bm, (xs, ys, DECK_Z + config.ROW_ARCADE_H - 5.2 + k * 0.9),
                     (2.6 - 0.3 * k, 1.0, 0.5), yaw=yaw)
        sign = _emit(f"DD_Struct_RowSign_{i}", bm)
        if not vacant and warm.take(dd_mood.WarmBudget.district_for(xs, ys)):
            dd_mood.mark_all(sign, dd_mood.WARM_SLOT)
        objs.append(sign)

        # chalk board: one clean quad face for a Studio SurfaceGui price list
        xc, yc, _ = _polar(ang + 1.6, r + config.ROW_DEPTH / 2.0 - 3.8)
        board = dd_mesh.box(f"DD_UI_RowChalkboard_{i}", 4.0, 0.5, 3.0,
                            base_z=0.0, yaw=yaw)
        board.location = (xc, yc, DECK_Z + 6.0)
        dd_mesh.set_quad_face_uv(board, face_index=4)
        objs.append(_finish(board, "Structures"))

        # bay lantern -- modelled the same as a lit one, glass sent to the
        # dark slot because no bay is in LIT_LANTERN_SITES
        bm = bmesh.new()
        xl, yl, _ = _polar(ang - 3.0, r - 1.0)
        _add_box(bm, (xl, yl, DECK_Z + config.ROW_ARCADE_H - 2.4), (0.4, 0.4, 2.0), yaw=yaw)
        _add_box(bm, (xl, yl, DECK_Z + config.ROW_ARCADE_H - 4.6), (1.8, 1.8, 2.4), yaw=yaw)
        _add_box(bm, (xl, yl, DECK_Z + config.ROW_ARCADE_H - 6.2), (2.4, 2.4, 0.8), yaw=yaw)
        lamp = _emit(f"DD_Lamp_RowBay_{i}", bm)
        dd_mood.mark_glass(lamp, 0.75, 3.3)
        objs.append(lamp)

        # one story prop per bay; the vacant bay gets a hitching ring instead
        bm = bmesh.new()
        xp, yp, _ = _polar(ang + 3.2, r + 5.0)
        if vacant:
            _add_box(bm, (xp, yp, DECK_Z + 0.6), (1.2, 1.2, 1.2), yaw=yaw)
        else:
            _add_box(bm, (xp, yp, DECK_Z + 1.4), (2.2, 2.2, 2.8), yaw=yaw)
        objs.append(_emit(f"DD_Struct_RowStool_{i}", bm))
    return objs


def build_merchant_cart(warm):
    """Movable: Studio parks it in bay 4 on a timer. Built as its own object so
    the vacant bay reads as vacant when the cart is elsewhere."""
    ang = config.ROW_ANGLE_DEG - ROW_SPAN_DEG / 2.0 - 12.0
    x, y, _ = _polar(ang, config.ROW_RADIUS + 2.0)
    yaw = _tangent_yaw(ang)
    bm = bmesh.new()
    _add_box(bm, (x, y, DECK_Z + 3.0), (12.0, 6.0, 3.0), yaw=yaw)
    _add_box(bm, (x, y, DECK_Z + 5.2), (10.0, 5.0, 1.4), yaw=yaw)
    for s in (1.0, -1.0):
        wx, wy, _ = _polar(ang + 2.0 * s, config.ROW_RADIUS + 2.0)
        _add_box(bm, (wx, wy, DECK_Z + 1.5), (3.0, 0.8, 3.0), yaw=yaw)
    _add_box(bm, (x, y, DECK_Z + 8.0), (11.0, 6.4, 0.6), yaw=yaw)     # folded awning
    cart = _emit("DD_Struct_MerchantCart", bm)
    if warm.take(dd_mood.WarmBudget.district_for(x, y)):
        dd_mood.mark_all(cart, dd_mood.WARM_SLOT)
    return cart


# ---- enclosure -------------------------------------------------------------

def build_enclosure(warm):
    """Six gabled buildings backing the plaza rim, heights inside
    ENCLOSURE_H_MIN..H_MAX, each clear of the eight lane corridors."""
    objs = []
    for name, ang, span, radius, depth, wall_h, ridge_h in ENCLOSURE:
        width = 2.0 * radius * math.sin(math.radians(span) / 2.0)
        bm = bmesh.new()
        x, y, _ = _polar(ang, radius)
        _add_gable(bm, (x, y), width, depth, DECK_Z, wall_h, ridge_h,
                   yaw=_tangent_yaw(ang))
        objs.append(_emit(f"DD_Struct_{name}", bm))
    return objs


def build_inn_fitout(warm):
    """The inn marks spawn, so it carries this phase's single lit lantern --
    the one piece of warm light on the whole west side."""
    objs = []
    ang, radius = 159.0, 118.0
    yaw = _tangent_yaw(ang)
    x, y, _ = _polar(ang, radius - 11.0)

    # Not "DD_Struct_InnFrontage" -- that name belongs to the enclosure gable
    # in ENCLOSURE, and colliding with it made Blender append ".001", which
    # then failed the naming regex.
    bm = bmesh.new()
    _add_box(bm, (x, y, DECK_Z + 5.0), (10.0, 2.0, 4.0), yaw=yaw)          # bay window
    _add_box(bm, (x, y, DECK_Z + 0.6), (14.0, 4.0, 1.2), yaw=yaw)          # stoop
    objs.append(_emit("DD_Struct_InnBayWindow", bm))

    bm = bmesh.new()
    bx, by, _ = _polar(ang + 3.5, radius - 12.0)
    _add_box(bm, (bx, by, DECK_Z + 1.4), (6.0, 1.6, 0.6), yaw=yaw)
    for s in (1.0, -1.0):
        lx, ly, _ = _polar(ang + 3.5 + 0.8 * s, radius - 12.0)
        _add_box(bm, (lx, ly, DECK_Z + 0.7), (0.8, 1.4, 1.4), yaw=yaw)
    objs.append(_emit("DD_Struct_InnBench", bm))

    bm = bmesh.new()
    sx, sy, _ = _polar(ang - 4.0, radius - 12.5)
    _add_box(bm, (sx, sy, DECK_Z + 11.0), (0.5, 4.0, 0.5), yaw=yaw)
    _add_box(bm, (sx, sy, DECK_Z + 8.4), (4.0, 0.6, 3.0), yaw=yaw)
    sign = _emit("DD_Struct_InnSign", bm)
    if warm.take(dd_mood.WarmBudget.district_for(sx, sy)):
        dd_mood.mark_all(sign, dd_mood.WARM_SLOT)
    objs.append(sign)

    # the lit lantern: same model as every other, different glass material
    bm = bmesh.new()
    lx, ly, _ = _polar(ang + 1.0, radius - 12.5)
    _add_box(bm, (lx, ly, DECK_Z + 10.0), (0.4, 0.4, 2.0), yaw=yaw)
    _add_box(bm, (lx, ly, DECK_Z + 7.8), (1.8, 1.8, 2.4), yaw=yaw)
    _add_box(bm, (lx, ly, DECK_Z + 6.2), (2.4, 2.4, 0.8), yaw=yaw)
    lamp = _emit("DD_Lamp_InnFrontage", bm)
    dd_mood.mark_glass(lamp, 0.75, 3.3)
    objs.append(lamp)
    return objs


def build_gamepass_wall():
    """Three framed panels on the shop's south arch. Frame only, never the
    content -- the panels are clean quads with correct UVs for a SurfaceGui."""
    objs = []
    y = -config.SHOP_FOOTPRINT / 2.0 - 0.8
    for i in range(3):
        x = (i - 1) * 9.0
        panel = dd_mesh.box(f"DD_UI_GamepassWall_{i + 1}", 7.0, 0.6, 9.0, base_z=0.0)
        panel.location = (x, y, 6.0)
        dd_mesh.set_quad_face_uv(panel, face_index=2)   # -Y face, toward the plaza
        objs.append(_finish(panel, "Structures"))
    return objs


# ---- NPC anchors -----------------------------------------------------------

def anchor_positions():
    """World position and facing for every entry in config.NPC_ANCHORS.
    LampTender is the roaming one -- it gets the first of its five candidate
    sites, and the rest are emitted to the JSON for Studio to choose from."""
    bays = _bay_angles()
    r = config.ROW_RADIUS
    pos = {}
    for i, name in enumerate(("Tidewright", "Fishmonger", "Assayer", "Traveller")):
        ang = bays[i]
        x, y, _ = _polar(ang, r + config.ROW_DEPTH / 2.0 - 6.0)
        pos[name] = ((x, y, DECK_Z), ang + 180.0)       # behind the counter, facing out

    half = config.SHOP_FOOTPRINT / 2.0
    pos["Curator"] = ((0.0, half - 8.0, config.GROUND_Z), 270.0)
    pos["Harbourmaster"] = ((half - 8.0, 0.0, config.GROUND_Z), 180.0)

    ix, iy, _ = _polar(159.0, 118.0 - 13.0)
    pos["Innkeeper"] = ((ix, iy, DECK_Z), 159.0 + 180.0)
    pos["Shipwright"] = ((config.KIOSK_XY[0] - 4.0, config.KIOSK_XY[1], config.GROUND_Z),
                         math.degrees(math.atan2(-config.KIOSK_XY[1], -config.KIOSK_XY[0])))
    pos["Deckhand"] = ((config.ISLAND_RADIUS + config.BEACH_RUN + 6.0,
                        config.DOCK_OFFSET_Y, config.BEACH_DROP), 180.0)
    pos["LampTender"] = (LAMPTENDER_SITES[0][1], LAMPTENDER_SITES[0][2])
    return pos


LAMPTENDER_SITES = [
    ("rim_path",       (-150.0, 95.0, config.GROUND_Z), 0.0),
    ("tide_pool",      (config.POOL_XY[0] + 30.0, config.POOL_XY[1], config.GROUND_Z), 180.0),
    ("breakwater_head", (272.0, 103.0, 5.0), 200.0),
    ("behind_shop",    (-44.0, -18.0, config.PLAZA_LIFT), 0.0),
    ("fossil_arch",    (232.0, 0.0, config.GROUND_Z), 180.0),
]


def build_npc_anchors():
    """One Empty per entry in config.NPC_ANCHORS, named so validate.py check 23
    finds it. Empties do not survive FBX, so out/npc_anchors.json is the real
    deliverable -- Studio spawns by name from that."""
    pos = anchor_positions()
    objs = []
    for name, _site in config.NPC_ANCHORS:
        (x, y, z), facing = pos[name]
        empty = bpy.data.objects.new(f"DD_Marker_NPC_{name}", None)
        empty.empty_display_type = "SINGLE_ARROW"
        empty.empty_display_size = 4.0
        empty.location = (x, y, z)
        empty.rotation_euler = (0.0, 0.0, math.radians(facing))
        bpy.context.scene.collection.objects.link(empty)
        dd_scene.link_to_collection(empty, "Markers")
        objs.append(empty)
    return objs


def export_npc_json():
    """Roblox coordinates: roblox_x = blender_x, roblox_y = blender_z,
    roblox_z = -blender_y.

    Shape is dictated by validate.py's check_npc_json_roundtrip, which was
    written in Phase 0 to define the contract: a flat list whose entries carry
    name/x/y/z at the top level. The roaming LampTender's other four candidate
    sites go to their own file rather than into this list -- extra entries here
    would be looked up as DD_Marker_NPC_<that name> and fail the round trip.
    """
    out_dir = os.path.join(REPO_ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    pos = anchor_positions()

    anchors = []
    for name, site in config.NPC_ANCHORS:
        (x, y, z), facing = pos[name]
        anchors.append({
            "name": name, "site": site,
            "x": round(x, 3), "y": round(z, 3), "z": round(-y, 3),
            "facing_deg": round(facing, 2),
        })
    path = os.path.join(out_dir, "npc_anchors.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(anchors, fh, indent=2)

    roam = [{
        "site": site,
        "x": round(x, 3), "y": round(z, 3), "z": round(-y, 3),
        "facing_deg": round(facing, 2),
    } for site, (x, y, z), facing in LAMPTENDER_SITES]
    with open(os.path.join(out_dir, "npc_lamptender_sites.json"), "w", encoding="utf-8") as fh:
        json.dump(roam, fh, indent=2)
    return path


# ---- verification ----------------------------------------------------------

def _lane_overlap(a0, a1):
    """Degrees of [a0,a1] that fall inside any lane corridor."""
    total = 0.0
    for lane in LANE_ANGLES:
        l0, l1 = lane - LANE_CLEAR_DEG / 2.0, lane + LANE_CLEAR_DEG / 2.0
        lo, hi = max(a0, l0), min(a1, l1)
        if hi > lo:
            total += hi - lo
    return total


def enclosure_report():
    """Measured coverage of the plaza rim, and whether any building intrudes
    into a lane opening."""
    spans = [(f"Row", config.ROW_ANGLE_DEG, ROW_SPAN_DEG)]
    spans += [(n, a, s) for n, a, s, _r, _d, _w, _h in ENCLOSURE]
    covered = 0.0
    intrusions = []
    for name, ang, span in spans:
        a0, a1 = ang - span / 2.0, ang + span / 2.0
        bad = _lane_overlap(a0, a1)
        if bad > 0.01:
            intrusions.append((name, round(bad, 2)))
        covered += span - bad
    return covered / 360.0, intrusions


def build():
    dd_scene.ensure_collections()
    purge()
    warm = dd_mood.WarmBudget(config.WARM_ACCENT_MAX_PER_DISTRICT)
    build_row_shell()
    build_row_bays(warm)
    build_merchant_cart(warm)
    build_enclosure(warm)
    build_inn_fitout(warm)
    build_gamepass_wall()
    build_npc_anchors()
    export_npc_json()

    coverage, intrusions = enclosure_report()
    print(f"enclosure coverage {coverage:.1%} (need {config.ENCLOSURE_COVERAGE:.0%})"
          f" -- {'OK' if coverage >= config.ENCLOSURE_COVERAGE else 'SHORT'}")
    print(f"lane intrusions: {intrusions or 'none'}")
    print(f"warm accents used per district: {warm.report()} "
          f"(cap {config.WARM_ACCENT_MAX_PER_DISTRICT})")


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)
    dd_palette.apply_debug_colors([o for o in bpy.data.objects if o.name.startswith("DD_")])

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=560.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p4b_top_ortho.png"))

    row_cam = dd_scene.setup_look_at_camera(
        "RenderCam_Row", location=(38.0, 8.0, 26.0),
        target=_polar(config.ROW_ANGLE_DEG, config.ROW_RADIUS, DECK_Z + 8.0), fov_deg=60.0)
    dd_scene.render_to_file(row_cam, os.path.join(renders_dir, "p4b_merchant_row.png"))

    # The enclosure test. Not from (0,0): the shop's 60x60 footprint occupies
    # the plaza's geometric centre, so a camera there stands inside the
    # building and photographs its own arches. The meaningful vantage is out
    # on the deck looking outward, where a player actually stands.
    for label, ang in (("row", 25.0), ("inn", 159.0), ("warehouse", 283.0)):
        x, y, _ = _polar(ang, 85.0)
        cam = dd_scene.setup_eye_camera(
            f"RenderCam_Enclosure_{label}", location=(x, y, DECK_Z + 5.0),
            facing_deg=ang, fov_deg=75.0)
        dd_scene.render_to_file(cam, os.path.join(renders_dir, f"p4b_enclosure_{label}.png"))

    # and one looking back across the square, to confirm the spire still
    # clears the enclosure roofline (CLAUDE.md check 25)
    x, y, _ = _polar(200.0, 105.0)
    cam = dd_scene.setup_eye_camera(
        "RenderCam_EnclosureInward", location=(x, y, DECK_Z + 5.0),
        facing_deg=20.0, fov_deg=75.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p4b_spire_over_roofline.png"))

    spawn_cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], DECK_Z + 5.0),
        facing_deg=config.SPAWN_FACING_DEG, fov_deg=70.0)
    dd_scene.render_to_file(spawn_cam, os.path.join(renders_dir, "p4b_spawn_sightline.png"))


if __name__ == "__main__":
    build()
    capture_renders()
