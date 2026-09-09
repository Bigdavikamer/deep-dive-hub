"""Phase 1 -- Greybox. Primitives only, correct dimensions, zero detail.

Island disc (with the gate arc already open -- built directly as a pie
wedge, never a boolean cut), shop box, spire cylinder, plaza annulus, seven
plot pads, beach ramp wedge, two dock planks, leaderboard stelae + dais,
spawn marker.

Two dimensions aren't in config.py and had to be inferred for this greybox
pass (flagged, not silently picked -- see the Phase 1 gate summary):
  DOCK_WIDTH    = 10.0  studs (walkway width; DOCK_LENGTH/OFFSET are given, width isn't)
  SPIRE_RADIUS  = 5.0   studs (only the peak height, Z=95, is specified)
Both are cheap to change later -- nothing else in the layout depends on them.

Idempotent: purges every object it owns by exact-name / prefix before
rebuilding, per CLAUDE.md operating rule 2.
"""
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bpy

import config
from lib import mesh as dd_mesh
from lib import palette as dd_palette
from lib import scene as dd_scene

DOCK_WIDTH = 10.0     # inferred -- not in config.py, see module docstring
SPIRE_RADIUS = 5.0    # inferred -- not in config.py, see module docstring

OWNED_PREFIXES = [
    "DD_Terrain_Island",
    "DD_Terrain_Beach",
    "DD_Struct_Shop",
    "DD_Struct_Spire",
    "DD_Plaza_Floor",
    "DD_Plot_Pad_",
    "DD_Dock_North",
    "DD_Dock_South",
    "DD_UI_LeaderboardStele_",
    "DD_UI_LeaderboardDais",
    "DD_Marker_Spawn",
]


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def build_island():
    obj = dd_mesh.wedge_solid(
        "DD_Terrain_Island",
        radius=config.ISLAND_RADIUS,
        angle_start_deg=config.GATE_HALF_ANGLE,
        angle_end_deg=360.0 - config.GATE_HALF_ANGLE,
        thickness=6.0,
        segments=64,
        base_z=config.GROUND_Z,
    )
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Terrain")
    return obj


def build_beach_ramp():
    near_x = config.ISLAND_RADIUS
    far_x = config.ISLAND_RADIUS + config.BEACH_RUN
    half_w = config.GATE_WIDTH / 2.0
    top_near_z = config.GROUND_Z
    top_far_z = config.BEACH_DROP
    bottom_z = config.BEACH_DROP - 4.0

    verts = [
        (near_x, -half_w, top_near_z),  # 0 top near left
        (near_x, half_w, top_near_z),   # 1 top near right
        (far_x, half_w, top_far_z),     # 2 top far right
        (far_x, -half_w, top_far_z),    # 3 top far left
        (near_x, -half_w, bottom_z),    # 4 bottom near left
        (near_x, half_w, bottom_z),     # 5 bottom near right
        (far_x, half_w, bottom_z),      # 6 bottom far right
        (far_x, -half_w, bottom_z),     # 7 bottom far left
    ]
    faces = [
        (0, 1, 2, 3),  # slanted top
        (4, 7, 6, 5),  # bottom
        (0, 4, 5, 1),  # near wall
        (3, 2, 6, 7),  # far wall
        (0, 3, 7, 4),  # left wall (-Y)
        (1, 5, 6, 2),  # right wall (+Y)
    ]
    obj = dd_mesh.new_mesh_object("DD_Terrain_Beach", verts, faces)
    dd_mesh.recalc_normals_outward(obj)
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Terrain")
    return obj


def build_shop():
    obj = dd_mesh.box("DD_Struct_Shop", config.SHOP_FOOTPRINT, config.SHOP_FOOTPRINT, config.SHOP_ROOF_Z, base_z=0.0)
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Structures")
    return obj


def build_spire():
    height = config.SPIRE_PEAK_Z - config.SHOP_ROOF_Z
    obj = dd_mesh.cylinder("DD_Struct_Spire", SPIRE_RADIUS, height, base_z=0.0, segments=12)
    obj.location = (0.0, 0.0, config.SHOP_ROOF_Z)
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Structures")
    return obj


def build_plaza_floor():
    obj = dd_mesh.annulus("DD_Plaza_Floor", config.PLAZA_INNER_R, config.PLAZA_OUTER_R, base_z=config.PLAZA_LIFT, segments=64)
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Plaza")
    return obj


def build_plots():
    objs = []
    thickness = 3.0
    for i in range(config.PLOT_COUNT):
        x, y = config.plot_xy(i)
        yaw = config.plot_yaw(i)
        name = f"DD_Plot_Pad_{i + 1:02d}"
        obj = dd_mesh.box(name, config.PLOT_SIZE, config.PLOT_SIZE, thickness, base_z=-thickness, yaw=yaw)
        obj.location = (x, y, config.PLOT_Z)
        dd_mesh.shade_flat(obj)
        dd_scene.link_to_collection(obj, "Plots")
        objs.append(obj)
    return objs


def build_docks():
    start_x = config.ISLAND_RADIUS + config.BEACH_RUN
    center_x = start_x + config.DOCK_LENGTH / 2.0
    objs = []
    for sign, side in ((1.0, "North"), (-1.0, "South")):
        name = f"DD_Dock_{side}"
        obj = dd_mesh.box(name, config.DOCK_LENGTH, DOCK_WIDTH, 1.0, base_z=-1.0)
        obj.location = (center_x, sign * config.DOCK_OFFSET_Y, 0.0)
        dd_mesh.shade_flat(obj)
        dd_scene.link_to_collection(obj, "Docks")
        objs.append(obj)
    return objs


def build_leaderboard():
    court_angle = config.LB_COURT_ANGLE
    cx = config.LB_COURT_R * math.cos(math.radians(court_angle))
    cy = config.LB_COURT_R * math.sin(math.radians(court_angle))
    face_yaw_deg = court_angle + 90.0  # local +Y faces plaza centre (matches plot_yaw's convention)
    face_yaw = math.radians(face_yaw_deg)
    local_x_dir = (math.cos(face_yaw), math.sin(face_yaw))  # tangent direction to space stelae along

    dais_w = 3 * (config.LB_STELE_W + 4.0) + 10.0
    dais = dd_mesh.box("DD_UI_LeaderboardDais", dais_w, 20.0, config.LB_DAIS_H, base_z=0.0, yaw=face_yaw)
    dais.location = (cx, cy, 0.0)
    dd_mesh.shade_flat(dais)
    dd_scene.link_to_collection(dais, "Plaza")

    spacing = config.LB_STELE_W + 4.0
    objs = [dais]
    for j, i in enumerate((-1, 0, 1)):
        offset = i * spacing
        px = cx + offset * local_x_dir[0]
        py = cy + offset * local_x_dir[1]
        stele_yaw = math.radians(face_yaw_deg + i * config.LB_STELE_FAN)
        name = f"DD_UI_LeaderboardStele_{j + 1:02d}"
        stele = dd_mesh.box(name, config.LB_STELE_W, 4.0, config.LB_STELE_H, base_z=0.0, yaw=stele_yaw)
        stele.location = (px, py, config.LB_DAIS_H)
        dd_mesh.shade_flat(stele)
        dd_scene.link_to_collection(stele, "Plaza")
        objs.append(stele)
    return objs


def build_spawn_marker():
    # Kept low (top well below the Z=5 eye-camera height used for the spawn
    # sightline render) so it marks the point without blocking the shot.
    obj = dd_mesh.cone("DD_Marker_Spawn", 2.0, 3.5, base_z=0.0, segments=8)
    obj.location = (config.SPAWN_XY[0], config.SPAWN_XY[1], 0.0)
    dd_mesh.shade_flat(obj)
    dd_scene.link_to_collection(obj, "Markers")
    return obj


def build():
    dd_scene.ensure_collections()
    purge()
    build_island()
    build_beach_ramp()
    build_shop()
    build_spire()
    build_plaza_floor()
    build_plots()
    build_docks()
    build_leaderboard()
    build_spawn_marker()


def capture_renders():
    """Top-down ortho + spawn eye-level renders, per CLAUDE.md's Phase 1
    gate deliverable. Reuses lib.scene camera/render helpers so every later
    phase captures the same way."""
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=900.0, height=600.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p1_top_ortho.png"), xray=True)

    eye_cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], 5.0),
        facing_deg=config.SPAWN_FACING_DEG,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(eye_cam, os.path.join(renders_dir, "p1_spawn_eye.png"), xray=False)


if __name__ == "__main__":
    build()
    capture_renders()
