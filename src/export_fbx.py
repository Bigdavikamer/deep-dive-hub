"""FBX export per collection, plus the NPC anchor JSON handoff.

Modifiers (the structural bevel) are applied here, on throwaway duplicates,
NOT in the build scripts -- so the authored source meshes stay editable and
re-runnable. This is the fix for the "bevel modifier not applied before
export" failure mode in CLAUDE.md.

FBX settings below are copied verbatim from CLAUDE.md's "HARD CONSTRAINTS"
table (sourced from Roblox's own docs). Do not change them without checking
that section first.
"""
import json
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bpy

import config
from lib import mesh as dd_mesh
from lib import scene as dd_scene

OUT_DIR = os.path.join(REPO_ROOT, "out")

FBX_EXPORT_KWARGS = dict(
    use_selection=True,
    path_mode="COPY",
    embed_textures=True,
    apply_scale_options="FBX_SCALE_UNITS",
    global_scale=0.01,
    add_leaf_bones=False,
    bake_anim=False,
    axis_forward="-Z",
    axis_up="Y",
    object_types={"MESH"},
)


def bake_shared_meshes(mesh_datablocks):
    """Bevel each UNIQUE mesh datablock once and return {orig name: baked}.

    Baking per object would be the obvious thing and would be wrong. Phase 7b
    places ~490 instances that share ~90 kit datablocks by design, so that one
    barrel mesh becomes one reused MeshId in Studio; copying the mesh per
    object turns 294 datablocks into 816 and undoes the entire linked-data
    strategy -- hundreds of separate uploads and a Studio import that crawls.
    So the bevel is applied to the shared mesh, once, and every instance keeps
    pointing at the same result.

    The bevel is added here rather than in the build scripts on purpose: the
    authored sources stay editable and re-runnable, which is the documented fix
    for the "bevel modifier not applied before export" failure mode. Nothing in
    the build carries object-level modifiers, so baking off a holder object
    loses nothing.
    """
    baked = {}
    holder_coll = bpy.data.collections.new("DD_BakeTmp")
    bpy.context.scene.collection.children.link(holder_coll)
    try:
        for mesh in mesh_datablocks:
            holder = bpy.data.objects.new(f"_ddbake_{mesh.name}", mesh)
            holder_coll.objects.link(holder)
            dd_mesh.bevel_edges(holder, config.BEVEL_WIDTH, config.BEVEL_SEGMENTS)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            baked[mesh.name] = bpy.data.meshes.new_from_object(holder.evaluated_get(dg))
            bpy.data.objects.remove(holder, do_unlink=True)
    finally:
        bpy.data.collections.remove(holder_coll)
    return baked


def _duplicate_for_export(obj, tmp_collection, baked):
    """A node referencing the shared baked mesh, keeping the object's own
    transform. Rotation and scale stay on the node rather than being baked into
    vertices: placed instances legitimately carry both (that is how one mesh
    becomes thirty differently-oriented barrels), and baking them would force a
    unique mesh per instance -- the very thing bake_shared_meshes avoids.
    Source meshes already hold identity rotation and scale, so nothing is lost
    for them either."""
    dup = obj.copy()
    dup.modifiers.clear()
    dup.data = baked[obj.data.name]
    tmp_collection.objects.link(dup)
    return dup


def export_collection(collection_name, out_path):
    """Export every mesh object in `collection_name` (recursively, including
    nested sub-collections) to a single FBX file."""
    coll = bpy.data.collections.get(collection_name)
    if coll is None:
        print(f"export_fbx: collection '{collection_name}' not found, skipping")
        return False

    mesh_objs = [o for o in coll.all_objects if o.type == "MESH"]
    if not mesh_objs:
        print(f"export_fbx: collection '{collection_name}' has no mesh objects, skipping")
        return False

    tmp_coll = bpy.data.collections.new(f"DD_ExportTmp_{collection_name}")
    bpy.context.scene.collection.children.link(tmp_coll)

    for o in bpy.data.objects:
        o.select_set(False)

    unique = {o.data.name: o.data for o in mesh_objs}
    baked = bake_shared_meshes(list(unique.values()))

    duplicates = []
    try:
        for obj in mesh_objs:
            dup = _duplicate_for_export(obj, tmp_coll, baked)
            dup.select_set(True)
            duplicates.append(dup)
        bpy.context.view_layer.objects.active = duplicates[0]

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with bpy.context.temp_override(
            active_object=duplicates[0],
            selected_objects=duplicates,
            selected_editable_objects=duplicates,
        ):
            bpy.ops.export_scene.fbx(filepath=out_path, **FBX_EXPORT_KWARGS)
        print(f"export_fbx: wrote {out_path} "
              f"({len(duplicates)} objects, {len(unique)} shared meshes)")
    finally:
        for dup in duplicates:
            bpy.data.objects.remove(dup, do_unlink=True)
        for mesh in baked.values():
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.data.collections.remove(tmp_coll)

    return True


def export_all():
    results = {}
    for name in dd_scene.COLLECTIONS:
        out_path = os.path.join(OUT_DIR, f"DD_{name}.fbx")
        results[name] = export_collection(name, out_path)
    return results


def export_npc_anchors_json():
    """Roblox coordinate conversion (Blender Z-up -> Roblox Y-up):
        roblox_x =  blender_x
        roblox_y =  blender_z
        roblox_z = -blender_y
    Empties don't survive FBX cleanly, so this JSON is the real deliverable
    for NPC placement -- Studio spawns characters by name from it.
    """
    entries = []
    missing = []
    for npc_name, site in config.NPC_ANCHORS:
        obj_name = f"DD_Marker_NPC_{npc_name}"
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            missing.append(obj_name)
            continue
        bx, by, bz = obj.matrix_world.translation
        yaw_deg = obj.rotation_euler.z * 180.0 / 3.141592653589793
        entries.append({
            "name": npc_name,
            "site": site,
            "x": bx,
            "y": bz,
            "z": -by,
            "facing_deg": yaw_deg,
        })

    if missing:
        print(f"export_npc_anchors_json: {len(missing)} anchors missing (not built yet): {missing}")

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "npc_anchors.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    print(f"export_npc_anchors_json: wrote {len(entries)} entries to {out_path}")
    return out_path


if __name__ == "__main__":
    export_all()
    export_npc_anchors_json()
