"""Post-Phase-8 polish pass -- verification renders only.

Not a phase in the CLAUDE.md sense: it owns no DD_ prefix and purges nothing.
It exists to prove that the polish pass (config.CAVITY_DARKEN_STRENGTH,
config.TERRAIN_BLEND_BANDS, the rowboat/hull-repair weathering marks) actually
did something, once p2_terrain, p7a_kit and p8_materials have rebuilt the
scene with the current source (run build_all.py, or at least those three).

Two of the three polish items are vertex-colour bakes (lib.mood.COLOR_ATTR /
TERRAIN_TINT_ATTR) that are deliberately NOT wired into a Blender shader node
graph -- see lib.mood's module docstring for why -- so they are invisible in
the standard MATERIAL-mode renders every other phase uses (Workbench's
MATERIAL preview reads a material's flat diffuse_color, not a node graph).
The *_vertex.png renders below switch Workbench to VERTEX colour-type and
point each mesh's active colour attribute at the layer being inspected, which
is the only way to see this data inside Blender. The real target for both
bakes is Roblox Studio reading the FBX's vertex colours on import, not this
render -- these are a sanity check, not the deliverable.

The third item (hull/rowboat weathering) uses real per-slot PALETTE
materials, so it shows up in ordinary MATERIAL-mode renders like everything
else in the kit.
"""
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bpy

import config
from lib import mood as dd_mood
from lib import scene as dd_scene

RENDERS_DIR = os.path.join(REPO_ROOT, "renders")


def _set_active_color(mesh, name):
    idx = mesh.color_attributes.find(name)
    if idx < 0:
        return False
    mesh.color_attributes.active_color_index = idx
    if hasattr(mesh.color_attributes, "render_color_index"):
        mesh.color_attributes.render_color_index = idx
    return True


def _vertex_render(attr_name, filepath, only_prefix=None):
    """Point every matching DD_ mesh's active/render colour attribute at
    `attr_name` (skipping any mesh that doesn't carry it) and render a
    Workbench VERTEX-mode top ortho."""
    touched = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.name.startswith("DD_"):
            continue
        if only_prefix and not obj.name.startswith(only_prefix):
            continue
        if _set_active_color(obj.data, attr_name):
            touched += 1
    cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=560.0, height=700.0)
    dd_scene.render_to_file(cam, filepath, color_type="VERTEX")
    return touched


def _lookat_close_up(name, obj_name, offset, fov_deg=40.0):
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        return None
    loc = obj.matrix_world.translation
    target = (loc.x, loc.y, loc.z + 2.0)
    cam_loc = (loc.x + offset[0], loc.y + offset[1], loc.z + offset[2])
    return dd_scene.setup_look_at_camera(name, location=cam_loc, target=target, fov_deg=fov_deg)


def capture_renders():
    os.makedirs(RENDERS_DIR, exist_ok=True)

    n = _vertex_render(dd_mood.COLOR_ATTR, os.path.join(RENDERS_DIR, "p9_cavity_vertex.png"))
    print(f"cavity/AO vertex render: {n} meshes carried {dd_mood.COLOR_ATTR}")

    n = _vertex_render(
        dd_mood.TERRAIN_TINT_ATTR,
        os.path.join(RENDERS_DIR, "p9_terrain_blend_vertex.png"),
        only_prefix="DD_Terrain_Island",
    )
    print(f"terrain blend vertex render: {n} meshes carried {dd_mood.TERRAIN_TINT_ATTR}")

    cam = _lookat_close_up("RenderCam_Rowboat", "DD_Prop_Rowboat_A", (0.0, -13.0, 5.0), fov_deg=38.0)
    if cam:
        dd_scene.render_to_file(cam, os.path.join(RENDERS_DIR, "p9_rowboat_weathering.png"))

    cam = _lookat_close_up("RenderCam_HullRepair", "DD_Prop_HullRepair_A", (0.0, -18.0, 6.0), fov_deg=42.0)
    if cam:
        dd_scene.render_to_file(cam, os.path.join(RENDERS_DIR, "p9_hull_repair_weathering.png"))

    # Final MATERIAL-mode comparison pair, same framing p8_materials.py used,
    # so they diff cleanly against renders/p8_spawn_sightline.png and
    # renders/p8_top_ortho.png.
    cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], config.PLAZA_LIFT + 5.0),
        facing_deg=config.SPAWN_FACING_DEG, fov_deg=70.0)
    dd_scene.render_to_file(cam, os.path.join(RENDERS_DIR, "p9_spawn_sightline.png"))

    top = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=560.0, height=700.0)
    dd_scene.render_to_file(top, os.path.join(RENDERS_DIR, "p9_top_ortho.png"))


if __name__ == "__main__":
    capture_renders()
