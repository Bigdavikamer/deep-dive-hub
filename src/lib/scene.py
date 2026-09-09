"""Collection setup, purge-by-prefix, and naming/origin helpers.

Every build script (p1_greybox.py .. p8_materials.py) starts by calling
purge_by_prefix() for its own object prefix, then rebuilds from scratch.
This is what makes the scripts idempotent per the brief's operating rules.
"""
import re

import bpy

COLLECTIONS = [
    "Terrain", "Structures", "Plaza", "Plots", "Docks",
    "Props", "Overhead", "Nature", "Underwater", "Lore", "Markers",
]

# DD_<Category>_<Name>[_<Variant>][.{District}.{Index}]
NAME_RE = re.compile(
    r"^DD_(Terrain|Struct|Plot|Dock|Prop|Nature|Marker|UI|Lamp|Overhead|Lore|Sub)"
    r"_[A-Za-z0-9]+(_[A-Za-z0-9]+)*"
    r"(\.[A-Za-z0-9]+\.\d+)?$"
)

# Matches the ".District.Index" suffix that marks a placed/scattered instance,
# e.g. "DD_Prop_Barrel_A.MarketW.017". Unsuffixed names are source kit
# meshes (structural/terrain builds, and the Phase 7a prop-kit grid at
# (1000,0,0)) and must carry identity scale/rotation; suffixed names are
# scatter placements and are exempt -- see CLAUDE.md "HARD CONSTRAINTS".
PLACED_INSTANCE_RE = re.compile(r"\.[A-Za-z0-9]+\.\d+$")


def ensure_collections():
    """Create all top-level collections if missing and link them under the
    scene root. Safe to call repeatedly."""
    scene_coll = bpy.context.scene.collection
    result = {}
    for name in COLLECTIONS:
        coll = bpy.data.collections.get(name)
        if coll is None:
            coll = bpy.data.collections.new(name)
        if coll.name not in scene_coll.children:
            scene_coll.children.link(coll)
        result[name] = coll
    return result


def purge_by_prefix(prefix):
    """Delete every object whose name starts with `prefix`, then remove any
    mesh datablocks that were only used by those objects. Call this first in
    every build script so re-running produces identical output."""
    doomed = [o for o in bpy.data.objects if o.name.startswith(prefix)]
    doomed_meshes = set()
    for obj in doomed:
        if obj.type == "MESH" and obj.data is not None:
            doomed_meshes.add(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in doomed_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def link_to_collection(obj, collection_name):
    """Link `obj` to exactly one collection, unlinking it from any other
    (including the default scene collection it gets linked to on creation)."""
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    colls = ensure_collections()
    colls[collection_name].objects.link(obj)


def set_origin_to_base(obj):
    """Move the object's origin to its bounding-box base centre (min Z,
    centred X/Y) without bpy.ops, so it survives headless/MCP execution.
    Roblox expects origins at base centre, not volume centre.

    Deliberately does NOT read obj.matrix_world: in this MCP/headless
    context, matrix_world is a cached/evaluated value that does not refresh
    until a depsgraph update, so reading it immediately after setting
    obj.location returns the object's PREVIOUS transform -- a real bug
    found while building Phase 3 (every object silently snapped back to
    the world origin). Building the transform matrix directly from
    obj.location/rotation/scale sidesteps the staleness entirely.
    """
    import mathutils

    mesh = obj.data
    if mesh is None or len(mesh.vertices) == 0:
        return
    rotation = obj.rotation_quaternion if obj.rotation_mode == "QUATERNION" else obj.rotation_euler
    mat = mathutils.Matrix.LocRotScale(obj.location, rotation, obj.scale)

    coords = [mat @ v.co for v in mesh.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    base = mathutils.Vector(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, min(zs)))
    offset_world = base - obj.location
    local_offset = mat.to_3x3().inverted() @ offset_world
    for v in mesh.vertices:
        v.co -= local_offset
    obj.location = base
    mesh.update()


def is_valid_name(name):
    return bool(NAME_RE.match(name))


def is_placed_instance(name):
    """True for a scattered/placed instance (name ends '.District.Index'),
    false for a source kit mesh (structural build or unplaced prop-kit
    object)."""
    return bool(PLACED_INSTANCE_RE.search(name))


# ---- verification cameras / renders -----------------------------------------
# Every phase gate needs a top-down ortho + an eye-level render. These live
# here (not per-phase) so every p*_*.py script captures the same way.

def setup_ortho_top_camera(name, ortho_scale, height=600.0):
    """Camera looking straight down (-Z world) from directly above the
    origin. Identity rotation already looks down -Z in Blender, so no
    look-at math is needed."""
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_obj = bpy.data.objects.get(name)
    if cam_obj is None:
        cam_obj = bpy.data.objects.new(name, cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.data = cam_data
    cam_obj.location = (0.0, 0.0, height)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)
    return cam_obj


def setup_eye_camera(name, location, facing_deg, fov_deg=70.0):
    """Perspective camera at `location`, looking horizontally toward
    `facing_deg` (0 = +X, CCW, matching config.py's angle convention)."""
    import math

    import mathutils

    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.type = "PERSP"
    cam_data.angle = math.radians(fov_deg)
    cam_obj = bpy.data.objects.get(name)
    if cam_obj is None:
        cam_obj = bpy.data.objects.new(name, cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.data = cam_data
    cam_obj.location = location
    forward = mathutils.Vector((math.cos(math.radians(facing_deg)), math.sin(math.radians(facing_deg)), 0.0))
    cam_obj.rotation_euler = forward.to_track_quat("-Z", "Y").to_euler()
    return cam_obj


def render_to_file(camera_obj, filepath, resolution=(1600, 900), color_type="MATERIAL", xray=False):
    """Render `camera_obj`'s view to `filepath` using Workbench (fast, no
    lights required). color_type='MATERIAL' reads each object's assigned
    colour (see lib.palette.apply_debug_colors for greybox/gate renders --
    relying on Workbench's random per-object hash colouring proved
    unreliable). `xray=True` is for top-down layout checks only: solid
    terrain slabs otherwise occlude anything sitting below their top
    surface (e.g. plot pads at PLOT_Z, which is below GROUND_Z)."""
    scene = bpy.context.scene
    scene.camera = camera_obj
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.filepath = filepath
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = color_type
    shading.show_xray = xray
    if xray:
        shading.xray_alpha = 0.55
    bpy.ops.render.render(write_still=True)
    return filepath
