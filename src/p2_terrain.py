"""Phase 2 -- Terrain shell.

Replaces Phase 1's flat placeholder island wedge with the real coastline:
seeded per-angle jitter (no two of the 96 rim samples identical), two rock
outcrop bulges, one tidepool coastline notch, the west-side terracing (3
stepped bands, per CLAUDE.md reference rule 2), split into 4 quadrant
meshes to stay under the 8,000-tri/mesh terrain budget. Plus the tide pool
basin and the ocean floor slope beyond the gate.

Design notes / scope calls (flagged, not silently assumed):
  - Jitter/outcrop/notch amplitude is TAPERED TO ZERO at the two exact gate
    boundary angles (+/-GATE_HALF_ANGLE) so the coastline still meets
    Phase 1's beach ramp corners exactly -- no seam, no rebuild of Phase 1.
  - The flat-to-terraced transition happens between MID_RADIUS (215, just
    outside the plot ring's outer reach) and the coastline.
  - PLOT POCKETS (added after Phase 5): the plot ring carries seven recessed
    terraces. Without them the pads at PLOT_Z=-1.5 were entirely buried --
    this terrain was solid at GROUND_Z from the centre out to MID_RADIUS, so
    the walkable surface inside every plot was terrain, not pad, and only
    ~0.5 studs of Phase 5's 2-stud kerb cleared the ground. Each pocket is
    an annular sector sized to contain the whole 70x70 pad (its near corners
    reach r=139.5 at +/-14.5 deg, its far corners r=208 at +/-9.7 deg), so
    POCKET_HALF_ANGLE=15.5 and r 138..210 enclose it with margin, and the
    5.3 deg left between neighbouring pockets stays as a solid verge.
    POCKET_INNER_R is 138 and not the pad's own near edge at 135 on purpose:
    135..138 is Phase 4's plaza step ring, and starting the recess any
    further in would undercut it. The floor sits 0.4 below PLOT_Z so the pad
    reads as a raised paving slab inside the terrace rather than z-fighting
    a coplanar floor, and the sector-minus-square remainder becomes real
    ground for Phase 7's "plot_surround" scatter zone to sit on.
  - Tide pool rim Z is set to a modest local value (2.0), not the full
    WEST_TERRACE_LIFT -- keeps it visually coherent with the flat terrain
    immediately around it in this pass; later phases can grade the ground
    between them.
  - The tide pool basin is intentionally open at the rim (non-manifold
    boundary edges) -- it's a pit meant to sit inside the surrounding
    terrain quadrant mesh, not a sealed standalone solid; sealing it would
    mean cutting a matching hole in the terrain mesh and welding the two,
    which is real terrain-boolean work out of this phase's scope. Flagged
    in validate.py output, not silently ignored.
  - DD_Struct_PlazaFloor (Phase 1's flat annulus placeholder) still fails
    validate.py's manifold and origin-at-base checks -- pre-existing from
    Phase 1 (a zero-thickness placeholder), unrelated to this phase's work,
    and Phase 4 rebuilds it as real plaza geometry. Left untouched rather
    than reaching into Phase 4's scope.

Idempotent: purges "DD_Terrain_Island" (catches both Phase 1's old single
wedge and any previous run's quadrants), "DD_Terrain_TidePool", and
"DD_Terrain_OceanFloor" before rebuilding.
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
from mathutils import noise

import config
from lib import mesh as dd_mesh
from lib import palette as dd_palette
from lib import scene as dd_scene

OWNED_PREFIXES = [
    "DD_Terrain_Island",
    "DD_Terrain_TidePool",
    "DD_Terrain_OceanFloor",
]

MID_RADIUS = 215.0          # flat-to-terraced transition start (just past plot outer reach ~219.5)
TAPER_DEG = 12.0            # jitter/outcrop/notch fade to 0 within this many degrees of the gate edge
ISLAND_THICKNESS = 6.0

OUTCROP_ANGLES = (70.0, 250.0)   # between plot lanes, away from the gate/tidepool
OUTCROP_MAGNITUDE = 18.0
OUTCROP_HALF_WIDTH = 14.0

_POOL_ANGLE = math.degrees(math.atan2(config.POOL_XY[1], config.POOL_XY[0]))  # ~167.3 deg
NOTCH_MAGNITUDE = 16.0
NOTCH_HALF_WIDTH = 10.0

TIDEPOOL_RIM_Z = 2.0

# recessed plot terraces -- see the pocket note in the module docstring
POCKET_INNER_R     = 138.0   # outer edge of Phase 4's plaza step ring
POCKET_OUTER_R     = 210.0   # clears the pad's far corners at r=208
POCKET_HALF_ANGLE  = 15.5    # clears the pad's near corners at +/-14.5 deg
POCKET_FLOOR_Z     = config.PLOT_Z - 0.4

noise.seed_set(config.SCATTER_SEED)


def _smooth_bump(angle_deg, center_deg, half_width_deg):
    d = abs(((angle_deg - center_deg + 180.0) % 360.0) - 180.0)
    if d >= half_width_deg:
        return 0.0
    x = d / half_width_deg
    return (1.0 - x * x) ** 2


def _gate_taper(angle_deg):
    """0 exactly at +/-GATE_HALF_ANGLE, ramping to 1 within TAPER_DEG."""
    d_near = abs(angle_deg - config.GATE_HALF_ANGLE)
    d_far = abs(angle_deg - (360.0 - config.GATE_HALF_ANGLE))
    d = min(d_near, d_far)
    if d >= TAPER_DEG:
        return 1.0
    x = d / TAPER_DEG
    return x * x * (3.0 - 2.0 * x)  # smoothstep


def _jitter(angle_deg):
    t = math.radians(angle_deg)
    p1 = mathutils.Vector((math.cos(t) * 1.5, math.sin(t) * 1.5, 0.0))
    p2 = mathutils.Vector((math.cos(t) * 4.0, math.sin(t) * 4.0, 10.0))
    n = noise.noise(p1) * 0.7 + noise.noise(p2) * 0.3
    return n * config.COAST_JITTER


def coast_radius(angle_deg):
    """Island rim radius at this angle: base + jitter + outcrops - notch,
    all tapered to exactly ISLAND_RADIUS at the gate boundary angles."""
    delta = _jitter(angle_deg)
    for oc in OUTCROP_ANGLES:
        delta += OUTCROP_MAGNITUDE * _smooth_bump(angle_deg, oc, OUTCROP_HALF_WIDTH)
    delta -= NOTCH_MAGNITUDE * _smooth_bump(angle_deg, _POOL_ANGLE, NOTCH_HALF_WIDTH)
    return config.ISLAND_RADIUS + delta * _gate_taper(angle_deg)


def terrace_z(angle_deg):
    """West-side terracing: 3 stepped bands, 0 on the east half."""
    d = abs(((angle_deg - 180.0 + 180.0) % 360.0) - 180.0)
    if d >= 90.0:
        return 0.0
    if d < 30.0:
        return config.WEST_TERRACE_LIFT
    if d < 60.0:
        return config.WEST_TERRACE_LIFT * 2.0 / 3.0
    return config.WEST_TERRACE_LIFT * 1.0 / 3.0


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def plot_pockets():
    """One recessed terrace per plot, as (a_min, a_max, r_min, r_max, floor_z)."""
    return [
        (a - POCKET_HALF_ANGLE, a + POCKET_HALF_ANGLE,
         POCKET_INNER_R, POCKET_OUTER_R, POCKET_FLOOR_Z)
        for a in config.PLOT_ANGLES_DEG
    ]


def _angle_samples(a0, a1, per_degree, boundaries):
    """Uniform coastline sampling with every pocket edge forced onto an exact
    grid line -- a uniform sample within 0.05 deg of a pocket edge is dropped
    in favour of the edge, never the other way round, since the pocket bounds
    are what has to land exactly."""
    n = max(4, round((a1 - a0) * per_degree))
    uniform = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
    inside = [b for b in boundaries if a0 + 0.05 < b < a1 - 0.05]
    kept = [u for u in uniform if all(abs(u - b) > 0.05 for b in inside)]
    return sorted(kept + inside)


def build_quadrants():
    arc = 360.0 - 2.0 * config.GATE_HALF_ANGLE
    per_degree = config.COAST_SEGMENTS / arc
    ring_radii = [0.0, POCKET_INNER_R, POCKET_OUTER_R, MID_RADIUS]
    pockets = plot_pockets()
    boundaries = [edge for p in pockets for edge in (p[0], p[1])]
    quadrants = [
        ("NE", config.GATE_HALF_ANGLE, 90.0),
        ("NW", 90.0, 180.0),
        ("SW", 180.0, 270.0),
        ("SE", 270.0, 360.0 - config.GATE_HALF_ANGLE),
    ]
    objs = []
    for suffix, a0, a1 in quadrants:
        # three of the seven pockets straddle a quadrant boundary (at 90, 180
        # and 270); each half is passed to its own quadrant clipped to that
        # quadrant's arc, and terrain_quadrant leaves the seam wall-less so
        # the recess reads as one terrace across the two meshes.
        clipped = [
            (max(pa0, a0), min(pa1, a1), pr0, pr1, floor_z)
            for pa0, pa1, pr0, pr1, floor_z in pockets
            if min(pa1, a1) - max(pa0, a0) > 0.05
        ]
        obj = dd_mesh.terrain_quadrant(
            f"DD_Terrain_Island_{suffix}",
            angle_samples_deg=_angle_samples(a0, a1, per_degree, boundaries),
            ring_radii=ring_radii,
            outer_radius_fn=coast_radius,
            outer_z_fn=terrace_z,
            thickness=ISLAND_THICKNESS,
            pockets=clipped,
            base_z=config.GROUND_Z,
        )
        dd_mesh.shade_flat(obj)
        dd_scene.set_origin_to_base(obj)
        dd_scene.link_to_collection(obj, "Terrain")
        objs.append(obj)
    return objs


def build_tidepool():
    cx, cy = config.POOL_XY
    r = config.POOL_RADIUS
    rim_z = TIDEPOOL_RIM_Z
    floor_z = config.POOL_DEPTH
    segments = 24

    bm = None
    import bmesh
    bm = bmesh.new()
    rim = []
    floor = []
    for i in range(segments):
        t = 2.0 * math.pi * i / segments
        x, y = cx + r * math.cos(t), cy + r * math.sin(t)
        rim.append(bm.verts.new((x, y, rim_z)))
        fx, fy = cx + (r * 0.6) * math.cos(t), cy + (r * 0.6) * math.sin(t)
        floor.append(bm.verts.new((fx, fy, floor_z)))
    floor_center = bm.verts.new((cx, cy, floor_z))
    bm.verts.ensure_lookup_table()

    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((rim[i], rim[j], floor[j], floor[i]))          # sloped basin wall
        bm.faces.new((floor_center, floor[i], floor[j]))            # basin floor fan

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    obj = dd_mesh.bm_to_object("DD_Terrain_TidePool", bm)
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, "Terrain")
    return obj


def build_ocean_floor():
    near_x = config.ISLAND_RADIUS + config.BEACH_RUN
    far_x = 700.0
    half_w = 300.0
    top_near_z = config.OCEAN_FLOOR_NEAR
    top_far_z = config.OCEAN_FLOOR_FAR
    bottom_z = top_far_z - 20.0

    verts = [
        (near_x, -half_w, top_near_z), (near_x, half_w, top_near_z),
        (far_x, half_w, top_far_z), (far_x, -half_w, top_far_z),
        (near_x, -half_w, bottom_z), (near_x, half_w, bottom_z),
        (far_x, half_w, bottom_z), (far_x, -half_w, bottom_z),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5),
        (0, 4, 5, 1), (3, 2, 6, 7),
        (0, 3, 7, 4), (1, 5, 6, 2),
    ]
    obj = dd_mesh.new_mesh_object("DD_Terrain_OceanFloor", verts, faces)
    dd_mesh.recalc_normals_outward(obj)
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, "Terrain")
    return obj


def build():
    dd_scene.ensure_collections()
    purge()
    build_quadrants()
    build_tidepool()
    build_ocean_floor()


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=1000.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p2_top_ortho.png"), xray=True)

    eye_cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], 5.0),
        facing_deg=config.SPAWN_FACING_DEG,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(eye_cam, os.path.join(renders_dir, "p2_spawn_eye.png"), xray=False)

    # plot pocket check: oblique from over the plaza rim down into plot 4's
    # recessed terrace, the one view that shows whether the pad is actually
    # exposed and how the plaza edge, entrance stair and pocket wall meet.
    pocket_cam = dd_scene.setup_look_at_camera(
        "RenderCam_PlotPocket",
        location=(-96.0, 26.0, 42.0),
        target=(config.plot_xy(3)[0], config.plot_xy(3)[1], config.PLOT_Z),
        fov_deg=55.0,
    )
    dd_scene.render_to_file(pocket_cam, os.path.join(renders_dir, "p2_plot_pocket.png"), xray=False)

    # west-terrace / tidepool check angle
    west_cam = dd_scene.setup_eye_camera(
        "RenderCam_West",
        location=(-100.0, 60.0, 15.0),
        facing_deg=200.0,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(west_cam, os.path.join(renders_dir, "p2_west_terrace.png"), xray=False)


if __name__ == "__main__":
    build()
    capture_renders()
