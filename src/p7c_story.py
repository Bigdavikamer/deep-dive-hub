"""Phase 7c -- Hand-placed storytelling.

Scatter cannot do intent. Everything here has an answer to "who put this here,
and why", and every position is explicit rather than sampled: the overhead rope
lines, the fossil jaw arch, the trophy rack, the dive-log wall, the ex-voto
shrine, the hull under repair, the two wind-bent pines, the chair facing the
sea, the boots at the dock, the tide-line barnacle rings and the wheel ruts.

It also closes three things earlier phases left open:

  THE FIFTH LIT SITE. dock_north_head is the last entry in LIT_LANTERN_SITES
  without an object. It belongs to the Deckhand's post -- the first NPC a new
  player meets -- so the lantern arrives here together with the rope coil and
  the crate to sit on that make the spot read as somebody's station rather than
  a marker.

  THE OVERHEAD LAYER. Phase 7b placed ground and mid only. Rope lines need two
  anchor points and a reason, so they are strung here, one per plaza quarter,
  which satisfies OVERHEAD_MIN_SITES and completes the three-layer rule.

  THE TIDE LINE. Barnacle and algae banding at a fixed Z, on the shore arc and
  around both breakwater roots. Applied consistently at WATERLINE_Z it is the
  cheapest thing in the build that makes the coast read as real.

Placement style: anything with a kit mesh is a LINKED instance named
<kit>.<Site>.<nn>, so it shares the datablock and satisfies check 17 exactly as
the scatter does. Only genuinely unique geometry -- the dive-log wall, the tide
line, the wheel ruts, the mooring stones, the Deckhand's lantern -- is authored
here as its own mesh.

Idempotent: purges the story instances and unique objects it owns.
"""
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bmesh
import bpy
import mathutils

import config
import p6_gate
from lib import mesh as dd_mesh
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import parts as P
from lib import scene as dd_scene

DECK_Z = config.PLAZA_LIFT
WATERLINE_Z = p6_gate.WATERLINE_Z

# Site tokens must NOT collide with the district/zone tokens p7b_scatter uses
# (CatchN, OutfitE, BallastS, MarketW, QuayRim, Beach, PlotSur, SubNear,
# IslandRim). purge() deletes placed instances by site token, so reusing the
# district names here quietly wiped every plaza prop the scatter had just
# placed -- the plaza read as 99.6% empty and the three-layer check collapsed.
STORY_SITES = ("Gate", "ShopN", "ShopE", "RimW", "YardS", "DockN", "Tide",
               "Ruts", "Pool", "RopeN", "RopeE", "RopeS", "RopeW")

OWNED_UNIQUE = [
    "DD_Lore_DiveLogWall",
    "DD_Struct_TideLine",
    "DD_Struct_WheelRut",
    "DD_Struct_MooringStone",
    "DD_Lamp_DockNorthHead",
]

# Rope lines, one per quarter: (site token, angle, radius, yaw offset)
ROPE_LINE_SITES = [
    ("RopeN", 88.0, 96.0, 0.0),
    ("RopeE", 12.0, 98.0, 0.0),
    ("RopeS", 250.0, 97.0, 0.0),
    ("RopeW", 172.0, 96.0, 0.0),
]


def purge():
    for o in [o for o in bpy.data.objects
              if dd_scene.is_placed_instance(o.name)
              and o.name.split(".")[1] in STORY_SITES]:
        bpy.data.objects.remove(o, do_unlink=True)
    for prefix in OWNED_UNIQUE:
        dd_scene.purge_by_prefix(prefix)


def _kit(name):
    o = bpy.data.objects.get(name)
    if o is None or o.location.x < 800.0:
        raise KeyError(f"kit mesh {name} missing -- run p7a_kit first")
    return o


def _place(kit_name, site, index, xy, z=None, yaw=0.0, lean=False, settle=True):
    """One linked instance of a kit mesh at an explicit spot."""
    src = _kit(kit_name)
    x, y = xy
    if z is None:
        z = _ground(x, y) if settle else 0.0
        if z is None:
            print(f"   !! no ground under {kit_name} at ({x:.0f},{y:.0f}) -- skipped")
            return None
        z += config.SCATTER_SINK
    obj = bpy.data.objects.new(f"{src.name}.{site}.{index:03d}", src.data)
    obj.location = (x, y, z)
    if lean:
        m = (mathutils.Matrix.Rotation(-math.radians(config.WIND_LEAN_DEG), 3, "Y")
             @ mathutils.Matrix.Rotation(yaw, 3, "Z"))
        obj.rotation_euler = m.to_euler()
    else:
        obj.rotation_euler = (0.0, 0.0, yaw)
    bpy.context.scene.collection.objects.link(obj)
    dd_scene.link_to_collection(obj, _collection_for(src.name))
    return obj


def _collection_for(name):
    for prefix, coll in (("DD_Nature_", "Nature"), ("DD_Sub_", "Underwater"),
                         ("DD_Lore_", "Lore"), ("DD_Overhead_", "Overhead")):
        if name.startswith(prefix):
            return coll
    return "Props"


def _ground(x, y):
    """Real ground under a point, ducking past any scatter props in the way.

    Phase 7b has already dressed these areas, so a single downward ray very
    often lands on a barrel rather than the terrain. Rejecting that hit outright
    made legitimate spots unplaceable -- the mug beside the chair on the rim
    simply vanished -- so instead the ray restarts just below each prop it meets
    and keeps looking for a surface that can actually carry weight."""
    dg = bpy.context.evaluated_depsgraph_get()
    z = 140.0
    for _ in range(10):
        hit, loc, _n, _i, obj, _m = bpy.context.scene.ray_cast(dg, (x, y, z), (0, 0, -1))
        if not hit:
            return None
        if obj.name.startswith(("DD_Prop_", "DD_Nature_", "DD_Sub_", "DD_Lore_",
                                "DD_Overhead_")):
            z = loc.z - 0.05
            continue
        return loc.z
    return None


def _polar(angle_deg, radius):
    a = math.radians(angle_deg)
    return (radius * math.cos(a), radius * math.sin(a))


def _emit(name, bm, collection):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    obj = dd_mesh.bm_to_object(name, bm)
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, collection)
    return obj


# ---- the set pieces --------------------------------------------------------

def place_fossil_arch():
    """The threshold. Straddles the gate lane at the head of the beach ramp so
    every dive passes through it -- the legs sit outside the corridor, the walk
    goes between them."""
    return _place("DD_Lore_FossilArch_A", "Gate", 0, (p6_gate.SHORE_R - 4.0, 0.0),
                  yaw=math.radians(90.0))


def place_trophy_rack():
    """Outside the shop's north face, offset clear of the entrance lane. Some
    mounts are deliberately empty with only a name plate."""
    return _place("DD_Lore_TrophyRack_A", "ShopN", 0, (-15.0, 33.0),
                  yaw=math.radians(-90.0))


def build_dive_log_wall():
    """Under the shop's east arch: carved boards, depth marks, names. Unique
    geometry -- there is one of these and it is specific to that wall."""
    bm = bmesh.new()
    x = config.SHOP_FOOTPRINT / 2.0 - 3.0
    P.box(bm, (x, -10.0, DECK_Z + 4.5), (1.2, 14.0, 9.0))
    for k in range(6):                       # carved boards, depth marks
        P.box(bm, (x - 0.9, -15.0 + k * 2.1, DECK_Z + 2.2 + (k % 3) * 2.4),
              (0.5, 1.7, 1.5))
    P.box(bm, (x - 0.6, -10.0, DECK_Z + 9.4), (1.8, 15.0, 0.7))
    return _emit("DD_Lore_DiveLogWall", bm, "Lore")


def place_shrine_and_jars():
    """Ex-voto shrine on the west rim beside the tide pool, for divers who did
    not surface; specimen jars inside the shop and in the Assayer's bay."""
    made = [_place("DD_Lore_Shrine_A", "RimW", 0, _polar(150.0, 203.0),
                   yaw=math.radians(-30.0))]
    # (12,14), not (-20,18): the latter sat 3.1 studs off the inner end of the
    # Plot 3 lane, where it leaves the shop. This spot clears every lane mouth
    # and still reads as the Curator's shelf inside the north arch.
    made.append(_place("DD_Lore_JarShelf_A", "ShopN", 1, (12.0, 14.0),
                       z=DECK_Z, yaw=math.radians(200.0), settle=False))
    row_a = math.radians(config.ROW_ANGLE_DEG)
    rx = (config.ROW_RADIUS + config.ROW_DEPTH / 2.0 - 4.0)
    made.append(_place("DD_Lore_JarShelf_B", "OutfitE", 0,
                       (rx * math.cos(row_a), rx * math.sin(row_a)),
                       z=DECK_Z, yaw=row_a + math.pi, settle=False))
    return [m for m in made if m]


def place_hull_and_yard():
    """The S district centrepiece, out on the rim between plots 6 and 7 where
    there is room for a 14-stud hull, with its trestles and tools around it."""
    site = _polar(284.0, 155.0)
    made = [_place("DD_Prop_HullRepair_A", "YardS", 0, site,
                   yaw=math.radians(284.0 + 90.0))]
    for i, (asset, off) in enumerate((("DD_Prop_Sawhorse_A", (14.0, 6.0)),
                                      ("DD_Prop_Tool_A", (10.0, -8.0)),
                                      ("DD_Prop_TimberStack_B", (-13.0, -9.0)),
                                      ("DD_Prop_Tool_C", (-8.0, 8.0)))):
        made.append(_place(asset, "YardS", i + 1,
                           (site[0] + off[0], site[1] + off[1]),
                           yaw=math.radians(30.0 * i)))
    return [m for m in made if m]


def place_pines():
    """Exactly two, west rim, both leaning inland. The lean comes from the
    placement rotation so it tracks WIND_LEAN_DEG."""
    made = []
    for i, (ang, rad, yaw) in enumerate(((151.0, 208.0, 0.4), (166.0, 214.0, 2.1))):
        made.append(_place(f"DD_Nature_Pine_{'AB'[i]}", "RimW", 10 + i,
                           _polar(ang, rad), yaw=yaw, lean=True))
    return [m for m in made if m]


def place_chair_and_boots():
    """A chair on the rim facing the sea with a mug beside it, and boots left
    at the top of the dock ramp pointing at the water. Both are somebody's
    afternoon, not decoration."""
    made = []
    chair = _polar(29.0, 224.0)
    made.append(_place("DD_Prop_Story_C", "RimW", 20, chair, yaw=math.radians(29.0)))
    made.append(_place("DD_Prop_Story_B", "RimW", 21,
                       (chair[0] - 2.4, chair[1] - 2.0), yaw=0.6))
    made.append(_place("DD_Prop_Story_A", "DockN", 0,
                       (p6_gate.BEACH_OUTER_R - 5.0, config.DOCK_OFFSET_Y + 3.0),
                       yaw=0.0))
    return [m for m in made if m]


def build_deckhand_post():
    """The Deckhand's station at the head of the north dock, and with it the
    fifth and last lit site. The lantern is modelled exactly like every other
    in the kit; only its glass material differs."""
    x = p6_gate.BEACH_OUTER_R + 6.0
    y = config.DOCK_OFFSET_Y
    z = config.BEACH_DROP

    bm = bmesh.new()
    P.cylinder(bm, (x, y - 4.0, z + 3.0), 0.35, 6.0, segments=6)
    P.box(bm, (x, y - 4.0, z + 5.6), (1.9, 1.9, 0.3))       # plate
    P.box(bm, (x, y - 4.0, z + 7.0), (1.5, 1.5, 2.2))       # GLASS
    P.pyramid(bm, (x, y - 4.0, z + 8.6), 2.1, 1.0)
    lamp = _emit("DD_Lamp_DockNorthHead", bm, "Props")
    dd_mood.mark_glass(lamp, 5.6 - 0.15, 8.2 - 0.15)

    made = [lamp]
    made.append(_place("DD_Prop_RopeCoil_A", "DockN", 1, (x - 2.5, y + 2.5),
                       z=z, yaw=0.3, settle=False))
    made.append(_place("DD_Prop_Crate_A", "DockN", 2, (x + 2.0, y + 1.0),
                       z=z, yaw=0.8, settle=False))
    return [m for m in made if m]


def place_rope_lines():
    """One overhead span per plaza quarter. The kit mesh is the line, its
    hangers and their lanterns; it is lifted so the line itself sits ~14 studs
    over the deck rather than resting on it."""
    made = []
    for i, (site, ang, rad, extra) in enumerate(ROPE_LINE_SITES):
        src = _kit(f"DD_Overhead_RopeLine_{'ABC'[i % 3]}")
        lift = DECK_Z + 14.0 - src.dimensions.z
        obj = _place(src.name, site, 30 + i, _polar(ang, rad), z=lift,
                     yaw=math.radians(ang + 90.0 + extra), settle=False)
        made.append(obj)
    return [m for m in made if m]


def build_tide_line():
    """Barnacle and algae banding at a fixed Z across the shore arc and around
    both breakwater roots. One height everywhere is the whole point: a tide
    line that wanders reads as noise, a consistent one reads as a coast."""
    made = []
    r_at_waterline = (p6_gate.SHORE_R + config.BEACH_RUN
                      * (WATERLINE_Z - config.GROUND_Z)
                      / (config.BEACH_DROP - config.GROUND_Z))
    band = dd_mesh.annulus_sector_solid(
        "DD_Struct_TideLine_Shore",
        inner_radius=r_at_waterline - 2.6, outer_radius=r_at_waterline + 2.6,
        angle_start_deg=-config.GATE_HALF_ANGLE, angle_end_deg=config.GATE_HALF_ANGLE,
        thickness=0.45, segments=30, base_z=WATERLINE_Z + 0.22)
    dd_mesh.shade_flat(band)
    dd_scene.set_origin_to_base(band)
    dd_scene.link_to_collection(band, "Structures")
    made.append(band)

    for side, suffix in ((1.0, "North"), (-1.0, "South")):
        centre = p6_gate.breakwater_centreline(side)
        bm = bmesh.new()
        for i in range(0, len(centre) - 1, 2):
            a = mathutils.Vector(centre[i])
            b = mathutils.Vector(centre[i + 1])
            tan = (b - a)
            tan.z = 0.0
            if tan.length < 1e-6:
                continue
            tan.normalize()
            nrm = mathutils.Vector((-tan.y, tan.x, 0.0))
            for s in (1.0, -1.0):
                p = a + nrm * (s * (p6_gate.BREAKWATER_LANDWARD_W + 1.4))
                P.box(bm, (p.x, p.y, WATERLINE_Z), (3.2, 1.0, 0.9),
                      yaw=math.atan2(tan.y, tan.x))
        made.append(_emit(f"DD_Struct_TideLine_{suffix}", bm, "Structures"))
    return made


def build_mooring_stones():
    """Depth-marked stones along the north breakwater, incised bands deepening
    as they go out. Marks, never modelled numerals."""
    centre = p6_gate.breakwater_centreline(1.0)
    bm = bmesh.new()
    for k in range(5):
        i = 2 + k * 2
        if i >= len(centre):
            break
        p = mathutils.Vector(centre[i])
        P.box(bm, (p.x, p.y, p6_gate.BREAKWATER_TOP_Z + 1.6), (2.0, 2.0, 3.2))
        for m in range(k + 1):               # one more band each stone out
            P.box(bm, (p.x, p.y - 1.05, p6_gate.BREAKWATER_TOP_Z + 0.7 + m * 0.5),
                  (1.3, 0.3, 0.22))
    return [_emit("DD_Struct_MooringStone_North", bm, "Structures")]


def build_wheel_ruts():
    """Worn into the cobbles where the barrows run: the gate lane and the two
    busiest plaza lanes. Laid a hair above the path surface so Phase 8 can
    darken them without a second material on the path itself."""
    import p4_plaza

    bm = bmesh.new()
    lanes = [(0.0, p4_plaza.BOW_MAGNITUDES[7])]
    for i in (0, 3):
        lanes.append((config.PLOT_ANGLES_DEG[i],
                      p4_plaza.BOW_MAGNITUDES[i] * (1.0 if i % 2 == 0 else -1.0)))
    for ang, bow in lanes:
        a = math.radians(ang)
        p0 = mathutils.Vector((config.PLAZA_INNER_R * math.cos(a),
                               config.PLAZA_INNER_R * math.sin(a)))
        p1 = mathutils.Vector((config.PLAZA_OUTER_R * math.cos(a),
                               config.PLAZA_OUTER_R * math.sin(a)))
        d = p1 - p0
        perp = mathutils.Vector((-d.y, d.x)).normalized()
        ctrl = (p0 + p1) / 2.0 + perp * bow
        prev = None
        for s in range(13):
            t = s / 12.0
            pt = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * ctrl + t ** 2 * p1
            if prev is not None:
                seg = pt - prev
                n = mathutils.Vector((-seg.y, seg.x)).normalized()
                yaw = math.atan2(seg.y, seg.x)
                mid = (prev + pt) / 2.0
                for off in (-2.1, 2.1):
                    q = mid + n * off
                    P.box(bm, (q.x, q.y, DECK_Z + 0.20),
                          (seg.length + 0.4, 0.8, 0.12), yaw=yaw)
            prev = pt
    return [_emit("DD_Struct_WheelRut_Plaza", bm, "Structures")]


def build():
    dd_scene.ensure_collections()
    purge()
    made = []
    made.append(place_fossil_arch())
    made.append(place_trophy_rack())
    made.append(build_dive_log_wall())
    made += place_shrine_and_jars()
    made += place_hull_and_yard()
    made += place_pines()
    made += place_chair_and_boots()
    made += build_deckhand_post()
    made += place_rope_lines()
    made += build_tide_line()
    made += build_mooring_stones()
    made += build_wheel_ruts()
    made = [m for m in made if m]
    print(f"phase 7c placed {len(made)} story objects")

    present, missing = dd_mood.audit_lit_sites(config)
    print(f"   lit sites present: {present}")
    print(f"   lit sites missing: {missing or 'none -- all five built'}")

    overhead = [o for o in bpy.data.objects if o.name.startswith("DD_Overhead_")
                and dd_scene.is_placed_instance(o.name)]
    spots = set()
    for o in overhead:
        spots.add((round(o.location.x / 25.0), round(o.location.y / 25.0)))
    print(f"   overhead sites: {len(spots)} distinct "
          f"(need >= {config.OVERHEAD_MIN_SITES}) "
          f"{'OK' if len(spots) >= config.OVERHEAD_MIN_SITES else 'FAIL'}")
    return made


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)
    dd_palette.apply_debug_colors([o for o in bpy.data.objects if o.name.startswith("DD_")])

    # r=44, not 72. At 72 the camera stands among the plaza-edge props with a
    # 5-stud-tall drying rack a few studs away filling the entire frame, which
    # shows nothing about how the quarter reads. Backing off to 44 puts ~90
    # studs of the quarter in view, from the open floor out to the enclosure
    # behind it -- which is what a density judgement actually needs.
    for label, ang in (("catch_n", 100.0), ("outfit_e", 20.0),
                       ("ballast_s", 250.0), ("market_w", 172.0)):
        a = math.radians(ang)
        cam = dd_scene.setup_eye_camera(
            f"RenderCam_Q_{label}",
            location=(44.0 * math.cos(a), 44.0 * math.sin(a), DECK_Z + 5.5),
            facing_deg=ang, fov_deg=75.0)
        dd_scene.render_to_file(cam, os.path.join(renders_dir, f"p7c_{label}.png"))

    cam = dd_scene.setup_look_at_camera(
        "RenderCam_DockBack", location=(400.0, -58.0, 10.0),
        target=(60.0, 0.0, 30.0), fov_deg=62.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p7c_dock_lookback.png"))

    cam = dd_scene.setup_look_at_camera(
        "RenderCam_Threshold", location=(150.0, 0.0, 12.0),
        target=(p6_gate.SHORE_R + 20.0, 0.0, 2.0), fov_deg=60.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p7c_threshold.png"))


if __name__ == "__main__":
    build()
    capture_renders()
