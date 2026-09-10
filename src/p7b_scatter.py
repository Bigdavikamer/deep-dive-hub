"""Phase 7b -- Zones, lanes, seeded scatter.

Turns the 91 kit meshes into the placed dressing: zone polygons, traffic lanes
subtracted BEFORE sampling, seeded Poisson-disc points, district-weighted prop
choice, jitter, and a raycast settle so nothing floats.

LANES ARE SUBTRACTED FIRST, not audited afterwards. CLAUDE.md lists "dressing
in the walking lanes" as the fastest way to make a beautiful map feel bad to
play, and a prop that has already been placed is one you have to notice before
you can remove it. Lane centrelines are not approximated here either: the
plaza paths bow 8-14 studs off the radial line, so this module recomputes the
exact quadratic Bezier p4_plaza used and imports that module's own
BOW_MAGNITUDES rather than keeping a second copy of them.

DENSITY VARIES SHARPLY, which is the difference between a lived-in town and
evenly-sprinkled noise. One Poisson-disc set is generated at
SCATTER_MIN_SPACING -- guaranteeing the minimum gap between every pair of
props regardless of zone -- and then thinned per zone to the rates in
ZONE_DENSITY. Thinning only ever removes points, so the spacing guarantee
survives it.

LINKED MESH DATA THROUGHOUT. Every instance is bpy.data.objects.new(name,
source.data): one barrel mesh backing thirty objects becomes one MeshId in
Studio. Copying instead would mean ~450 datablocks, ~450 uploads and an import
that crawls.

ANTI-REPETITION IS ENFORCED, NOT HOPED FOR. validate.py check 12 forbids two
instances of one mesh within 40 studs sharing a rotation within 5 degrees.
A plain +/-SCATTER_ROT_JITTER wobble cannot satisfy that -- a 30-degree band
holds only about six distinct 5-degree slots, so any tight cluster of one prop
violates it. Props with no canonical facing therefore take a full-circle base
yaw and use SCATTER_ROT_JITTER as the floor on variation; props that read
front-on (stalls, racks, boards) keep a meaningful facing and jitter around
it. Either way the yaw is re-rolled against nearby same-mesh instances and the
point is dropped rather than placed in violation.

Deferred to Phase 7c, which owns them: the overhead rope lines, the fossil
arch, trophy rack, dive-log wall, shrine, hull under repair, the two pines,
and the story props with fixed intent (boots at the dock, chair facing the
sea). So the "three layers in every quarter" and "overhead at >= 4 sites"
acceptance checks are answered after 7c, not here; this phase reports them as
pending rather than passing them silently.

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
import p4_plaza
import p6_gate
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import parts as P
from lib import scene as dd_scene

LANE_HALF = config.TRAFFIC_LANE_WIDTH / 2.0 + config.LANE_CLEARANCE
SETTLE_FROM_Z = 120.0

# Surfaces a prop may stand on; anything else under the ray means "no", which
# is what keeps props off building roofs for free.
#
# DD_Plot_Pad_ is deliberately NOT here. The plot_surround zone spans the whole
# recessed terrace, r 138..210, and the 70x70 pad sits inside that -- so
# treating the pad as valid ground scattered barrels across the squares players
# are supposed to build on. Excluding it leaves the surround dressed and the
# pad itself clear, which is what "plot_surround" was always meant to mean.
GROUND_PREFIXES = ("DD_Terrain_", "DD_Struct_Plaza", "DD_Struct_Path_",
                   "DD_Struct_Foreshore")

# ---- zones -----------------------------------------------------------------
# (name, density key, district token)
PLAZA_OPEN_R = (32.0, 80.0)
PLAZA_EDGE_R = (80.0, 104.0)
DISTRICT_CORE_R = (104.0, 133.0)

# Pools are WEIGHTED by repetition, because a quarter has to be identifiable
# from one unlabelled render. Drawing uniformly from a flat list left the N
# quarter's signature drying racks absent altogether on the first run -- with
# nine equally likely assets over ~35 plaza slots, a 1-in-60 miss is a coin
# flip you should not be taking with the thing that names the district.
# LanternPost carries the mid layer in every quarter; it was in no pool at all.
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

# props that read front-on: they keep a facing and only wobble around it
ORIENTED = {"MarketStall", "NoticeBoard", "DryingRack", "TallyBoard", "Awning",
            "GuttingTable", "Well", "Rowboat", "BannerPole"}
# whole-object cloth that the warm ration governs
WARM_ASSETS = {"MarketStall": (1, 2), "Awning": (1,), "BannerPole": (1, 2)}


def purge():
    doomed = [o for o in bpy.data.objects
              if o.name.startswith("DD_") and dd_scene.is_placed_instance(o.name)]
    for o in doomed:
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
        # the plot's own footpath: entrance stair out across the pocket
        cx, cy = config.plot_xy(i)
        lanes.append(_bezier_points(p1, (cx, cy), 0.0, samples=8))
    lanes.append(_bezier_points((config.PLAZA_INNER_R, 0.0),
                                (config.PLAZA_OUTER_R, 0.0),
                                p4_plaza.BOW_MAGNITUDES[7]))
    lanes.append(_bezier_points((p6_gate.FORESHORE_INNER_R, 0.0),
                                (p6_gate.SHORE_R - 2.0, 0.0), -11.0))
    # beach ramp, straight out the axis to the dock line
    lanes.append(_bezier_points((p6_gate.SHORE_R, 0.0),
                                (p6_gate.BEACH_OUTER_R, 0.0), 0.0, samples=8))
    # four shop entrances
    half = config.SHOP_FOOTPRINT / 2.0
    for ang in (0.0, 90.0, 180.0, 270.0):
        a = math.radians(ang)
        lanes.append(_bezier_points((half * math.cos(a), half * math.sin(a)),
                                    ((half + 26.0) * math.cos(a),
                                     (half + 26.0) * math.sin(a)), 0.0, samples=6))
    return lanes


def in_lane(x, y, lanes):
    p = mathutils.Vector((x, y))
    for line in lanes:
        for i in range(len(line) - 1):
            a, b = line[i], line[i + 1]
            ab = b - a
            L2 = ab.length_squared
            t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / L2))
            if (p - (a + ab * t)).length <= LANE_HALF:
                return True
    return False


# ---- zone classification ---------------------------------------------------

def quarter_token(x, y):
    return {"N": "CatchN", "E": "OutfitE", "S": "BallastS",
            "W": "MarketW"}[dd_mood.WarmBudget.district_for(x, y)]


def classify(x, y):
    """Zone key and district token for a point, or (None, None)."""
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

    # outside the plaza on the island: plot terraces vs the open rim
    for i in range(config.PLOT_COUNT):
        d = abs(((ang - config.PLOT_ANGLES_DEG[i] + 180.0) % 360.0) - 180.0)
        if d <= 15.5 and 138.0 <= r <= 210.0:
            return "plot_surround", "PlotSur"
    if 138.0 <= r <= 232.0:
        return "island_rim", "IslandRim"
    return None, None


# ---- sampling --------------------------------------------------------------

def poisson_disc(rng, x0, x1, y0, y1, radius, tries=18):
    """Bridson. One set for the whole map at SCATTER_MIN_SPACING, thinned per
    zone afterwards -- so the minimum gap holds between every pair of props
    regardless of which zones they landed in."""
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
    """Raycast down to real ground. Every candidate is settled BEFORE anything
    is placed, so a prop can never land on another prop -- interleaving the two
    also biases the scatter, because a ray blocked by an existing prop drops
    that point and thins the area around whatever was placed first. A hit on a
    building means the point is inside its footprint, and is dropped."""
    hit, loc, _n, _i, obj, _m = bpy.context.scene.ray_cast(
        dg, (x, y, SETTLE_FROM_Z), (0, 0, -1))
    if not hit:
        return None
    if not obj.name.startswith(GROUND_PREFIXES):
        return None
    return loc.z


# ---- placement -------------------------------------------------------------

def build():
    import random

    dd_scene.ensure_collections()
    purge()
    rng = random.Random(config.SCATTER_SEED)
    lanes = lane_centrelines()
    warm = dd_mood.WarmBudget(config.WARM_ACCENT_MAX_PER_DISTRICT)

    kit = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or dd_scene.is_placed_instance(o.name):
            continue
        bits = o.name.split("_")
        if len(bits) == 4 and o.location.x > 800.0:
            kit.setdefault(bits[2], []).append(o)
    for v in kit.values():
        v.sort(key=lambda o: o.name)

    x0, x1, y0, y1 = -250.0, 460.0, -250.0, 250.0
    pts = poisson_disc(rng, x0, x1, y0, y1, config.SCATTER_MIN_SPACING)
    rng.shuffle(pts)

    # Thin against the sample set's ACTUAL density, not against the largest
    # ZONE_DENSITY entry. A Poisson-disc set at SCATTER_MIN_SPACING packs far
    # denser than any zone asks for, so normalising by max(ZONE_DENSITY) placed
    # every zone about 1.7x over its specified rate.
    available = len(pts) / ((x1 - x0) * (y1 - y0)) * 1000.0
    print(f"poisson set: {len(pts)} pts = {available:.1f} per 1000 sq studs")

    # Pass 1: settle every candidate while the scene still holds no props.
    dg = bpy.context.evaluated_depsgraph_get()
    accepted = []
    for (x, y) in pts:
        zone, district = classify(x, y)
        if zone is None or district is None:
            continue
        density = config.ZONE_DENSITY.get(zone, 0.0)
        if density <= 0.0 or rng.random() > density / available:
            continue
        if in_lane(x, y, lanes):
            continue
        z = settle(dg, x, y)
        if z is not None:
            accepted.append((x, y, z, zone, district))

    placed, counts, per_mesh = [], {}, {}
    index = 0

    # Pass 2: place.
    for (x, y, z, zone, district) in accepted:
        pool = DISTRICT_PROPS.get(district) or ZONE_PROPS.get(district) or []
        pool = [k for k in pool if k in kit]
        if not pool:
            continue
        asset = rng.choice(pool)

        variants = kit[asset]
        choice = rng.randrange(len(variants))
        warm_ok = True
        if asset in WARM_ASSETS and choice in WARM_ASSETS[asset]:
            warm_ok = warm.take(dd_mood.WarmBudget.district_for(x, y))
            if not warm_ok:
                choice = 0                      # fall through to the cool default
        src = variants[choice]

        if asset in ORIENTED:
            base_yaw = math.atan2(-y, -x)       # face the plaza centre
            spread = math.radians(config.SCATTER_ROT_JITTER)
        else:
            base_yaw = rng.uniform(0.0, 2 * math.pi)
            spread = math.radians(config.SCATTER_ROT_JITTER)

        yaw = _pick_yaw(rng, base_yaw, spread, src.name, x, y, per_mesh)
        if yaw is None:
            continue

        name = f"{src.name}.{district}.{index:03d}"
        obj = bpy.data.objects.new(name, src.data)      # LINKED, never copied
        s = 1.0 + rng.uniform(-config.SCATTER_SCALE_JITTER, config.SCATTER_SCALE_JITTER)
        obj.scale = (s, s, s)
        obj.location = (x, y, z + config.SCATTER_SINK)

        if src.name.startswith("DD_Nature_"):
            obj.rotation_euler = _wind_lean(yaw)
        else:
            obj.rotation_euler = (0.0, 0.0, yaw)

        bpy.context.scene.collection.objects.link(obj)
        dd_scene.link_to_collection(obj, _collection_for(src.name))
        per_mesh.setdefault(src.name, []).append((x, y, yaw))
        counts[zone] = counts.get(zone, 0) + 1
        placed.append(obj)
        index += 1

    print(f"placed {len(placed)} instances from {sum(len(v) for v in kit.values())} kit meshes")
    for k in sorted(counts):
        print(f"   {k:16s} {counts[k]:4d}")
    print(f"   warm accents: {warm.report()} (cap {config.WARM_ACCENT_MAX_PER_DISTRICT}/quarter)")
    return placed


def _pick_yaw(rng, base, spread, mesh_name, x, y, per_mesh):
    """Re-roll until this yaw differs by >5 degrees from every instance of the
    same mesh within 40 studs. Returns None if it cannot, in which case the
    caller drops the point -- a slightly thinner cluster beats a check-12
    violation."""
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
    """Vegetation leans WIND_LEAN_DEG away from the ocean, which is +X. The
    lean is applied about global Y AFTER the yaw, so every plant leans the same
    way regardless of how it is spun -- composing it as a plain Euler would
    rotate the lean axis with the yaw and scatter the direction."""
    lean = mathutils.Matrix.Rotation(-math.radians(config.WIND_LEAN_DEG), 3, "Y")
    spin = mathutils.Matrix.Rotation(yaw, 3, "Z")
    return (lean @ spin).to_euler()


def _collection_for(name):
    if name.startswith("DD_Nature_"):
        return "Nature"
    if name.startswith("DD_Sub_"):
        return "Underwater"
    if name.startswith("DD_Lore_"):
        return "Lore"
    if name.startswith("DD_Overhead_"):
        return "Overhead"
    return "Props"


# ---- acceptance ------------------------------------------------------------

WALK_HEIGHT = 6.0


def _obstructs_at_walk_height(obj, lanes):
    """True if any of the object's geometry below WALK_HEIGHT lies inside a
    lane corridor. An arch you walk through has all its low geometry outside
    the corridor even though its centre is on the path."""
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

    # The rule exists so nothing obstructs a walking player, so the test is
    # whether an object's geometry BELOW head height sits in the corridor --
    # not whether its origin does. A rope line strung 14 studs up crosses a
    # lane by design, and the fossil arch straddles one on purpose with its
    # legs outside it; both would fail an origin-only test while leaving the
    # walk completely clear. The cheap origin test still runs first and only
    # objects it flags pay for the per-vertex check.
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

    # plaza empty floor
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

    for label, ang in (("catch_n", 96.8), ("outfit_e", 20.0),
                       ("ballast_s", 263.2), ("market_w", 180.0)):
        a = math.radians(ang)
        cam = dd_scene.setup_eye_camera(
            f"RenderCam_Q_{label}",
            location=(72.0 * math.cos(a), 72.0 * math.sin(a), config.PLAZA_LIFT + 5.0),
            facing_deg=ang, fov_deg=75.0)
        dd_scene.render_to_file(cam, os.path.join(renders_dir, f"p7b_{label}.png"))


if __name__ == "__main__":
    build()
    acceptance()
    capture_renders()
