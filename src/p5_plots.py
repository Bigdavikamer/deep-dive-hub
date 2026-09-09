"""Phase 5 -- Plots.

Per CLAUDE.md Phase 5 the plots get ONLY: the flat pad at Z=PLOT_Z, a low
stone kerb (PLOT_KERB_H), a plot marker post (timber post + hanging carved
sign + unlit lantern), and a footpath to the plaza. No houses -- players and
Studio scripts fill the pads.

What this phase does and does NOT rebuild
-----------------------------------------
  - The seven pads (DD_Plot_Pad_01..07) are already correct from Phase 1
    (3-stud-thick box, top at PLOT_Z, plot_yaw baked into local vertex data).
    NOT touched here.
  - The seven plaza->plot footpaths (DD_Struct_Path_Plot01..07) are already
    built by Phase 4, bowed per reference rule 3, running from
    PLAZA_INNER_R out to PLAZA_OUTER_R. PLAZA_OUTER_R == PLOT_RING_R -
    PLOT_SIZE/2 by construction, so each path already terminates exactly on
    its plot's near pad edge in plan view. NOT rebuilt here.
    There is, however, a real VERTICAL gap: the path/plaza deck top is at
    PLAZA_LIFT (+1.5) and the pad top is at PLOT_Z (-1.5) -- a 3-stud drop,
    and Phase 4's step ring already occupies the first STEP_RING_WIDTH studs
    beyond r=PLAZA_OUTER_R. So this phase adds only the missing connector:
    a two-block, three-riser stair (DD_Plot_Steps_XX) descending that 3
    studs, starting exactly where the step ring's outer edge lands
    (r = PLAZA_OUTER_R + STEP_RING_WIDTH) and landing flush on the pad.
    The kerb leaves a matching gap for it.
  - Phase 4's temporary DD_Plot_MarkerPost_XX placeholder cylinders (plain
    posts, built purely so GATE 2 could be verified against a real object)
    are PURGED here and replaced by the real marker family, same pattern as
    Phase 3 superseding Phase 1's greybox shop.

Geometry / scope notes (flagged, not silently assumed)
------------------------------------------------------
  - The pads sit 1.5 studs BELOW the surrounding Z=0 terrain (Phase 2's
    docstring already reads this as intentional terracing: a recessed pad in
    a raised plain). The kerb therefore rises from the pad top to +0.5 world
    -- a low stone lip just proud of the surrounding ground, which is exactly
    how a real kerb around a sunken yard reads. Nothing floats.
  - The kerb is flush with the pad edge on three sides but inset by
    STEP_RING_WIDTH on the plaza-facing side, because Phase 4's plaza step
    ring already overhangs the pad's first 3 studs -- see build_kerbs().
    One residual overlap is knowingly left alone: on plot 4 (due west, 180
    deg) Phase 4's emphasised west stair sweeps r=135..144 across +/-12 deg
    and its lowest tread grazes the top ~0.5 studs of that plot's near kerb.
    The tread sits ABOVE the kerb so nothing is visible, and reshaping the
    west stair is Phase 4 geometry, not this phase's.
  - No dimension here is pinned by config.py beyond PLOT_SIZE, PLOT_KERB_H
    and PLOT_Z. Kerb depth, marker post height, sign/lantern sizes and the
    stair run are design choices local to this module (constants below), all
    cheap to change; none of them is load-bearing for the layout.
  - Materials: debug/category colours only, exactly like Phases 1-4. The
    biolume_cyan interactable accent for the marker is built as real geometry
    (DD_Marker_Plot_XX_Plaque -- a plate on the post's plaza-facing side,
    the same "inlay strip on the customer side" idea the brief uses for the
    merchant-row counters) but is left UNPAINTED: assigning final PALETTE
    materials is Phase 8's job. validate.py's INTERACTABLE_NAME_HINTS
    already whitelists "DD_Marker_Plot", so Phase 8 can paint it cyan
    without touching the allowlist.

Per-plot variation ("no two identical", CLAUDE.md Phase 5)
----------------------------------------------------------
Everything below is derived deterministically from the plot index and
SCATTER_SEED, so re-running is byte-identical (operating rule 2):
  - Kerb stonework: per-plot base block length, per-block length / height /
    depth / lateral-offset jitter, and one of three corner treatments
    (flush corner block / raised square pier / two-tier stepped pier).
  - Sign carving: seven distinct low-poly carved icon silhouettes, modelled
    as real geometry raised proud of the board face (never a texture, never
    text): anchor, fish, shell, net, wave, hook, buoy.
  - Marker: post height jitter, board width jitter, and the whole marker
    mirrors to the other side of the entrance stair on odd-indexed plots.

Two inherited defects found while verifying this phase -- NOT fixed here
-----------------------------------------------------------------------
Both are in geometry earlier phases own, and both involve a real design
decision, so they are flagged rather than silently rebuilt (operating rule 9).

  1. THE PADS ARE BURIED. Phase 2's terrain quadrants are a solid flat disc
     at GROUND_Z from the centre out to MID_RADIUS=215; the plot ring lives
     at r=135..205, entirely underneath it. A downward raycast at any plot
     centre hits DD_Terrain_Island_*, not DD_Plot_Pad_*: the walkable surface
     inside every plot is terrain at Z=0, and the pad sits 1.5 studs below it,
     invisible. Consequence for this phase: the kerb is geometrically correct
     against config.py (2 studs standing on a pad whose top is PLOT_Z) but
     only 0.5 studs of it clears the terrain, and the lower of the two
     entrance treads is underground. Phase 2's docstring reads the recess as
     "intentional terracing", which is defensible -- but nothing has yet cut
     the terrain to expose it. The fix is either a Phase 2 recess per plot or
     a re-read of PLOT_Z; both are out of Phase 5's scope.
  2. THE MARKET CROSS STANDS IN PLOT 4. Phase 4 places it at (-145, 0),
     described there as "just outside the plaza ring" -- but PLAZA_OUTER_R is
     by construction plot 4's near pad edge, so r=145 with an 8-stud plinth
     lands squarely on plot 4's pad and across its entrance stair. Moving it
     is a Phase 4 placement change.

Idempotent: purges "DD_Plot_Kerb_", "DD_Plot_Steps_", "DD_Marker_Plot_" and
Phase 4's "DD_Plot_MarkerPost_" before rebuilding. Deliberately does NOT
purge the bare "DD_Plot_" prefix -- that would eat Phase 1's pads.
"""
import math
import os
import random
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

OWNED_PREFIXES = [
    "DD_Plot_Kerb_",
    "DD_Plot_Steps_",
    "DD_Marker_Plot_",
    "DD_Plot_MarkerPost_",   # Phase 4's temporary GATE 2 placeholder
]

# ---- kerb -------------------------------------------------------------------
KERB_DEPTH        = 2.6      # radial thickness of the stone kerb
KERB_JOINT        = 0.25     # mortar gap left between adjacent blocks
KERB_BLOCK_LEN    = [8.0, 9.0, 10.0, 8.5, 9.5, 11.0, 7.5]   # per plot, base course length
KERB_CORNER_VARIANT = [0, 1, 2, 1, 2, 0, 2]                 # per plot, 0/1/2 (see _kerb_corner)

# ---- entrance stair (the missing vertical link to Phase 4's footpath) --------
STEP_RING_WIDTH   = 3.0      # must match p4_plaza.STEP_RING_WIDTH
STAIR_RUN         = 3.0      # depth of each tread
STAIR_WIDTH       = [18.0, 17.0, 19.0, 18.5, 17.5, 19.0, 18.0]   # per plot

# ---- marker post ------------------------------------------------------------
POST_W            = 1.5
POST_H            = 11.0     # base at pad top -> +9.5 world, clears the plaza deck
POST_CAP_W        = 2.0
POST_CAP_H        = 0.4
POST_LOCAL_X      = 11.0     # beside the entrance stair, not in it
POST_LOCAL_Y      = 26.0     # just inside the near kerb's inner face

ARM_REACH         = 4.4      # bracket projection toward the plaza
ARM_W             = 0.5
ARM_H             = 0.6
ARM_Z             = 10.2     # underside of the bracket arm, local

SIGN_W            = 5.0
SIGN_H            = 3.6
SIGN_D            = 0.5
SIGN_LINK         = 0.6      # hanging link length between arm and board
ICON_RAISE        = 0.35     # how far the carved icon stands proud of the board

LANTERN_BODY_W    = 1.6
LANTERN_BODY_H    = 2.2
LANTERN_PLATE_H   = 0.3
LANTERN_ROOF_H    = 1.1
LANTERN_FINIAL_H  = 0.4
LANTERN_HANGER    = 0.8

PLAQUE_W          = 1.6
PLAQUE_H          = 1.2
PLAQUE_D          = 0.3
PLAQUE_Z          = 4.2      # chest height for a player standing on the pad


# ---- bmesh primitives in plot-local space -----------------------------------
# All of these bake `yaw` into the vertex data. Source kit meshes must keep
# identity object rotation (CLAUDE.md HARD CONSTRAINTS > Transforms), so a
# plot's facing lives in the mesh, never in obj.rotation_euler -- the same
# rule lib.mesh.box() documents.

def _rot(x, y, cos_y, sin_y):
    return (x * cos_y - y * sin_y, x * sin_y + y * cos_y)


def _add_box(bm, cx, cy, base_z, size_x, size_y, size_z, yaw):
    """Closed box shell added into `bm`. (cx, cy) is the footprint centre in
    plot-local coords, base_z its local base height."""
    hx, hy = size_x / 2.0, size_y / 2.0
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    lower, upper = [], []
    for lx, ly in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
        wx, wy = _rot(cx + lx, cy + ly, cos_y, sin_y)
        lower.append(bm.verts.new((wx, wy, base_z)))
        upper.append(bm.verts.new((wx, wy, base_z + size_z)))
    bm.faces.new(lower)
    bm.faces.new(upper)
    for k in range(4):
        m = (k + 1) % 4
        bm.faces.new((lower[k], lower[m], upper[m], upper[k]))


def _add_pyramid(bm, cx, cy, base_z, size, height, yaw):
    """Closed square pyramid (the lantern roof). Quad base + 4 tris."""
    h = size / 2.0
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    base = []
    for lx, ly in ((-h, -h), (h, -h), (h, h), (-h, h)):
        wx, wy = _rot(cx + lx, cy + ly, cos_y, sin_y)
        base.append(bm.verts.new((wx, wy, base_z)))
    ax, ay = _rot(cx, cy, cos_y, sin_y)
    apex = bm.verts.new((ax, ay, base_z + height))
    bm.faces.new(base)
    for k in range(4):
        bm.faces.new((base[k], base[(k + 1) % 4], apex))


def _finalize(bm, name, location, collection="Plots"):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    obj = dd_mesh.bm_to_object(name, bm)
    obj.location = location
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, collection)
    return obj


def _plot_origin(i):
    """World location for a plot-local mesh: pad centre, at pad top height."""
    x, y = config.plot_xy(i)
    return (x, y, config.PLOT_Z)


def to_world(i, local_x, local_y):
    """Plot-local (x, y) -> world (x, y). Used by the render cameras."""
    px, py = config.plot_xy(i)
    yaw = config.plot_yaw(i)
    dx, dy = _rot(local_x, local_y, math.cos(yaw), math.sin(yaw))
    return (px + dx, py + dy)


# ---- kerb -------------------------------------------------------------------

def _kerb_corner(bm, rng, variant, cx, cy, yaw):
    """Corner treatment. Returns the run inset the straight courses must
    respect so nothing interpenetrates. Three visibly distinct variants."""
    h = config.PLOT_KERB_H
    if variant == 0:                       # flush corner block
        _add_box(bm, cx, cy, 0.0, KERB_DEPTH, KERB_DEPTH, h * rng.uniform(0.95, 1.05), yaw)
        return KERB_DEPTH / 2.0
    if variant == 1:                       # raised square pier
        w = KERB_DEPTH * 1.5
        _add_box(bm, cx, cy, 0.0, w, w, h * 1.6, yaw)
        return w / 2.0
    w = KERB_DEPTH * 1.6                   # variant 2: two-tier stepped pier
    _add_box(bm, cx, cy, 0.0, w, w, h * 1.1, yaw)
    _add_box(bm, cx, cy, h * 1.1, w * 0.68, w * 0.68, h * 0.6, yaw)
    return w / 2.0


def _kerb_run(bm, rng, axis, fixed, t0, t1, block_len, yaw):
    """Fill the span t0..t1 along `axis` ('x' or 'y') with individual stone
    blocks, each with its own seeded length / height / depth / offset."""
    t = t0
    while t1 - t > 1.2:
        seg = min(block_len * rng.uniform(0.82, 1.18), t1 - t)
        if seg < 1.2:
            break
        h = config.PLOT_KERB_H * rng.uniform(0.86, 1.14)
        d = KERB_DEPTH * rng.uniform(0.90, 1.10)
        off = rng.uniform(-0.18, 0.18)
        mid = t + seg / 2.0
        if axis == "x":
            _add_box(bm, mid, fixed + off, 0.0, seg - KERB_JOINT, d, h, yaw)
        else:
            _add_box(bm, fixed + off, mid, 0.0, d, seg - KERB_JOINT, h, yaw)
        t += seg


def build_kerbs():
    """Kerb rectangle: flush with the pad edge on three sides, but pulled in
    by STEP_RING_WIDTH on the plaza-facing side. Phase 4's plaza step ring
    already overhangs the pad's first 3 studs (it spans r=PLAZA_OUTER_R..
    +STEP_RING_WIDTH with its underside at GROUND_Z), so a near kerb sitting
    flush at r=135 would be buried inside it and interpenetrate its underside.
    Insetting puts the near kerb immediately OUTSIDE the ring's outer edge,
    where it is both visible and clear."""
    objs = []
    c = config.PLOT_SIZE / 2.0 - KERB_DEPTH / 2.0   # kerb centreline offset
    c_near = c - STEP_RING_WIDTH                    # plaza-facing side, inset
    for i in range(config.PLOT_COUNT):
        rng = random.Random(config.SCATTER_SEED + 1000 * (i + 1))
        yaw = config.plot_yaw(i)
        block_len = KERB_BLOCK_LEN[i]
        variant = KERB_CORNER_VARIANT[i]
        half_gap = STAIR_WIDTH[i] / 2.0 + 0.5           # entrance opening, near side

        bm = bmesh.new()
        inset = 0.0
        for sx in (-c, c):
            for cy in (-c, c_near):
                inset = _kerb_corner(bm, rng, variant, sx, cy, yaw)

        lo, hi = -c + inset, c - inset
        y_hi = c_near - inset
        _kerb_run(bm, rng, "x", -c, lo, hi, block_len, yaw)          # far side (-Y)
        _kerb_run(bm, rng, "y", -c, lo, y_hi, block_len, yaw)        # -X side
        _kerb_run(bm, rng, "y", c, lo, y_hi, block_len, yaw)         # +X side
        # near side (+Y, faces the plaza): split around the entrance stair
        _kerb_run(bm, rng, "x", c_near, lo, -half_gap, block_len, yaw)
        _kerb_run(bm, rng, "x", c_near, half_gap, hi, block_len, yaw)

        objs.append(_finalize(bm, f"DD_Plot_Kerb_{i + 1:02d}", _plot_origin(i)))
    return objs


# ---- entrance stair ---------------------------------------------------------

def build_stairs():
    """Three risers of 1.0 stud each, closing the PLAZA_LIFT -> PLOT_Z drop
    between Phase 4's step ring and the pad. Two solid tread blocks, both
    seated on the pad so nothing floats; the third riser is the drop from the
    lower tread onto the pad itself."""
    objs = []
    near_edge = config.PLOT_SIZE / 2.0                       # local y of the pad's plaza edge
    start_y = near_edge - STEP_RING_WIDTH                    # where p4's step ring lands
    total_drop = config.PLAZA_LIFT - config.PLOT_Z           # 3.0
    rise = total_drop / 3.0
    for i in range(config.PLOT_COUNT):
        yaw = config.plot_yaw(i)
        width = STAIR_WIDTH[i]
        bm = bmesh.new()
        for step in range(2):
            y1 = start_y - step * STAIR_RUN
            y0 = y1 - STAIR_RUN
            height = total_drop - (step + 1) * rise          # 2.0 then 1.0, measured from the pad
            _add_box(bm, 0.0, (y0 + y1) / 2.0, 0.0, width, STAIR_RUN, height, yaw)
        objs.append(_finalize(bm, f"DD_Plot_Steps_{i + 1:02d}", _plot_origin(i)))
    return objs


# ---- carved sign icons ------------------------------------------------------
# Each icon is a list of (u, v, w, h) rectangles in the board's normalised
# face space: u across (-0.5..0.5), v up (-0.5..0.5). Raised ICON_RAISE studs
# proud of the board's plaza-facing surface -- carved relief geometry, never
# a texture and never modelled text (CLAUDE.md: "carved icon, no text").

ICONS = {
    "Anchor": [
        (0.00, -0.05, 0.10, 0.62), (0.00, 0.20, 0.52, 0.10), (0.00, 0.40, 0.16, 0.12),
        (-0.26, -0.32, 0.22, 0.10), (0.26, -0.32, 0.22, 0.10),
        (-0.34, -0.22, 0.10, 0.14), (0.34, -0.22, 0.10, 0.14),
    ],
    "Fish": [
        (0.00, 0.00, 0.60, 0.22), (-0.02, 0.16, 0.42, 0.12), (-0.02, -0.16, 0.42, 0.12),
        (0.32, 0.00, 0.12, 0.24), (0.38, 0.17, 0.16, 0.10), (0.38, -0.17, 0.16, 0.10),
        (-0.18, 0.06, 0.07, 0.07),
    ],
    "Shell": [
        (0.00, -0.32, 0.24, 0.10),
        (-0.28, -0.11, 0.10, 0.34), (-0.14, -0.03, 0.10, 0.50), (0.00, 0.02, 0.10, 0.60),
        (0.14, -0.03, 0.10, 0.50), (0.28, -0.11, 0.10, 0.34),
    ],
    "Net": [
        (-0.24, 0.00, 0.06, 0.66), (0.00, 0.00, 0.06, 0.66), (0.24, 0.00, 0.06, 0.66),
        (0.00, -0.24, 0.66, 0.06), (0.00, 0.00, 0.66, 0.06), (0.00, 0.24, 0.66, 0.06),
        (0.00, 0.36, 0.72, 0.07),
    ],
    "Wave": [
        (-0.10, -0.24, 0.62, 0.10), (0.10, -0.06, 0.62, 0.10), (-0.10, 0.12, 0.62, 0.10),
        (0.30, 0.24, 0.16, 0.10), (-0.30, 0.00, 0.14, 0.09),
    ],
    "Hook": [
        (0.12, 0.18, 0.09, 0.50), (0.12, 0.44, 0.16, 0.10),
        (0.06, -0.14, 0.10, 0.16), (-0.04, -0.26, 0.18, 0.10), (-0.16, -0.18, 0.10, 0.16),
        (-0.16, 0.00, 0.08, 0.18),
    ],
    "Buoy": [
        (0.00, -0.28, 0.24, 0.10), (0.00, -0.16, 0.40, 0.12), (0.00, 0.00, 0.48, 0.18),
        (0.00, 0.16, 0.40, 0.12), (0.00, 0.28, 0.24, 0.10),
        (0.00, 0.02, 0.52, 0.07), (0.00, 0.40, 0.07, 0.16),
    ],
}
ICON_ORDER = ["Anchor", "Fish", "Shell", "Net", "Wave", "Hook", "Buoy"]


# ---- marker post family -----------------------------------------------------

def _marker_geometry(i):
    """Resolve every per-plot varied dimension for plot i, once, so the five
    marker objects all agree."""
    rng = random.Random(config.SCATTER_SEED + 7 * (i + 1))
    mirror = -1.0 if i % 2 else 1.0          # marker swaps sides of the stair
    return {
        "rng": rng,
        "yaw": config.plot_yaw(i),
        "px": mirror * POST_LOCAL_X,
        "py": POST_LOCAL_Y,
        "post_h": POST_H + rng.uniform(-0.6, 0.6),
        "sign_w": SIGN_W + rng.uniform(-0.4, 0.4),
        "arm_reach": ARM_REACH + rng.uniform(-0.3, 0.3),
        "icon": ICON_ORDER[i],
    }


def build_markers():
    objs = []
    for i in range(config.PLOT_COUNT):
        g = _marker_geometry(i)
        yaw, px, py = g["yaw"], g["px"], g["py"]
        loc = _plot_origin(i)
        tag = f"{i + 1:02d}"

        arm_z = g["post_h"] - 0.8            # bracket underside, just under the cap
        sign_top = arm_z - SIGN_LINK
        sign_base = sign_top - SIGN_H
        sign_y = py + g["arm_reach"] - 0.8

        # 1. timber post + cap
        bm = bmesh.new()
        _add_box(bm, px, py, 0.0, POST_W, POST_W, g["post_h"], yaw)
        _add_box(bm, px, py, g["post_h"], POST_CAP_W, POST_CAP_W, POST_CAP_H, yaw)
        objs.append(_finalize(bm, f"DD_Marker_Plot_{tag}_Post", loc))

        # 2. iron bracket: arm, gusset, sign links, lantern hanger
        bm = bmesh.new()
        arm_mid = py + g["arm_reach"] / 2.0
        _add_box(bm, px, arm_mid, arm_z, ARM_W, g["arm_reach"], ARM_H, yaw)
        _add_box(bm, px, py + 1.1, arm_z - 1.4, ARM_W, 1.6, 1.4, yaw)          # gusset
        for side in (-1.0, 1.0):
            _add_box(bm, px + side * (g["sign_w"] / 2.0 - 0.8), sign_y,
                     sign_top, 0.25, 0.25, SIGN_LINK, yaw)                      # sign links
        lantern_y = py + g["arm_reach"] * 0.36
        _add_box(bm, px, lantern_y, arm_z - LANTERN_HANGER, 0.25, 0.25, LANTERN_HANGER, yaw)
        objs.append(_finalize(bm, f"DD_Marker_Plot_{tag}_Bracket", loc))

        # 3. hanging carved sign: board + the plot's own carved icon in relief
        bm = bmesh.new()
        _add_box(bm, px, sign_y, sign_base, g["sign_w"], SIGN_D, SIGN_H, yaw)
        face_y = sign_y + SIGN_D / 2.0
        for u, v, w, h in ICONS[g["icon"]]:
            _add_box(
                bm,
                px + u * g["sign_w"],
                face_y + ICON_RAISE / 2.0,
                sign_base + (v + 0.5) * SIGN_H - (h * SIGN_H) / 2.0,
                w * g["sign_w"], ICON_RAISE, h * SIGN_H, yaw,
            )
        objs.append(_finalize(bm, f"DD_Marker_Plot_{tag}_Sign", loc))

        # 4. unlit lantern (no emission -- Phase 8 paints it iron/glass, not gold)
        bm = bmesh.new()
        lz = arm_z - LANTERN_HANGER - (LANTERN_PLATE_H + LANTERN_BODY_H
                                       + LANTERN_ROOF_H + LANTERN_FINIAL_H)
        _add_box(bm, px, lantern_y, lz, LANTERN_BODY_W + 0.4, LANTERN_BODY_W + 0.4,
                 LANTERN_PLATE_H, yaw)
        _add_box(bm, px, lantern_y, lz + LANTERN_PLATE_H, LANTERN_BODY_W, LANTERN_BODY_W,
                 LANTERN_BODY_H, yaw)
        _add_pyramid(bm, px, lantern_y, lz + LANTERN_PLATE_H + LANTERN_BODY_H,
                     LANTERN_BODY_W + 0.6, LANTERN_ROOF_H, yaw)
        _add_box(bm, px, lantern_y, lz + LANTERN_PLATE_H + LANTERN_BODY_H + LANTERN_ROOF_H,
                 0.35, 0.35, LANTERN_FINIAL_H, yaw)
        lantern = _finalize(bm, f"DD_Marker_Plot_{tag}_Lantern", loc)
        # Mood lever 1: none of the seven plot lanterns is a lit site, so their
        # glass goes in the glass slot for Phase 8 to paint dark. The band is
        # local, and _finalize has already put local Z=0 at the plate's base.
        dd_mood.mark_glass(lantern, LANTERN_PLATE_H - 0.01,
                           LANTERN_PLATE_H + LANTERN_BODY_H + 0.01)
        objs.append(lantern)

        # 5. interactable plaque on the post's plaza-facing side. Geometry only;
        #    Phase 8 paints it biolume_cyan (already on validate.py's
        #    INTERACTABLE_NAME_HINTS allowlist as "DD_Marker_Plot").
        bm = bmesh.new()
        _add_box(bm, px, py + POST_W / 2.0 + PLAQUE_D / 2.0, PLAQUE_Z,
                 PLAQUE_W, PLAQUE_D, PLAQUE_H, yaw)
        objs.append(_finalize(bm, f"DD_Marker_Plot_{tag}_Plaque", loc))
    return objs


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def build():
    dd_scene.ensure_collections()
    purge()
    build_kerbs()
    build_stairs()
    build_markers()


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=1000.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p5_top_ortho.png"), xray=True)

    # Oblique 3/4 detail on two plots. A pitch-free eye camera cannot see into
    # the pads (they sit 1.5 studs BELOW the surrounding terrain, so the plaza
    # rim occludes them from a standing gaze), hence setup_look_at_camera --
    # this is the frame that actually proves pad + kerb + entrance stair +
    # post + sign + lantern all line up.
    for idx, out_name in ((0, "p5_plot_detail.png"), (3, "p5_plot_detail_b.png")):
        mirror = -1.0 if idx % 2 else 1.0
        cam_x, cam_y = to_world(idx, mirror * 22.0, 78.0)
        tgt_x, tgt_y = to_world(idx, mirror * 5.0, 26.0)
        cam = dd_scene.setup_look_at_camera(
            f"RenderCam_PlotDetail{idx}",
            location=(cam_x, cam_y, 34.0),
            target=(tgt_x, tgt_y, config.PLOT_Z + 2.0),
            fov_deg=55.0,
        )
        dd_scene.render_to_file(cam, os.path.join(renders_dir, out_name), xray=False)

    # One true eye-level frame: what a player walking the plot lane actually
    # sees of the marker (sign readable, lantern hanging, kerb line running).
    mirror0 = 1.0
    eye_x, eye_y = to_world(0, mirror0 * 4.0, 66.0)
    eye_cam = dd_scene.setup_eye_camera(
        "RenderCam_PlotEye",
        location=(eye_x, eye_y, 6.0),
        facing_deg=config.PLOT_ANGLES_DEG[0],
        fov_deg=60.0,
    )
    dd_scene.render_to_file(eye_cam, os.path.join(renders_dir, "p5_plot_eye.png"), xray=False)

    # Square top-down over the whole plot ring so all seven markers, kerbs and
    # entrance stairs can be counted in one frame (a 16:9 crop loses the north
    # and south plots at |y| = 168.8).
    ring_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=470.0, height=700.0)
    dd_scene.render_to_file(
        ring_cam, os.path.join(renders_dir, "p5_plot_ring.png"),
        resolution=(1400, 1400), xray=True,
    )


if __name__ == "__main__":
    build()
    capture_renders()
