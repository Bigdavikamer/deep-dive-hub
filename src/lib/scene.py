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
    Roblox expects origins at base centre, not volume centre."""
    import mathutils

    mesh = obj.data
    if mesh is None or len(mesh.vertices) == 0:
        return
    coords = [obj.matrix_world @ v.co for v in mesh.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    base = mathutils.Vector(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, min(zs)))
    offset_world = base - obj.matrix_world.translation
    local_offset = obj.matrix_world.inverted().to_3x3() @ offset_world
    for v in mesh.vertices:
        v.co -= local_offset
    obj.matrix_world.translation = base
    mesh.update()


def is_valid_name(name):
    return bool(NAME_RE.match(name))
