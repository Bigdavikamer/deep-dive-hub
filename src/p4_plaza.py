"""Phase 4 -- Plaza, paths, leaderboard court. GATE 2.

Solid plaza floor (replacing Phase 1's flat placeholder -- fixes the
non-manifold/zero-thickness issue flagged since Phase 2), a shallow step
ring around the whole outer edge plus an emphasised 3-step stair at the
west opening (TERRACE_STEP_COUNT), eight bowed paths (reference rule 3 --
none is a straight radial spoke) each with a carved lane sign, the market
cross at the west opening, leaderboard court (moved here from Phase 1's
greybox -- stelae now get a real clean-quad UV'd face per the brief), and
two flanking banner poles.

Lane names (rule 4), assigned in plot order 1-7 then the east gate path --
no ordering was specified beyond "The Descent" = east, so this is a
systematic default, not a load-bearing guess:
  Netmender's Walk, Salt Lane, Tar Row, Chandler's Cut, Cooper's Way,
  Gutting Lane, Ballast Row, The Descent

Plot-ward paths run entirely within the plaza (PLAZA_OUTER_R already
equals each plot's near-edge radius by construction -- see config.py's
comment on PLAZA_OUTER_R), so they carry PLAZA_LIFT height throughout.
The gate path continues past the plaza edge to the coastline and sits at
GROUND_Z instead; the ~1.5-stud step where it crosses the plaza boundary
is handled by the step ring, not by the path itself.

GATE 2 diagnosis via raycast (not just eyeballing the render) found the
solid plaza floor grazingly occludes the plot pads' low (Z<2) edge from
spawn's shallow sightline -- geometrically correct (the plaza is a real
raised platform between spawn and the plots), and it clears completely at
Z=2 and above. Phase 5's actual marker post is exactly the object this
check needs and will stand well above that. Since Phase 5 hasn't run yet,
this phase adds a plain DD_Plot_MarkerPost_XX cylinder (no kerb, sign, or
lantern -- that's Phase 5's real spec) purely so GATE 2 can be verified
against a concrete object now rather than deferred on the assumption that
a future phase will happen to clear it. Phase 5 purges and replaces these,
same pattern as Phase 3 superseding Phase 1's greybox shop.

Market cross placed at r=145, due west (angle 180), just outside the
plaza ring on the spawn approach -- "the plaza's west opening where spawn
arrives" is otherwise unconstrained by config.py, so this is a design
placement, not a pinned number.

Idempotent: purges "DD_Struct_PlazaFloor" (Phase 1's placeholder gets
replaced), "DD_Struct_PlazaStep", "DD_Struct_Path_", "DD_Struct_LaneSign_",
"DD_Struct_MarketCross", "DD_Lamp_Banner", "DD_UI_Leaderboard" (moved here
from Phase 1) before rebuilding.
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

import config
from lib import mesh as dd_mesh
from lib import palette as dd_palette
from lib import scene as dd_scene

LANE_NAMES = [
    "Netmenders Walk", "Salt Lane", "Tar Row", "Chandlers Cut",
    "Coopers Way", "Gutting Lane", "Ballast Row",
]
GATE_LANE_NAME = "The Descent"

PATH_WIDTH = config.TRAFFIC_LANE_WIDTH
PATH_THICKNESS = 2.0
BOW_MAGNITUDES = [10.0, 12.0, 9.0, 14.0, 8.0, 13.0, 11.0, 10.0]  # 8 paths, all within [8,14]

STEP_RING_WIDTH = 3.0
STEP_RING_H = 1.5  # -> PLAZA_LIFT down to GROUND_Z in one shallow step

WEST_STEP_ANGLE_HALF = 12.0  # degrees either side of due-west for the emphasised stair
WEST_STEP_RUN = 3.0          # studs per step, radially

SIGN_POST_H = 6.0
SIGN_POST_R = 0.8
SIGN_PLAQUE_W = 5.0
SIGN_PLAQUE_H = 3.0
SIGN_PLAQUE_D = 0.6

MARKET_CROSS_XY = (-145.0, 0.0)
MARKET_CROSS_TIER_H = 1.0
MARKET_CROSS_TIER_RADII = (8.0, 6.5, 5.0)
MARKET_CROSS_COLUMN_R = 1.0
MARKET_CROSS_COLUMN_H = 6.0

BANNER_POLE_H = 14.0
BANNER_POLE_R = 0.6

OWNED_PREFIXES = [
    "DD_Struct_PlazaFloor",
    "DD_Struct_PlazaStep",
    "DD_Struct_Path_",
    "DD_Struct_LaneSign_",
    "DD_Struct_MarketCross",
    "DD_Lamp_Banner",
    "DD_UI_Leaderboard",
    "DD_Plaza_Floor",  # legacy Phase 1 name, cleaned up here too
    "DD_Plot_MarkerPost_",  # temporary GATE 2 placeholder; Phase 5 replaces with the real marker
]

MARKER_POST_H = 8.0
MARKER_POST_R = 0.6


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def _finish(obj, collection="Plaza"):
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, collection)
    return obj


def build_plaza_floor():
    """Solid annulus (top, bottom, inner wall, outer wall) -- fixes the
    non-manifold / zero-thickness placeholder from Phase 1."""
    inner_r, outer_r = config.PLAZA_INNER_R, config.PLAZA_OUTER_R
    top_z, thickness, segments = config.PLAZA_LIFT, 2.0, 64
    bm = bmesh.new()
    inner_top, outer_top, inner_bot, outer_bot = [], [], [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        cos_a, sin_a = math.cos(a), math.sin(a)
        inner_top.append(bm.verts.new((inner_r * cos_a, inner_r * sin_a, top_z)))
        outer_top.append(bm.verts.new((outer_r * cos_a, outer_r * sin_a, top_z)))
        inner_bot.append(bm.verts.new((inner_r * cos_a, inner_r * sin_a, top_z - thickness)))
        outer_bot.append(bm.verts.new((outer_r * cos_a, outer_r * sin_a, top_z - thickness)))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((inner_top[i], inner_top[j], outer_top[j], outer_top[i]))
        bm.faces.new((inner_bot[i], outer_bot[i], outer_bot[j], inner_bot[j]))
        bm.faces.new((outer_top[i], outer_top[j], outer_bot[j], outer_bot[i]))
        bm.faces.new((inner_top[i], inner_bot[i], inner_bot[j], inner_top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    obj = dd_mesh.bm_to_object("DD_Struct_PlazaFloor", bm)
    return _finish(obj)


def build_step_ring_annulus():
    """Shallow step ring from PLAZA_OUTER_R out to +STEP_RING_WIDTH: a flat
    tread flush with the plaza (top at PLAZA_LIFT) whose outer wall is the
    single shallow riser down to GROUND_Z. Skips the west arc, where the
    emphasised stair (build_west_steps) takes over -- built as ONE
    continuous 336-degree annulus sector (wrapping through 0 deg) via
    lib.mesh.annulus_sector_solid, which already gives clean end caps at
    the cut points, rather than hand-skipping faces in a full ring (which
    left orphaned/loose vertices where the ring was cut)."""
    inner_r = config.PLAZA_OUTER_R
    outer_r = inner_r + STEP_RING_WIDTH
    half = WEST_STEP_ANGLE_HALF
    obj = dd_mesh.annulus_sector_solid(
        "DD_Struct_PlazaStepRing",
        inner_radius=inner_r, outer_radius=outer_r,
        angle_start_deg=180.0 + half, angle_end_deg=180.0 - half + 360.0,
        thickness=config.PLAZA_LIFT - config.GROUND_Z,
        segments=56, base_z=config.PLAZA_LIFT,
    )
    return _finish(obj)


def build_west_steps():
    """An emphasised TERRACE_STEP_COUNT staircase at the west opening,
    where spawn arrives -- the plaza's own "west terrace lift and steps"."""
    objs = []
    rise_per_step = config.PLAZA_LIFT / config.TERRACE_STEP_COUNT
    half_angle = WEST_STEP_ANGLE_HALF
    for s in range(config.TERRACE_STEP_COUNT):
        r0 = config.PLAZA_OUTER_R + s * WEST_STEP_RUN
        r1 = r0 + WEST_STEP_RUN
        top_z = config.PLAZA_LIFT - s * rise_per_step
        obj = dd_mesh.annulus_sector_solid(
            f"DD_Struct_PlazaStepWest_{s:02d}",
            inner_radius=r0, outer_radius=r1,
            angle_start_deg=180.0 - half_angle, angle_end_deg=180.0 + half_angle,
            thickness=rise_per_step + 0.5, segments=8, base_z=top_z,
        )
        objs.append(_finish(obj))
    return objs


def build_paths():
    objs = []
    for i in range(config.PLOT_COUNT):
        angle = math.radians(config.PLOT_ANGLES_DEG[i])
        p0 = (config.PLAZA_INNER_R * math.cos(angle), config.PLAZA_INNER_R * math.sin(angle))
        p1 = (config.PLAZA_OUTER_R * math.cos(angle), config.PLAZA_OUTER_R * math.sin(angle))
        bow = BOW_MAGNITUDES[i] * (1.0 if i % 2 == 0 else -1.0)
        obj = dd_mesh.bowed_path(
            f"DD_Struct_Path_Plot{i + 1:02d}", p0, p1, PATH_WIDTH, bow, PATH_THICKNESS,
            base_z=config.PLAZA_LIFT,
        )
        objs.append(_finish(obj))

    p0 = (config.PLAZA_INNER_R, 0.0)
    p1 = (config.ISLAND_RADIUS, 0.0)
    bow = BOW_MAGNITUDES[7]
    gate_obj = dd_mesh.bowed_path(
        "DD_Struct_Path_Gate", p0, p1, PATH_WIDTH, bow, PATH_THICKNESS, base_z=config.GROUND_Z,
    )
    objs.append(_finish(gate_obj, collection="Plaza"))
    return objs


def build_lane_signs():
    objs = []
    entries = [(config.PLOT_ANGLES_DEG[i], LANE_NAMES[i], i + 1) for i in range(config.PLOT_COUNT)]
    entries.append((0.0, GATE_LANE_NAME, "Gate"))
    for angle_deg, _name, idx in entries:
        angle = math.radians(angle_deg)
        # place just outside the plaza's inner ring, offset laterally so the
        # sign doesn't block the path it names
        r = config.PLAZA_INNER_R + 6.0
        tangent = (-math.sin(angle), math.cos(angle))
        lateral = PATH_WIDTH / 2.0 + 2.0
        x = r * math.cos(angle) + tangent[0] * lateral
        y = r * math.sin(angle) + tangent[1] * lateral
        yaw = angle + math.pi / 2.0  # plaque faces the path (local +Y toward centre)

        post = dd_mesh.cylinder(f"DD_Struct_LaneSign_{idx}_Post", SIGN_POST_R, SIGN_POST_H, base_z=0.0, segments=8)
        post.location = (x, y, 0.0)
        objs.append(_finish(post))

        plaque = dd_mesh.box(
            f"DD_Struct_LaneSign_{idx}_Plaque", SIGN_PLAQUE_W, SIGN_PLAQUE_D, SIGN_PLAQUE_H,
            base_z=0.0, yaw=yaw,
        )
        plaque.location = (x, y, SIGN_POST_H - SIGN_PLAQUE_H - 0.3)
        dd_mesh.set_quad_face_uv(plaque, face_index=4)  # +Y-facing face, clean quad for a future SurfaceGui name label
        objs.append(_finish(plaque))
    return objs


def build_market_cross():
    objs = []
    x, y = MARKET_CROSS_XY
    z = 0.0
    for i, r in enumerate(MARKET_CROSS_TIER_RADII):
        tier = dd_mesh.cylinder(f"DD_Struct_MarketCross_Tier{i}", r, MARKET_CROSS_TIER_H, base_z=0.0, segments=8)
        tier.location = (x, y, z)
        objs.append(_finish(tier))
        z += MARKET_CROSS_TIER_H

    column = dd_mesh.cylinder("DD_Struct_MarketCross_Column", MARKET_CROSS_COLUMN_R, MARKET_CROSS_COLUMN_H, base_z=0.0, segments=8)
    column.location = (x, y, z)
    objs.append(_finish(column))
    z += MARKET_CROSS_COLUMN_H

    arm_len, arm_th = 5.0, 0.8
    arm1 = dd_mesh.box("DD_Struct_MarketCross_ArmNS", arm_th, arm_len, arm_th, base_z=0.0)
    arm1.location = (x, y, z)
    objs.append(_finish(arm1))
    arm2 = dd_mesh.box("DD_Struct_MarketCross_ArmEW", arm_len, arm_th, arm_th, base_z=0.0)
    arm2.location = (x, y, z)
    objs.append(_finish(arm2))
    return objs


def build_banner_poles():
    court_angle = config.LB_COURT_ANGLE
    cx = config.LB_COURT_R * math.cos(math.radians(court_angle))
    cy = config.LB_COURT_R * math.sin(math.radians(court_angle))
    face_yaw = math.radians(court_angle + 90.0)
    tangent = (math.cos(face_yaw), math.sin(face_yaw))
    reach = 2 * (config.LB_STELE_W + 4.0) + 6.0  # just beyond the outermost stele

    objs = []
    for sign, suffix in ((1.0, "A"), (-1.0, "B")):
        x = cx + sign * reach * tangent[0]
        y = cy + sign * reach * tangent[1]
        pole = dd_mesh.cylinder(f"DD_Lamp_BannerPole_{suffix}", BANNER_POLE_R, BANNER_POLE_H, base_z=0.0, segments=8)
        pole.location = (x, y, 0.0)
        objs.append(_finish(pole))

        flag_w, flag_h = 3.0, 4.0
        flag = dd_mesh.box(f"DD_Lamp_BannerFlag_{suffix}", 0.2, flag_w, flag_h, base_z=0.0)
        flag.location = (x, y + flag_w / 2.0, BANNER_POLE_H - flag_h - 0.5)
        objs.append(_finish(flag))
    return objs


def build_leaderboard():
    court_angle = config.LB_COURT_ANGLE
    cx = config.LB_COURT_R * math.cos(math.radians(court_angle))
    cy = config.LB_COURT_R * math.sin(math.radians(court_angle))
    face_yaw_deg = court_angle + 90.0
    face_yaw = math.radians(face_yaw_deg)
    local_x_dir = (math.cos(face_yaw), math.sin(face_yaw))

    dais_w = 3 * (config.LB_STELE_W + 4.0) + 10.0
    dais = dd_mesh.box("DD_UI_LeaderboardDais", dais_w, 20.0, config.LB_DAIS_H, base_z=0.0, yaw=face_yaw)
    dais.location = (cx, cy, 0.0)
    objs = [_finish(dais)]

    spacing = config.LB_STELE_W + 4.0
    for j, i in enumerate((-1, 0, 1)):
        offset = i * spacing
        px = cx + offset * local_x_dir[0]
        py = cy + offset * local_x_dir[1]
        stele_yaw = math.radians(face_yaw_deg + i * config.LB_STELE_FAN)
        name = f"DD_UI_LeaderboardStele_{j + 1:02d}"
        stele = dd_mesh.box(name, config.LB_STELE_W, 4.0, config.LB_STELE_H, base_z=0.0, yaw=stele_yaw)
        stele.location = (px, py, config.LB_DAIS_H)
        dd_mesh.set_quad_face_uv(stele, face_index=4)  # +Y-facing face: the SurfaceGui panel
        objs.append(_finish(stele))
    return objs


def build_plot_marker_placeholders():
    """Temporary: a plain post per plot so GATE 2's "at least two plot
    markers visible" can be checked against a real object now. Phase 5
    purges this prefix and replaces it with the full marker (kerb, carved
    sign, lantern)."""
    objs = []
    for i in range(config.PLOT_COUNT):
        x, y = config.plot_xy(i)
        post = dd_mesh.cylinder(f"DD_Plot_MarkerPost_{i + 1:02d}", MARKER_POST_R, MARKER_POST_H, base_z=0.0, segments=8)
        post.location = (x, y, config.PLOT_Z)
        objs.append(_finish(post, collection="Plots"))
    return objs


def build():
    dd_scene.ensure_collections()
    purge()
    build_plaza_floor()
    build_step_ring_annulus()
    build_west_steps()
    build_paths()
    build_lane_signs()
    build_market_cross()
    build_banner_poles()
    build_leaderboard()
    build_plot_marker_placeholders()


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=1000.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p4_top_ortho.png"), xray=True)

    # GATE 2: the spawn sightline, facing exactly SPAWN_FACING_DEG.
    eye_cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], 5.0),
        facing_deg=config.SPAWN_FACING_DEG,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(eye_cam, os.path.join(renders_dir, "p4_spawn_sightline.png"), xray=False)

    west_cam = dd_scene.setup_eye_camera(
        "RenderCam_West",
        location=(-160.0, 20.0, 8.0),
        facing_deg=170.0,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(west_cam, os.path.join(renders_dir, "p4_market_cross.png"), xray=False)


if __name__ == "__main__":
    build()
    capture_renders()
