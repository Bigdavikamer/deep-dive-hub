"""Phase 6 -- Ocean gate and harbour works.

Harbour foreshore, graded beach ramp, the scoured shelf lip, two breakwater
arms with ramped seaward faces and coping, the timber cargo crane, lantern
caps, two modular dive docks on pilings, the dockside kiosk, the smuggler's
cellar door, buoys and the half-sunk wreck.

THE FORESHORE, and why it exists. Phases 1-2 built the island as a wedge with
the whole +/-GATE_HALF_ANGLE sector removed from the centre outward, not just
the rim opened. That left a void from the plaza's step ring (r=138) out to the
shoreline (r=235) which only the 16-stud gate path bridged: a player stepping
30 studs off that path fell through the world, the beach ramp at x>=235 was
disconnected from the island entirely, and config's KIOSK_XY (205,-38) -- the
brief's "top of the beach ramp" -- was suspended over nothing. The brief's
"rim open across +/-34.4 deg, a 260-stud mouth" describes an open coastline,
not a missing wedge; GATE_WIDTH 260 is the chord 2*235*sin(34.4) = 265. So
this phase fills the sector with flat ground at GROUND_Z from the step ring to
the shore, meeting the island quadrants at both gate boundary angles where
p2's coastline jitter is already tapered to exactly ISLAND_RADIUS.

Everything here is an arc band, not a rectangle. At the gate's edge angles the
arc r=235 sits ~39 studs inside the line x=235, so Phase 1's rectangular beach
slab hung off the coastline at both corners.

Dimensions not in config.py, inferred here rather than silently picked:
  WATERLINE_Z        = -4.0   sea level. The beach ramp runs GROUND_Z to
                              BEACH_DROP (0 -> -6), and "dry sand -> wet sand
                              -> shallow" only means anything if the waterline
                              falls inside that run; -4 puts the last third
                              under water. Everything tide-related keys off
                              this -- the cellar door sill, the buoys, and
                              Phase 7c's barnacle rings.
  BREAKWATER_* widths/heights  only BREAKWATER_REACH (90) is specified.
  DOCK_WIDTH         = 10.0   matches the value Phase 1 inferred.
  DOCK_DECK_Z        = BEACH_DROP, so the deck is flush with the foot of the
                              beach ramp and you walk straight on.

Deferred on purpose: kelp and coral clusters. The brief lists them here, but
the Phase 7a prop library also specifies them with variant counts (4 each) and
Phase 7b places them by seeded scatter with linked mesh data. Building them
twice would fork the mesh data and break validate.py check 17, so this phase
builds only the unique gate set pieces -- the wreck and the three buoys.

Idempotent: purges its own prefixes, superseding Phase 1's DD_Terrain_Beach
and its greybox DD_Dock_North / DD_Dock_South planks.
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
from lib import mesh as dd_mesh
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import scene as dd_scene

# ---- inferred dimensions (see module docstring) ----------------------------
WATERLINE_Z = -4.0

GATE_A0 = -config.GATE_HALF_ANGLE
GATE_A1 = config.GATE_HALF_ANGLE

FORESHORE_INNER_R = config.PLAZA_OUTER_R + 3.0    # outer edge of Phase 4's step ring
SHORE_R = config.ISLAND_RADIUS
BEACH_OUTER_R = SHORE_R + config.BEACH_RUN
ISLAND_THICKNESS = 6.0
BEACH_BOTTOM_Z = config.BEACH_DROP - 4.0
BEACH_BANDS = ("Dry", "Wet", "Shallow")

SHELF_OUTER_R = BEACH_OUTER_R + 25.0
PATH_PROUD = 0.15                                  # matches p4_plaza

BREAKWATER_SAMPLES = 14
BREAKWATER_TOP_Z = 5.0
BREAKWATER_BASE_Z = -12.0
BREAKWATER_LANDWARD_W = 8.0
BREAKWATER_SEAWARD_TOP_W = 5.0
BREAKWATER_SEAWARD_BASE_W = 14.0
COPING_COUNT = 7
CAP_POST_H = 6.0
CAP_GLASS_H = 2.8
CAP_ROOF_H = 1.2

DOCK_WIDTH = 10.0
DOCK_DECK_Z = config.BEACH_DROP
DOCK_DECK_THICK = 1.0
DOCK_PILING_R = 0.9
DOCK_START_X = BEACH_OUTER_R

KIOSK_H = 11.0
CRANE_MAST_H = 20.0

OWNED_PREFIXES = [
    "DD_Terrain_Foreshore",
    "DD_Terrain_Beach",          # supersedes Phase 1's rectangular slab
    "DD_Terrain_ShelfLip",
    "DD_Struct_Path_GateOuter",
    "DD_Struct_Breakwater",
    "DD_Struct_CargoCrane",
    "DD_Struct_Kiosk",
    "DD_Struct_CellarDoor",
    "DD_Struct_CellarLedge",
    "DD_Lamp_Breakwater",
    "DD_Dock_North",             # supersedes Phase 1's greybox planks
    "DD_Dock_South",
    "DD_Sub_Wreck",
    # DD_Sub_Buoy is deliberately absent: the Phase 7a kit owns those meshes
    # now, and purging a prefix this phase no longer builds would delete them
    # whenever p6 is re-run on its own.
]


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def _finish(obj, collection):
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, collection)
    return obj


def _add_box(bm, center, size, yaw=0.0):
    """Append one box (yaw baked into its vertices) to an existing bmesh, so a
    multi-part fitting stays a single object and a single mesh datablock."""
    cx, cy, cz = center
    sx, sy, sz = size
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
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


def _emit(name, bm, collection):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return _finish(dd_mesh.bm_to_object(name, bm), collection)


def ground_z(x, y):
    """Walkable surface height in the gate sector: flat foreshore in to the
    shore, then the beach ramp. The breakwater roots sit on the beach, which is
    above the waterline there, so anything mounted on an arm has to clear this
    and not just WATERLINE_Z."""
    r = math.hypot(x, y)
    if r <= SHORE_R:
        return config.GROUND_Z
    if r >= BEACH_OUTER_R:
        return config.BEACH_DROP
    return config.GROUND_Z + (config.BEACH_DROP - config.GROUND_Z) * (r - SHORE_R) / config.BEACH_RUN


def seabed_z(x):
    """Top of Phase 2's ocean floor slab at this X."""
    near_x, far_x = BEACH_OUTER_R, 700.0
    t = min(max((x - near_x) / (far_x - near_x), 0.0), 1.0)
    return config.OCEAN_FLOOR_NEAR + (config.OCEAN_FLOOR_FAR - config.OCEAN_FLOOR_NEAR) * t


# ---- ground ----------------------------------------------------------------

def build_foreshore():
    """Flat harbour ground filling the gate sector from the plaza's step ring
    out to the shoreline -- the land every other object in this phase and the
    kiosk in config.py stands on."""
    obj = dd_mesh.annulus_sector_solid(
        "DD_Terrain_Foreshore",
        inner_radius=FORESHORE_INNER_R, outer_radius=SHORE_R,
        angle_start_deg=GATE_A0, angle_end_deg=GATE_A1,
        thickness=ISLAND_THICKNESS, segments=32, base_z=config.GROUND_Z,
    )
    return _finish(obj, "Terrain")


def build_beach():
    """Three graded arc bands, dry -> wet -> shallow, ramping GROUND_Z down to
    BEACH_DROP across BEACH_RUN. Separate meshes so Phase 8 can paint sand_dry,
    sand_wet and water_shallow without splitting geometry later."""
    objs = []
    span = config.BEACH_RUN / len(BEACH_BANDS)
    for k, band in enumerate(BEACH_BANDS):
        r0 = SHORE_R + k * span
        r1 = r0 + span
        z0 = config.GROUND_Z + (config.BEACH_DROP - config.GROUND_Z) * (k / len(BEACH_BANDS))
        z1 = config.GROUND_Z + (config.BEACH_DROP - config.GROUND_Z) * ((k + 1) / len(BEACH_BANDS))
        obj = dd_mesh.annulus_sector_ramp(
            f"DD_Terrain_Beach{band}",
            inner_radius=r0, outer_radius=r1,
            angle_start_deg=GATE_A0, angle_end_deg=GATE_A1,
            z_inner=z0, z_outer=z1, bottom_z=BEACH_BOTTOM_Z, segments=32,
        )
        objs.append(_finish(obj, "Terrain"))
    return objs


def build_shelf_lip():
    """The drop. Carries the beach's foot down to the ocean floor instead of
    leaving a 34-stud step hanging at the dock line -- this is the sand-to-dark
    transition the brief wants read as the edge of the shelf."""
    obj = dd_mesh.annulus_sector_ramp(
        "DD_Terrain_ShelfLip",
        inner_radius=BEACH_OUTER_R, outer_radius=SHELF_OUTER_R,
        angle_start_deg=GATE_A0, angle_end_deg=GATE_A1,
        z_inner=config.BEACH_DROP, z_outer=config.OCEAN_FLOOR_NEAR,
        bottom_z=config.OCEAN_FLOOR_NEAR - 4.0, segments=32,
    )
    return _finish(obj, "Terrain")


def build_gate_causeway():
    """Carries The Descent across the foreshore from the step ring to the
    shore, bowed like every other lane (reference rule 3)."""
    obj = dd_mesh.bowed_path(
        "DD_Struct_Path_GateOuter",
        (FORESHORE_INNER_R, 0.0), (SHORE_R - 2.0, 0.0),
        config.TRAFFIC_LANE_WIDTH, -11.0, 2.0,
        base_z=config.GROUND_Z + PATH_PROUD,
    )
    return _finish(obj, "Plaza")


# ---- harbour works ---------------------------------------------------------

def breakwater_centreline(side):
    """Quadratic Bezier from the rim edge, curving out and hooking back toward
    the gate axis so the two arms frame the mouth. `side` is +1 north, -1 south."""
    a = math.radians(config.GATE_HALF_ANGLE * side)
    root = mathutils.Vector((SHORE_R * math.cos(a), SHORE_R * math.sin(a), 0.0))
    ctrl = root + mathutils.Vector((45.0, 5.0 * side, 0.0))
    end = root + mathutils.Vector((78.0, -30.0 * side, 0.0))
    pts = []
    for i in range(BREAKWATER_SAMPLES + 1):
        t = i / BREAKWATER_SAMPLES
        p = (1 - t) ** 2 * root + 2 * (1 - t) * t * ctrl + t ** 2 * end
        pts.append((p.x, p.y, 0.0))
    return pts


def build_breakwaters():
    """Ramped seaward face, blocky landward face -- the profile is asymmetric
    on purpose (harbour-works rule 6). `side` also flips which way the ramp
    faces, since the seaward side is +Y on the north arm and -Y on the south."""
    objs = []
    for side, suffix in ((1.0, "North"), (-1.0, "South")):
        centreline = breakwater_centreline(side)
        section = [
            (-BREAKWATER_LANDWARD_W * side, BREAKWATER_BASE_Z),
            (-BREAKWATER_LANDWARD_W * side, BREAKWATER_TOP_Z),
            (BREAKWATER_SEAWARD_TOP_W * side, BREAKWATER_TOP_Z),
            (BREAKWATER_SEAWARD_BASE_W * side, BREAKWATER_BASE_Z),
        ]
        obj = dd_mesh.swept_solid(f"DD_Struct_Breakwater{suffix}", centreline, section)
        objs.append(_finish(obj, "Structures"))

        # coping stones at irregular intervals along the crest
        bm = bmesh.new()
        for k in range(COPING_COUNT):
            t = (k + 0.5) / COPING_COUNT
            t += 0.045 * math.sin(k * 2.4 + side)          # deterministic irregularity
            i = min(int(t * BREAKWATER_SAMPLES), BREAKWATER_SAMPLES - 1)
            p = mathutils.Vector(centreline[i])
            nxt = mathutils.Vector(centreline[i + 1])
            tan = (nxt - p).normalized()
            yaw = math.atan2(tan.y, tan.x)
            length = 7.0 + 2.5 * math.sin(k * 1.7)
            _add_box(bm, (p.x, p.y, BREAKWATER_TOP_Z + 0.7),
                     (length, BREAKWATER_LANDWARD_W + BREAKWATER_SEAWARD_TOP_W - 1.0, 1.4), yaw=yaw)
        objs.append(_emit(f"DD_Struct_BreakwaterCoping{suffix}", bm, "Structures"))

        # Lantern cap at the arm head -- two of the five sites that stay lit.
        # Built from a running height so the glass band is derived, not a
        # magic pair: lib.mood.mark_glass needs its exact local Z extent to
        # put those faces in the glass material slot.
        head = mathutils.Vector(centreline[-1])
        bm = bmesh.new()
        z = BREAKWATER_TOP_Z
        _add_box(bm, (head.x, head.y, z + CAP_POST_H / 2.0), (3.0, 3.0, CAP_POST_H))
        z += CAP_POST_H
        _add_box(bm, (head.x, head.y, z + CAP_GLASS_H / 2.0), (4.2, 4.2, CAP_GLASS_H))
        z += CAP_GLASS_H
        _add_box(bm, (head.x, head.y, z + CAP_ROOF_H / 2.0), (5.0, 5.0, CAP_ROOF_H))
        lamp = _emit(f"DD_Lamp_Breakwater{suffix}", bm, "Structures")
        dd_mood.mark_glass(lamp, CAP_POST_H - 0.01, CAP_POST_H + CAP_GLASS_H + 0.01)
        objs.append(lamp)
    return objs


def build_cargo_crane():
    """Timber cargo crane on the north arm. Harbour districts read as working
    ports because of cranes and vertical variation more than anything else."""
    centreline = breakwater_centreline(1.0)
    p = mathutils.Vector(centreline[BREAKWATER_SAMPLES // 2])
    nxt = mathutils.Vector(centreline[BREAKWATER_SAMPLES // 2 + 1])
    tan = (nxt - p).normalized()
    yaw = math.atan2(tan.y, tan.x)
    inward = mathutils.Vector((-tan.y, tan.x, 0.0)) * -1.0   # toward the harbour

    bm = bmesh.new()
    base_z = BREAKWATER_TOP_Z
    _add_box(bm, (p.x, p.y, base_z + 1.0), (7.0, 7.0, 2.0), yaw=yaw)
    _add_box(bm, (p.x, p.y, base_z + CRANE_MAST_H / 2.0), (2.6, 2.6, CRANE_MAST_H), yaw=yaw)
    # jib reaching out over the water, with a diagonal brace under it
    jib_len = 16.0
    jib_mid = p + inward * (jib_len / 2.0)
    _add_box(bm, (jib_mid.x, jib_mid.y, base_z + CRANE_MAST_H - 1.0), (jib_len, 2.0, 1.8),
             yaw=yaw + math.pi / 2.0)
    brace_mid = p + inward * (jib_len * 0.3)
    _add_box(bm, (brace_mid.x, brace_mid.y, base_z + CRANE_MAST_H - 5.0), (9.0, 1.4, 1.4),
             yaw=yaw + math.pi / 2.0)
    # pulley block and its hanging hook
    head = p + inward * (jib_len - 1.5)
    _add_box(bm, (head.x, head.y, base_z + CRANE_MAST_H - 3.2), (2.2, 2.2, 2.4), yaw=yaw)
    _add_box(bm, (head.x, head.y, base_z + CRANE_MAST_H - 7.0), (0.5, 0.5, 5.0), yaw=yaw)
    return _emit("DD_Struct_CargoCrane", bm, "Structures")


def build_cellar_door():
    """Smuggler's cellar entrance: a barred iron door set into the south arm's
    landward face above the tide line, reached by a narrow ledge. Geometry only
    -- the interior is Studio's."""
    centreline = breakwater_centreline(-1.0)
    i = 3
    p = mathutils.Vector(centreline[i])
    tan = (mathutils.Vector(centreline[i + 1]) - p).normalized()
    yaw = math.atan2(tan.y, tan.x)
    landward = mathutils.Vector((-tan.y, tan.x, 0.0))       # -side faces the harbour
    face = p + landward * BREAKWATER_LANDWARD_W

    # Above the tide line, but the arm's root sits on beach that is already
    # above it -- keyed to the waterline alone the sill buried itself in sand.
    sill_z = max(WATERLINE_Z + 2.0, ground_z(face.x, face.y) + 0.6)
    bm = bmesh.new()
    _add_box(bm, (face.x, face.y, sill_z + 3.0), (7.0, 1.6, 6.0), yaw=yaw)      # frame
    _add_box(bm, (face.x, face.y, sill_z + 3.0), (5.2, 0.6, 4.6), yaw=yaw)      # door leaf
    for k in range(3):                                                          # bars
        off = (k - 1) * 1.5
        bar = face + tan * off
        _add_box(bm, (bar.x, bar.y, sill_z + 3.0), (0.4, 1.0, 4.6), yaw=yaw)
    door = _emit("DD_Struct_CellarDoor", bm, "Structures")

    bm = bmesh.new()
    ledge_mid = face + landward * 3.0
    _add_box(bm, (ledge_mid.x, ledge_mid.y, sill_z - 0.4), (14.0, 6.0, 0.8), yaw=yaw)
    ledge = _emit("DD_Struct_CellarLedge", bm, "Structures")
    return [door, ledge]


# ---- docks -----------------------------------------------------------------

def build_docks():
    """Two dive docks built from DOCK_MODULE_LEN modules on pilings, decks flush
    with the foot of the beach ramp. These are the dive-entry points, so each
    gets a head marker -- DD_Dock_* is already on validate.py's biolume_cyan
    allowlist for Phase 8 to paint."""
    objs = []
    module_len = config.DOCK_MODULE_LEN
    full, remainder = divmod(config.DOCK_LENGTH, module_len)
    lengths = [module_len] * int(full) + ([remainder] if remainder > 0.01 else [])

    for side, suffix in ((1.0, "North"), (-1.0, "South")):
        y = config.DOCK_OFFSET_Y * side
        x = DOCK_START_X
        for m, seg_len in enumerate(lengths):
            bm = bmesh.new()
            cx = x + seg_len / 2.0
            _add_box(bm, (cx, y, DOCK_DECK_Z - DOCK_DECK_THICK / 2.0),
                     (seg_len, DOCK_WIDTH, DOCK_DECK_THICK))
            for px in (x + 2.0, x + seg_len - 2.0):
                for py in (y - DOCK_WIDTH / 2.0 + 1.5, y + DOCK_WIDTH / 2.0 - 1.5):
                    bed = seabed_z(px)
                    height = DOCK_DECK_Z - DOCK_DECK_THICK - bed
                    circle = bmesh.new()
                    bmesh.ops.create_cone(circle, cap_ends=True, cap_tris=True, segments=6,
                                          radius1=DOCK_PILING_R, radius2=DOCK_PILING_R,
                                          depth=height)
                    bmesh.ops.translate(circle, verts=circle.verts,
                                        vec=(px, py, bed + height / 2.0))
                    tmp = bpy.data.meshes.new("_tmp_piling")
                    circle.to_mesh(tmp)
                    circle.free()
                    bm.from_mesh(tmp)
                    bpy.data.meshes.remove(tmp)
            objs.append(_emit(f"DD_Dock_{suffix}_Mod{m:02d}", bm, "Docks"))
            x += seg_len

        bm = bmesh.new()
        _add_box(bm, (x - 3.0, y, DOCK_DECK_Z + 0.4), (5.0, DOCK_WIDTH - 1.0, 0.5))
        objs.append(_emit(f"DD_Dock_{suffix}_DiveMarker", bm, "Docks"))
    return objs


# ---- kiosk -----------------------------------------------------------------

def build_kiosk():
    """Single-vendor shack at the top of the beach ramp, housing the
    Shipwright: tarred plank walls, a corrugated lean-to, oar rack, and a
    rowboat on trestles. Open toward the harbour so the counter faces the lane."""
    kx, ky = config.KIOSK_XY
    f = config.KIOSK_FOOTPRINT
    half = f / 2.0
    yaw = math.atan2(-ky, -kx)      # front faces back toward the plaza

    bm = bmesh.new()
    _add_box(bm, (kx, ky, config.GROUND_Z + 0.4), (f, f, 0.8), yaw=yaw)          # deck
    back = mathutils.Vector((math.cos(yaw + math.pi), math.sin(yaw + math.pi), 0.0))
    side_v = mathutils.Vector((-back.y, back.x, 0.0))
    wall_c = mathutils.Vector((kx, ky, 0.0)) + back * half
    _add_box(bm, (wall_c.x, wall_c.y, KIOSK_H / 2.0), (f, 1.2, KIOSK_H), yaw=yaw + math.pi / 2.0)
    for s in (1.0, -1.0):
        w = mathutils.Vector((kx, ky, 0.0)) + side_v * (half * s)
        _add_box(bm, (w.x, w.y, KIOSK_H / 2.0), (f, 1.2, KIOSK_H), yaw=yaw)
    # counter across the open front
    front = mathutils.Vector((kx, ky, 0.0)) - back * (half - 1.0)
    _add_box(bm, (front.x, front.y, config.ROW_COUNTER_H / 2.0),
             (f - 2.0, 2.0, config.ROW_COUNTER_H), yaw=yaw + math.pi / 2.0)
    # lean-to roof, sloped by stacking two offset slabs (keeps it quad-only)
    roof_c = mathutils.Vector((kx, ky, 0.0)) + back * 2.0
    _add_box(bm, (roof_c.x, roof_c.y, KIOSK_H + 1.0), (f + 3.0, f + 1.0, 1.0), yaw=yaw)
    _add_box(bm, (wall_c.x, wall_c.y, KIOSK_H + 2.2), (f + 3.0, f / 2.0, 1.4), yaw=yaw)
    shell = _emit("DD_Struct_Kiosk", bm, "Structures")

    # oar rack and a rowboat up on trestles beside the shack
    bm = bmesh.new()
    rack = mathutils.Vector((kx, ky, 0.0)) + side_v * (half + 4.0)
    for k in range(4):
        o = rack + back * (k * 2.2 - 3.3)
        _add_box(bm, (o.x, o.y, 5.0), (0.6, 0.6, 10.0))
    boat = mathutils.Vector((kx, ky, 0.0)) - side_v * (half + 6.0)
    for s in (1.0, -1.0):
        t = boat + back * (5.0 * s)
        _add_box(bm, (t.x, t.y, 1.6), (4.0, 1.0, 3.2), yaw=yaw)
    _add_box(bm, (boat.x, boat.y, 4.2), (7.0, 18.0, 2.0), yaw=yaw)
    _add_box(bm, (boat.x, boat.y, 5.6), (5.0, 15.0, 1.0), yaw=yaw)
    fitout = _emit("DD_Struct_KioskFitout", bm, "Structures")
    return [shell, fitout]


# ---- underwater set pieces -------------------------------------------------

def build_buoys():
    """Three buoys riding the waterline beyond the dock heads."""
    objs = []
    spots = ((452.0, 24.0), (474.0, -68.0), (503.0, 62.0))
    for (bx, by), suffix in zip(spots, "ABC"):
        bm = bmesh.new()
        _add_box(bm, (bx, by, WATERLINE_Z - 1.0), (5.0, 5.0, 6.0))
        _add_box(bm, (bx, by, WATERLINE_Z + 2.6), (3.2, 3.2, 1.6))
        _add_box(bm, (bx, by, WATERLINE_Z + 5.4), (0.8, 0.8, 4.0))
        objs.append(_emit(f"DD_Sub_Buoy_{suffix}", bm, "Underwater"))
    return objs


def build_wreck():
    """Half-sunk hull grounded in the shallows off the south side of the mouth,
    listing, with its mast broken toward shore. At r=280 the beach is -3.9 and
    the waterline is -4.0, so the hull straddles it and actually reads as
    half-sunk -- out on the -40 floor it would simply be gone.

    Angle -13 deg, not the -20 deg it started at: the arms hook inward from
    their +/-34.4 roots to about +/-20.7 at the head, so anything past 20 deg
    lands on a breakwater. This keeps the hull ~40 studs off the south arm and
    ~60 studs off the causeway."""
    wx, wy = 273.0, -63.0
    tilt = math.radians(26.0)

    bm = bmesh.new()
    _add_box(bm, (0.0, 0.0, 3.0), (42.0, 13.0, 8.0))
    _add_box(bm, (0.0, 0.0, 7.4), (34.0, 10.0, 1.6))       # deck
    _add_box(bm, (16.0, 0.0, 8.0), (7.0, 8.0, 7.0))        # bow rise
    _add_box(bm, (-15.0, 0.0, 8.4), (6.0, 9.0, 5.0))       # stern block
    for k in range(4):                                      # broken ribs amidships
        _add_box(bm, (-6.0 + k * 4.0, 0.0, 9.6), (0.9, 11.0, 3.6))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0),
                     matrix=mathutils.Matrix.Rotation(tilt, 3, "X"))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0),
                     matrix=mathutils.Matrix.Rotation(math.radians(-24.0), 3, "Z"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(wx, wy, WATERLINE_Z - 1.5))
    hull = _emit("DD_Sub_WreckHull", bm, "Underwater")

    bm = bmesh.new()
    _add_box(bm, (0.0, 0.0, 9.0), (2.2, 2.2, 18.0))
    _add_box(bm, (0.0, 0.0, 15.0), (9.0, 1.2, 1.2))        # yard, still lashed
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0),
                     matrix=mathutils.Matrix.Rotation(math.radians(58.0), 3, "Y"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(wx - 4.0, wy + 2.0, WATERLINE_Z - 1.0))
    mast = _emit("DD_Sub_WreckMast", bm, "Underwater")
    return [hull, mast]


def apply_mood():
    """Mood lever 3 for this phase's geometry: the water and the recessed
    places get darker with depth on their own, so the gate reads as an edge
    you descend over even with scene lighting off."""
    s = config.DEPTH_DARKEN_STRENGTH
    shelf = bpy.data.objects.get("DD_Terrain_ShelfLip")
    if shelf:
        dd_mood.apply_depth_darken(shelf, s, config.BEACH_DROP, config.OCEAN_FLOOR_NEAR)
    shallow = bpy.data.objects.get("DD_Terrain_BeachShallow")
    if shallow:
        dd_mood.apply_depth_darken(shallow, s * 0.5, WATERLINE_Z, config.BEACH_DROP)
    ledge = bpy.data.objects.get("DD_Struct_CellarLedge")
    if ledge:
        dd_mood.apply_flat_darken(ledge, 1.0 - s)


def build():
    dd_scene.ensure_collections()
    purge()
    build_foreshore()
    build_beach()
    build_shelf_lip()
    build_gate_causeway()
    build_breakwaters()
    build_cargo_crane()
    build_cellar_door()
    build_docks()
    build_kiosk()
    # Buoys are NOT built here any more. The Phase 7a library specifies Buoy
    # with 3 variants, so the kit owns those meshes and Phase 7b places them as
    # linked instances -- same reasoning as kelp and coral. Building them here
    # too collided on DD_Sub_Buoy_A/B/C (Blender appended ".001", which fails
    # the naming regex) and would have forked the mesh data besides. The wreck
    # stays: it is a unique set piece with no kit entry.
    build_wreck()
    apply_mood()


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=1100.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p6_top_ortho.png"), xray=False)

    gate_cam = dd_scene.setup_look_at_camera(
        "RenderCam_Gate", location=(120.0, -150.0, 120.0), target=(330.0, 0.0, -6.0), fov_deg=55.0)
    dd_scene.render_to_file(gate_cam, os.path.join(renders_dir, "p6_gate_oblique.png"))

    # the walk every player makes: plaza edge, down the causeway, out the mouth
    descent_cam = dd_scene.setup_eye_camera(
        "RenderCam_Descent", location=(150.0, 0.0, 5.0), facing_deg=0.0, fov_deg=70.0)
    dd_scene.render_to_file(descent_cam, os.path.join(renders_dir, "p6_descent_eye.png"))

    dock_cam = dd_scene.setup_look_at_camera(
        "RenderCam_DockBack", location=(430.0, -70.0, 14.0), target=(180.0, 0.0, 20.0), fov_deg=60.0)
    dd_scene.render_to_file(dock_cam, os.path.join(renders_dir, "p6_dock_lookback.png"))


if __name__ == "__main__":
    build()
    capture_renders()
