"""Phase 7b -- Zones, lanes, and anchored vignette placement.

Props are placed as small ANCHORED GROUPS, not as independent points.

That is the whole idea here, and it replaced an earlier independent-sampling
pass. Independent placement never reads as intentional however large or
numerous the props are -- raising density and biasing toward big silhouettes
made the plaza fuller without making it look like anyone had put anything
anywhere. What reads as intent is several related objects together, against a
real feature, with genuinely clear ground around them. So:

  ANCHORS COME FROM FEATURES. VIGNETTE_ANCHOR_BIAS of them sit against the
  outward face of a building, at the base of a structure, on the outside of a
  path's bow, along the coast, or at one of the four district signature spots.
  Only the remainder float free, and those exist so the result does not look
  mechanically pinned to architecture.

  EACH ANCHOR GETS A SCENE. VIGNETTE_MIN_PROPS..VIGNETTE_MAX_PROPS related
  props at VIGNETTE_SPACING -- a lead object from the district's pool plus its
  clutter, tight enough to read as one thing rather than several.

  THE GAPS DO THE WORK. VIGNETTE_GAP_MIN of clear ground is enforced between
  every prop of one vignette and every prop of the next, and a vignette that
  cannot get it is dropped whole. Negative space is what makes the dressed
  spots read as dressed.

  LANES GET SIGHT CLEARANCE. Placement stands off by LANE_CLEARANCE plus
  SIGHT_CLEARANCE, so a lane reads as open well before you reach it. The
  acceptance check still tests the documented rule (lane + LANE_CLEARANCE);
  placement is simply more conservative than the rule requires.

  ONLY GROUND TEXTURE PLACES INDEPENDENTLY. Sea grass and heather are the
  kit's ambient cover; everything mid and overhead belongs to a vignette.

Kept deliberately from the tuned pass that preceded this: the weighted district
pools, OPEN_ZONE_ASSETS, and the plaza_open < plaza_edge < district_core
gradient. Consolidating points into groups lowers the total instance count;
that is the intended effect and is not compensated for by raising density.

LINKED MESH DATA THROUGHOUT: every instance is bpy.data.objects.new(name,
source.data), so one barrel mesh backs many objects and becomes one MeshId.

Idempotent: purges every placed instance (any name ending .District.Index).
"""
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bpy
import mathutils

import config
import p2_terrain
import p4_plaza
import p4b_merchant
import p6_gate
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import scene as dd_scene

LANE_HALF = config.TRAFFIC_LANE_WIDTH / 2.0 + config.LANE_CLEARANCE
LANE_HALF_PLACEMENT = LANE_HALF + config.SIGHT_CLEARANCE
VIGNETTE_RADIUS = config.VIGNETTE_SPACING * 2.4
ANCHOR_MIN_GAP = config.VIGNETTE_GAP_MIN + 2.0 * VIGNETTE_RADIUS
SETTLE_FROM_Z = 120.0
WALK_HEIGHT = 6.0

GROUND_PREFIXES = ("DD_Terrain_", "DD_Struct_Plaza", "DD_Struct_Path_",
                   "DD_Struct_Foreshore")

# Radii retuned so the bands describe the ground they are named for. The
# enclosure buildings stand at r 108..128, so the old district_core (104..133)
# was mostly INSIDE them and the strip of open floor in front of their walls --
# where dressing actually belongs -- fell in plaza_edge. Wall anchors landed at
# r~99 and the densest zone ended up with one vignette. The densities
# themselves are unchanged: plaza_open 7 < plaza_edge 9 < district_core 11.
PLAZA_OPEN_R = (32.0, 80.0)
PLAZA_EDGE_R = (80.0, 97.0)
DISTRICT_CORE_R = (97.0, 133.0)

DISTRICT_PROPS = {
    "CatchN": ["DryingRack"] * 4 + ["SaltVat"] * 2 + ["GuttingTable", "TallyBoard"]
              + ["Barrel", "Crate", "Net", "Bollard", "Tool", "LanternPost"],
    "OutfitE": ["RopeCoil"] * 4 + ["Net"] * 2 + ["Crate", "Bollard", "TallyBoard"]
               + ["Barrel", "Sawhorse", "Tool", "LanternPost"],
    "BallastS": ["TimberStack"] * 3 + ["Sawhorse"] * 2 + ["Tool"] * 2
                + ["Ballast", "Crate", "Barrel", "Rowboat", "RopeCoil", "LanternPost"],
    "MarketW": ["MarketStall"] * 3 + ["Awning"] * 2 + ["NoticeBoard", "Well"]
               + ["Crate", "BannerPole", "Story", "Barrel", "LanternPost"],
}
ZONE_PROPS = {
    "QuayRim": ["Bollard"] * 3 + ["RopeCoil"] * 2 + ["CrabPot", "Barrel", "Crate",
                                                     "Net", "Tool", "Gull", "LanternPost"],
    "Beach": ["Rock"] * 2 + ["CrabPot", "SeaGrass", "Story", "Ballast", "RopeCoil", "Gull"],
    "PlotSur": ["Rock", "SeaGrass", "Heather", "Crate", "Barrel"],
    "SubNear": ["Kelp"] * 3 + ["Coral"] * 3 + ["Ballast", "Anchor", "CrabPot",
                                               "Rock", "Buoy"],
    "IslandRim": ["Rock"] * 2 + ["SeaGrass", "Heather", "Ballast", "Gull"],
}

# Assets that can carry open floor -- the mid-layer shapes a player reads from
# across a square. These lead a vignette; the small stuff fills in around them.
OPEN_ZONE_ASSETS = {"MarketStall", "Well", "LanternPost", "NoticeBoard",
                    "DryingRack", "TimberStack", "BannerPole", "Awning",
                    "GuttingTable", "Rowboat", "SaltVat"}
SMALL_ASSETS = {"Crate", "Barrel", "Tool", "RopeCoil", "Bollard", "Sawhorse",
                "Net", "Story", "CrabPot", "Rock", "Ballast", "Kelp", "Coral",
                "Buoy", "Gull", "Anchor"}
# the only things still placed independently: true ground cover
AMBIENT_ASSETS = {"SeaGrass", "Heather"}
AMBIENT_ZONES = {"island_rim", "beach", "plot_surround", "underwater_near"}

ORIENTED = {"MarketStall", "NoticeBoard", "DryingRack", "TallyBoard", "Awning",
            "GuttingTable", "Well", "Rowboat", "BannerPole"}
WARM_ASSETS = {"MarketStall": (1, 2), "Awning": (1,), "BannerPole": (1, 2)}


def purge():
    for o in [o for o in bpy.data.objects
              if o.name.startswith("DD_") and dd_scene.is_placed_instance(o.name)]:
        bpy.data.objects.remove(o, do_unlink=True)


# ---- lanes -----------------------------------------------------------------

def _bezier_points(p0, p1, bow, samples=16):
    a, b = mathutils.Vector(p0), mathutils.Vector(p1)
    d = b - a
    perp = mathutils.Vector((-d.y, d.x)).normalized() * bow
    ctrl = (a + b) / 2.0 + perp
    return [((1 - t) ** 2 * a + 2 * (1 - t) * t * ctrl + t ** 2 * b)
            for t in (i / samples for i in range(samples + 1))]


def lane_centrelines():
    """Exactly the lanes Phases 4 and 6 built, recomputed from their own
    constants so the two can never drift apart."""
    lanes = []
    for i in range(config.PLOT_COUNT):
        ang = math.radians(config.PLOT_ANGLES_DEG[i])
        p0 = (config.PLAZA_INNER_R * math.cos(ang), config.PLAZA_INNER_R * math.sin(ang))
        p1 = (config.PLAZA_OUTER_R * math.cos(ang), config.PLAZA_OUTER_R * math.sin(ang))
        bow = p4_plaza.BOW_MAGNITUDES[i] * (1.0 if i % 2 == 0 else -1.0)
        lanes.append(_bezier_points(p0, p1, bow))
        cx, cy = config.plot_xy(i)
        lanes.append(_bezier_points(p1, (cx, cy), 0.0, samples=8))
    lanes.append(_bezier_points((config.PLAZA_INNER_R, 0.0),
                                (config.PLAZA_OUTER_R, 0.0),
                                p4_plaza.BOW_MAGNITUDES[7]))
    lanes.append(_bezier_points((p6_gate.FORESHORE_INNER_R, 0.0),
                                (p6_gate.SHORE_R - 2.0, 0.0), -11.0))
    lanes.append(_bezier_points((p6_gate.SHORE_R, 0.0),
                                (p6_gate.BEACH_OUTER_R, 0.0), 0.0, samples=8))
    half = config.SHOP_FOOTPRINT / 2.0
    for ang in (0.0, 90.0, 180.0, 270.0):
        a = math.radians(ang)
        lanes.append(_bezier_points((half * math.cos(a), half * math.sin(a)),
                                    ((half + 26.0) * math.cos(a),
                                     (half + 26.0) * math.sin(a)), 0.0, samples=6))
    return lanes


def in_lane(x, y, lanes, half=None):
    half = LANE_HALF if half is None else half
    p = mathutils.Vector((x, y))
    for line in lanes:
        for i in range(len(line) - 1):
            a, b = line[i], line[i + 1]
            ab = b - a
            L2 = ab.length_squared
            t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
            if (p - (a + ab * t)).length <= half:
                return True
    return False


# ---- zones -----------------------------------------------------------------

def quarter_token(x, y):
    return {"N": "CatchN", "E": "OutfitE", "S": "BallastS",
            "W": "MarketW"}[dd_mood.WarmBudget.district_for(x, y)]


def classify(x, y):
    r = math.hypot(x, y)
    ang = math.degrees(math.atan2(y, x)) % 360.0
    in_gate = ang <= config.GATE_HALF_ANGLE or ang >= 360.0 - config.GATE_HALF_ANGLE

    if PLAZA_OPEN_R[0] <= r < PLAZA_OPEN_R[1]:
        return "plaza_open", quarter_token(x, y)
    if PLAZA_EDGE_R[0] <= r < PLAZA_EDGE_R[1]:
        return "plaza_edge", quarter_token(x, y)
    if DISTRICT_CORE_R[0] <= r < DISTRICT_CORE_R[1]:
        return "district_core", quarter_token(x, y)

    if in_gate:
        if p6_gate.FORESHORE_INNER_R <= r < p6_gate.SHORE_R:
            return "quay_rim", "QuayRim"
        if p6_gate.SHORE_R <= r < p6_gate.BEACH_OUTER_R:
            return "beach", "Beach"
        if p6_gate.BEACH_OUTER_R <= r < p6_gate.BEACH_OUTER_R + 140.0:
            return "underwater_near", "SubNear"
        return None, None

    for i in range(config.PLOT_COUNT):
        d = abs(((ang - config.PLOT_ANGLES_DEG[i] + 180.0) % 360.0) - 180.0)
        if d <= 15.5 and 138.0 <= r <= 210.0:
            return "plot_surround", "PlotSur"
    if 138.0 <= r <= 232.0:
        return "island_rim", "IslandRim"
    return None, None


# ---- anchors ---------------------------------------------------------------

def _polar_xy(angle_deg, radius):
    a = math.radians(angle_deg)
    return radius * math.cos(a), radius * math.sin(a)


def wall_anchors():
    """Against the plaza-facing wall of every enclosure building and Merchant
    Row -- where barrels actually end up, out of the traffic and up against
    something."""
    out = []
    for _name, ang, span, radius, depth, _wh, _rh in p4b_merchant.ENCLOSURE:
        # 9 studs off the wall, not 4: the gable roof oversails its footprint,
        # so a closer anchor settles onto the roof rather than the deck and
        # gets dropped. 13 of 21 were being lost that way.
        stand = radius - depth / 2.0 - 9.0
        n = max(2, int(span / 9.0))
        for k in range(n):
            a = ang - span / 2.0 + span * (k + 0.5) / n
            x, y = _polar_xy(a, stand)
            out.append((x, y, math.radians(a + 180.0), "wall"))
    row_span = math.degrees(config.ROW_LENGTH / config.ROW_RADIUS)
    stand = config.ROW_RADIUS - config.ROW_DEPTH / 2.0 - 4.0
    for k in range(4):
        a = config.ROW_ANGLE_DEG - row_span / 2.0 + row_span * (k + 0.5) / 4
        x, y = _polar_xy(a, stand)
        out.append((x, y, math.radians(a + 180.0), "wall"))
    return out


def structure_anchors():
    """At the foot of built things: the shop's pier corners, the market cross,
    the leaderboard court, the kiosk, the tide pool rim, breakwater roots and
    the dock heads."""
    out = []
    half = config.SHOP_FOOTPRINT / 2.0 + 5.0
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        out.append((sx * half, sy * half, math.atan2(sy, sx), "base"))

    mx, my = p4_plaza.MARKET_CROSS_XY
    out.append((mx + 10.0, my - 4.0, math.atan2(my, mx), "base"))
    lx, ly = _polar_xy(config.LB_COURT_ANGLE, config.LB_COURT_R)
    out.append((lx + 8.0, ly - 12.0, math.radians(config.LB_COURT_ANGLE), "base"))
    out.append((config.KIOSK_XY[0] - 11.0, config.KIOSK_XY[1] - 7.0, 3.1, "base"))

    px, py = config.POOL_XY
    for k in range(3):
        a = math.radians(20.0 + k * 115.0)
        out.append((px + (config.POOL_RADIUS + 6.0) * math.cos(a),
                    py + (config.POOL_RADIUS + 6.0) * math.sin(a), a, "base"))

    for side in (1.0, -1.0):
        cl = p6_gate.breakwater_centreline(side)
        for i in (2, 6, 10):
            p = cl[i]
            out.append((p[0], p[1] - side * (p6_gate.BREAKWATER_LANDWARD_W + 6.0),
                        math.pi, "base"))
        out.append((p6_gate.BEACH_OUTER_R - 10.0,
                    config.DOCK_OFFSET_Y * side - side * 9.0, 0.0, "base"))
    return out


def open_plaza_anchors():
    """The open floor, on the bisector between each adjacent pair of lanes --
    the only line through plaza_open that is maximally far from traffic.

    Hugging the shop wall does not work here. Twelve corridors radiate from
    r=30 (eight lanes plus four arch approaches), and at r=40 their 32-stud
    placement corridors sum to more than the circumference, so the ring around
    the shop is entirely spoken for by circulation. Only 1 of 16 wall-hugging
    anchors survived. Out on the bisectors at r=66..78 there is real room, and
    a scene sitting midway between two paths still reads as deliberately
    placed rather than dropped at random.
    """
    out = []
    gates = sorted(list(config.PLOT_ANGLES_DEG) + [0.0, 360.0])
    for i in range(len(gates) - 1):
        mid = (gates[i] + gates[i + 1]) / 2.0
        for rad in (66.0, 74.0, 78.0):
            x, y = _polar_xy(mid, rad)
            out.append((x, y, math.radians(mid + 180.0), "open"))
    return out


def lane_sign_anchors():
    """Out beyond each lane's carved sign, at the plaza's inner edge. Offset
    far enough round that the sight clearance does not eat them."""
    out = []
    for a in list(config.PLOT_ANGLES_DEG) + [0.0]:
        for s in (1.0, -1.0):
            ang = a + s * 32.0      # the lanes bow up to 14 studs; 26 was too tight
            x, y = _polar_xy(ang, config.PLAZA_INNER_R + 26.0)
            out.append((x, y, math.radians(ang + 180.0), "sign"))
    return out


def plot_terrace_anchors():
    """On each plot's recessed terrace, around the pad. Anchors that land on
    the buildable pad settle onto DD_Plot_Pad_, which is not valid ground, so
    they drop out on their own and the pad stays clear."""
    out = []
    for i in range(config.PLOT_COUNT):
        a = config.PLOT_ANGLES_DEG[i]
        for off_a, rad in ((-12.0, 176.0), (12.0, 176.0), (0.0, 203.0), (-12.0, 200.0)):
            x, y = _polar_xy(a + off_a, rad)
            out.append((x, y, math.radians(a + 180.0), "plot"))
    return out


def foreshore_anchors():
    """The harbour ground either side of the causeway, and around the kiosk."""
    out = []
    for k in range(10):
        a = -config.GATE_HALF_ANGLE + 2 * config.GATE_HALF_ANGLE * (k + 0.5) / 10
        for rad in (p6_gate.SHORE_R - 13.0, p6_gate.FORESHORE_INNER_R + 18.0):
            x, y = _polar_xy(a, rad)
            out.append((x, y, math.radians(a + 180.0), "quay"))
    return out


def beach_anchors():
    """Up the sand either side of the ramp, above the tide line."""
    out = []
    for k in range(8):
        a = -config.GATE_HALF_ANGLE + 2 * config.GATE_HALF_ANGLE * (k + 0.5) / 8
        for rad in (p6_gate.SHORE_R + 16.0, p6_gate.SHORE_R + 44.0):
            x, y = _polar_xy(a, rad)
            out.append((x, y, math.radians(a + 180.0), "beach"))
    return out


def path_bend_anchors():
    """On the outside of each lane's bow. A bend is where a barrow gets parked
    clear of the traffic, so it is a real reason for props to be there."""
    out = []
    for i in range(config.PLOT_COUNT):
        ang = math.radians(config.PLOT_ANGLES_DEG[i])
        p0 = (config.PLAZA_INNER_R * math.cos(ang), config.PLAZA_INNER_R * math.sin(ang))
        p1 = (config.PLAZA_OUTER_R * math.cos(ang), config.PLAZA_OUTER_R * math.sin(ang))
        bow = p4_plaza.BOW_MAGNITUDES[i] * (1.0 if i % 2 == 0 else -1.0)
        pts = _bezier_points(p0, p1, bow, samples=8)
        mid = pts[4]
        tan = (pts[5] - pts[3]).normalized()
        nrm = mathutils.Vector((-tan.y, tan.x))
        for s in (1.0, -1.0):
            q = mid + nrm * (s * (LANE_HALF_PLACEMENT + 3.0))
            out.append((q.x, q.y, math.atan2(-nrm.y * s, -nrm.x * s), "bend"))
    return out


def natural_anchors():
    """Features outside the town: the coastline itself, the shelf lip, the
    dock pilings and the wreck. Without these the rim and the underwater
    near-field would have nothing to anchor to and would simply empty out."""
    out = []
    for k in range(26):
        a = config.GATE_HALF_ANGLE + (360.0 - 2 * config.GATE_HALF_ANGLE) * (k + 0.5) / 26
        r = p2_terrain.coast_radius(a) - 11.0
        x, y = _polar_xy(a, r)
        out.append((x, y, math.radians(a), "coast"))
    for k in range(12):
        a = -config.GATE_HALF_ANGLE + 2 * config.GATE_HALF_ANGLE * (k + 0.5) / 12
        for rad in (p6_gate.BEACH_OUTER_R + 10.0, p6_gate.BEACH_OUTER_R + 62.0,
                    p6_gate.BEACH_OUTER_R + 112.0):
            x, y = _polar_xy(a, rad)
            out.append((x, y, math.radians(a + 180.0), "shelf"))
    for side in (1.0, -1.0):
        for k in range(4):
            out.append((p6_gate.BEACH_OUTER_R + 18.0 + k * 26.0,
                        config.DOCK_OFFSET_Y * side + side * 11.0,
                        math.pi, "piling"))
    out.append((273.0 + 18.0, -63.0 - 12.0, math.pi, "wreck"))
    return out


def signature_anchors():
    """One deliberate scene per quarter -- the thing the district is named
    for, placed rather than sampled."""
    spots = (("CatchN", 100.0, 99.0), ("OutfitE", 350.0, 99.0),
             ("BallastS", 250.0, 99.0), ("MarketW", 172.0, 99.0))
    out = []
    for _tok, ang, rad in spots:
        x, y = _polar_xy(ang, rad)
        out.append((x, y, math.radians(ang + 180.0), "signature"))
    return out


def poisson_disc(rng, x0, x1, y0, y1, radius, tries=18):
    cell = radius / math.sqrt(2)
    gw = int((x1 - x0) / cell) + 1
    gh = int((y1 - y0) / cell) + 1
    grid = [None] * (gw * gh)
    pts, active = [], []

    def gi(p):
        return int((p[0] - x0) / cell) + int((p[1] - y0) / cell) * gw

    def ok(p):
        if not (x0 <= p[0] < x1 and y0 <= p[1] < y1):
            return False
        cx, cy = int((p[0] - x0) / cell), int((p[1] - y0) / cell)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < gw and 0 <= ny < gh:
                    q = grid[nx + ny * gw]
                    if q is not None and math.dist(p, q) < radius:
                        return False
        return True

    seed_pt = (rng.uniform(x0, x1), rng.uniform(y0, y1))
    pts.append(seed_pt)
    active.append(seed_pt)
    grid[gi(seed_pt)] = seed_pt
    while active:
        idx = rng.randrange(len(active))
        base = active[idx]
        placed = False
        for _ in range(tries):
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(radius, 2 * radius)
            cand = (base[0] + math.cos(a) * d, base[1] + math.sin(a) * d)
            if ok(cand):
                pts.append(cand)
                active.append(cand)
                grid[gi(cand)] = cand
                placed = True
                break
        if not placed:
            active.pop(idx)
    return pts


def settle(dg, x, y):
    hit, loc, _n, _i, obj, _m = bpy.context.scene.ray_cast(
        dg, (x, y, SETTLE_FROM_Z), (0, 0, -1))
    if not hit or not obj.name.startswith(GROUND_PREFIXES):
        return None
    return loc.z


# ---- composition -----------------------------------------------------------

def _kit_index():
    kit = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or dd_scene.is_placed_instance(o.name):
            continue
        bits = o.name.split("_")
        if len(bits) == 4 and o.location.x > 800.0:
            kit.setdefault(bits[2], []).append(o)
    for v in kit.values():
        v.sort(key=lambda o: o.name)
    return kit


def compose(rng, district, kit):
    """A lead object plus its clutter. Drawn from the same weighted district
    pools as before, so the districts still read from their signatures."""
    pool = [k for k in (DISTRICT_PROPS.get(district) or ZONE_PROPS.get(district) or [])
            if k in kit and k not in AMBIENT_ASSETS]
    if not pool:
        return None
    leads = [k for k in pool if k in OPEN_ZONE_ASSETS] or pool
    smalls = [k for k in pool if k in SMALL_ASSETS] or pool
    n = rng.randint(config.VIGNETTE_MIN_PROPS, config.VIGNETTE_MAX_PROPS)
    return [rng.choice(leads)] + [rng.choice(smalls) for _ in range(n - 1)]


def member_offsets(rng, n):
    """Positions within one vignette: the lead at the anchor, the rest packed
    around it no closer than VIGNETTE_SPACING."""
    pts = [(0.0, 0.0)]
    guard = 0
    while len(pts) < n and guard < 240:
        guard += 1
        a = rng.uniform(0.0, 2 * math.pi)
        d = rng.uniform(config.VIGNETTE_SPACING, VIGNETTE_RADIUS)
        p = (math.cos(a) * d, math.sin(a) * d)
        if all(math.dist(p, q) >= config.VIGNETTE_SPACING for q in pts):
            pts.append(p)
    return pts


def _pick_yaw(rng, base, spread, mesh_name, x, y, per_mesh):
    near = [e for e in per_mesh.get(mesh_name, [])
            if math.dist((x, y), (e[0], e[1])) < 40.0]
    for _ in range(24):
        yaw = base + rng.uniform(-spread, spread)
        if all(abs(math.degrees(_ang_diff(yaw, e[2]))) > 5.0 for e in near):
            return yaw
    return None


def _ang_diff(a, b):
    d = (a - b) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


def _wind_lean(yaw):
    lean = mathutils.Matrix.Rotation(-math.radians(config.WIND_LEAN_DEG), 3, "Y")
    spin = mathutils.Matrix.Rotation(yaw, 3, "Z")
    return (lean @ spin).to_euler()


def _collection_for(name):
    for prefix, coll in (("DD_Nature_", "Nature"), ("DD_Sub_", "Underwater"),
                         ("DD_Lore_", "Lore"), ("DD_Overhead_", "Overhead")):
        if name.startswith(prefix):
            return coll
    return "Props"


# ---- build -----------------------------------------------------------------

def build():
    import random

    dd_scene.ensure_collections()
    purge()
    rng = random.Random(config.SCATTER_SEED)
    lanes = lane_centrelines()
    warm = dd_mood.WarmBudget(config.WARM_ACCENT_MAX_PER_DISTRICT)
    kit = _kit_index()
    dg = bpy.context.evaluated_depsgraph_get()

    feature = (wall_anchors() + structure_anchors() + open_plaza_anchors()
               + lane_sign_anchors() + plot_terrace_anchors() + foreshore_anchors()
               + beach_anchors() + path_bend_anchors() + natural_anchors()
               + signature_anchors())
    rng.shuffle(feature)
    n_free = int(round(len(feature) * (1.0 - config.VIGNETTE_ANCHOR_BIAS)
                       / config.VIGNETTE_ANCHOR_BIAS))
    free_pts = poisson_disc(rng, -240.0, 450.0, -240.0, 240.0, ANCHOR_MIN_GAP)
    rng.shuffle(free_pts)
    free = [(x, y, rng.uniform(0.0, 2 * math.pi), "free") for x, y in free_pts[:n_free]]
    anchors = feature + free
    rng.shuffle(anchors)

    max_density = max(config.ZONE_DENSITY.values())
    placed, placed_xy = [], []
    per_mesh, counts, kinds = {}, {}, {}
    index = 0
    dropped_gap = 0

    for (ax, ay, facing, kind) in anchors:
        zone, district = classify(ax, ay)
        if zone is None:
            continue
        density = config.ZONE_DENSITY.get(zone, 0.0)
        if density <= 0.0 or rng.random() > density / max_density:
            continue
        if in_lane(ax, ay, lanes, LANE_HALF_PLACEMENT):
            continue

        assets = compose(rng, district, kit)
        if not assets:
            continue
        offsets = member_offsets(rng, len(assets))

        # settle and vet the whole vignette before committing any of it
        members = []
        for asset, (ox, oy) in zip(assets, offsets):
            mx, my = ax + ox, ay + oy
            if in_lane(mx, my, lanes, LANE_HALF_PLACEMENT):
                members = []
                break
            mz = settle(dg, mx, my)
            if mz is None:
                members = []
                break
            members.append((asset, mx, my, mz))
        if len(members) < config.VIGNETTE_MIN_PROPS:
            continue
        if any(math.dist((m[1], m[2]), q) < config.VIGNETTE_GAP_MIN
               for m in members for q in placed_xy):
            dropped_gap += 1
            continue

        for asset, mx, my, mz in members:
            variants = kit[asset]
            choice = rng.randrange(len(variants))
            if asset in WARM_ASSETS and choice in WARM_ASSETS[asset]:
                if not warm.take(dd_mood.WarmBudget.district_for(mx, my)):
                    choice = 0
            src = variants[choice]

            if asset in ORIENTED:
                base_yaw = facing
            else:
                base_yaw = rng.uniform(0.0, 2 * math.pi)
            yaw = _pick_yaw(rng, base_yaw, math.radians(config.SCATTER_ROT_JITTER),
                            src.name, mx, my, per_mesh)
            if yaw is None:
                continue

            obj = bpy.data.objects.new(f"{src.name}.{district}.{index:03d}", src.data)
            s = 1.0 + rng.uniform(-config.SCATTER_SCALE_JITTER, config.SCATTER_SCALE_JITTER)
            obj.scale = (s, s, s)
            obj.location = (mx, my, mz + config.SCATTER_SINK)
            obj.rotation_euler = (_wind_lean(yaw) if src.name.startswith("DD_Nature_")
                                  else (0.0, 0.0, yaw))
            bpy.context.scene.collection.objects.link(obj)
            dd_scene.link_to_collection(obj, _collection_for(src.name))
            per_mesh.setdefault(src.name, []).append((mx, my, yaw))
            placed_xy.append((mx, my))
            placed.append(obj)
            index += 1
        counts[zone] = counts.get(zone, 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1

    ambient = _ambient_pass(rng, lanes, kit, dg, per_mesh, index)
    placed += ambient

    n_vig = sum(counts.values())
    feature_used = sum(v for k, v in kinds.items() if k != "free")
    print(f"placed {len(placed)} instances in {n_vig} vignettes "
          f"(+{len(ambient)} ambient ground cover)")
    print(f"   vignettes per zone: {dict(sorted(counts.items()))}")
    print(f"   anchor kinds: {dict(sorted(kinds.items()))}")
    print(f"   feature-anchored: {feature_used}/{n_vig} = "
          f"{feature_used / max(n_vig, 1):.0%} (target {config.VIGNETTE_ANCHOR_BIAS:.0%})")
    print(f"   vignettes dropped for gap: {dropped_gap}")
    print(f"   warm accents: {warm.report()} (cap {config.WARM_ACCENT_MAX_PER_DISTRICT}/quarter)")
    return placed


def _ambient_pass(rng, lanes, kit, dg, per_mesh, index):
    """Sea grass and heather only, and only outside the town. Everything with
    mass belongs to a vignette; this is ground cover, which is the one thing
    that genuinely does occur independently."""
    made = []
    pts = poisson_disc(rng, -240.0, 450.0, -240.0, 240.0, config.SCATTER_MIN_SPACING)
    rng.shuffle(pts)
    max_density = max(config.ZONE_DENSITY.values())
    for (x, y) in pts:
        zone, district = classify(x, y)
        if zone not in AMBIENT_ZONES:
            continue
        pool = [k for k in (ZONE_PROPS.get(district) or []) if k in AMBIENT_ASSETS and k in kit]
        if not pool:
            continue
        if rng.random() > (config.ZONE_DENSITY[zone] / max_density) * 0.35:
            continue
        if in_lane(x, y, lanes, LANE_HALF_PLACEMENT):
            continue
        z = settle(dg, x, y)
        if z is None:
            continue
        variants = kit[rng.choice(pool)]
        src = variants[rng.randrange(len(variants))]
        yaw = _pick_yaw(rng, rng.uniform(0.0, 2 * math.pi),
                        math.radians(config.SCATTER_ROT_JITTER),
                        src.name, x, y, per_mesh)
        if yaw is None:
            continue
        obj = bpy.data.objects.new(f"{src.name}.{district}.{index + len(made):03d}", src.data)
        s = 1.0 + rng.uniform(-config.SCATTER_SCALE_JITTER, config.SCATTER_SCALE_JITTER)
        obj.scale = (s, s, s)
        obj.location = (x, y, z + config.SCATTER_SINK)
        obj.rotation_euler = _wind_lean(yaw)
        bpy.context.scene.collection.objects.link(obj)
        dd_scene.link_to_collection(obj, _collection_for(src.name))
        per_mesh.setdefault(src.name, []).append((x, y, yaw))
        made.append(obj)
    return made


# ---- acceptance ------------------------------------------------------------

def _obstructs_at_walk_height(obj, lanes):
    mw = obj.matrix_world
    base_z = obj.location.z
    for v in obj.data.vertices:
        p = mw @ v.co
        if p.z - base_z <= WALK_HEIGHT and in_lane(p.x, p.y, lanes):
            return True
    return False


def acceptance():
    lanes = lane_centrelines()
    inst = [o for o in bpy.data.objects if dd_scene.is_placed_instance(o.name)]

    in_lanes = []
    for o in inst:
        if o.name.startswith("DD_Overhead_"):
            continue
        if not in_lane(o.location.x, o.location.y, lanes):
            continue
        if _obstructs_at_walk_height(o, lanes):
            in_lanes.append(o)
    print(f"[15] props inside a traffic lane: {len(in_lanes)} "
          f"({'OK' if not in_lanes else 'FAIL'})")

    floating = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in inst:
        hit, loc, _n, _i, hobj, _m = bpy.context.scene.ray_cast(
            dg, (o.location.x, o.location.y, SETTLE_FROM_Z), (0, 0, -1))
        if hit and hobj.name.startswith(GROUND_PREFIXES):
            if abs(o.location.z - config.SCATTER_SINK - loc.z) > 0.3:
                floating.append(o.name)
    print(f"[16] floating props: {len(floating)} ({'OK' if not floating else 'FAIL'})")

    total = clear = 0
    occupied = [(o.location.x, o.location.y) for o in inst]
    for ri in range(24):
        r = 32.0 + ri * (config.PLAZA_OUTER_R - 34.0) / 23.0
        for ai in range(90):
            a = math.radians(ai * 4.0)
            x, y = r * math.cos(a), r * math.sin(a)
            total += 1
            if not any(math.dist((x, y), p) < 3.0 for p in occupied):
                clear += 1
    frac = clear / total
    print(f"[18] plaza empty floor {frac:.1%} (need >= {config.PLAZA_MIN_EMPTY:.0%}) "
          f"{'OK' if frac >= config.PLAZA_MIN_EMPTY else 'FAIL'}")

    quarters = {}
    for o in inst:
        q = dd_mood.WarmBudget.district_for(o.location.x, o.location.y)
        quarters[q] = quarters.get(q, 0) + 1
    print(f"[20] per-quarter instance counts: {quarters}")
    print("[19] overhead sites: deferred to Phase 7c, which owns the rope lines")
    return len(in_lanes) == 0 and not floating and frac >= config.PLAZA_MIN_EMPTY


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)
    dd_palette.apply_debug_colors([o for o in bpy.data.objects if o.name.startswith("DD_")])

    top = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=520.0, height=700.0)
    dd_scene.render_to_file(top, os.path.join(renders_dir, "p7b_top_ortho.png"))

    for label, ang in (("catch_n", 100.0), ("outfit_e", 20.0),
                       ("ballast_s", 250.0), ("market_w", 172.0)):
        a = math.radians(ang)
        cam = dd_scene.setup_eye_camera(
            f"RenderCam_Q_{label}",
            location=(44.0 * math.cos(a), 44.0 * math.sin(a), config.PLAZA_LIFT + 5.5),
            facing_deg=ang, fov_deg=75.0)
        dd_scene.render_to_file(cam, os.path.join(renders_dir, f"p7b_{label}.png"))


if __name__ == "__main__":
    build()
    acceptance()
    capture_renders()
