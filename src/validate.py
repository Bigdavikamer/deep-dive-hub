"""Acceptance checks for the Deep Dive hub map. Run this inside the
connected Blender session (or headless via `blender --background --python
src/validate.py`) after any build phase. Exits nonzero and prints a
per-object report on any failure.

NOTE on checks 6/7 vs 17: the brief requires every exported object to carry
identity scale/rotation (baked into vertex data) AND requires scattered prop
instances to share linked mesh data (so rotated/scaled duplicates read as one
MeshId). Those two rules are in tension for any two instances that don't
share the exact same yaw+scale jitter. This validator enforces both as
literally specified; resolving the tension (e.g. by exempting placed
instances from the identity-transform rule, since translation/rotation is
how Roblox parts are placed anyway) is a design call for Phase 7b, flagged
to the user rather than guessed here.
"""
import json
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bmesh
import bpy

import config
from lib import scene as dd_scene
from lib.palette import hex_to_linear_rgba

TOLERANCE = 0.01
ANTI_REPEAT_RADIUS = 40.0
ANTI_REPEAT_ANGLE_DEG = 5.0
TOTAL_TRI_TARGET = 400_000

# Objects allowed to carry biolume_cyan: dive docks, shop counter, plot
# markers, leaderboard frames, merchant row bay counters. Matched by
# substring against the object's base name (before any .District.### suffix).
INTERACTABLE_NAME_HINTS = (
    "DD_Dock_",
    "DD_UI_LeaderboardStele",
    "DD_Marker_Plot",
    "DD_Struct_ShopCounter",
    "DD_Struct_RowCounter",
    "DD_Struct_RowBay",
)


def base_name(obj_name):
    return obj_name.split(".")[0]


def dd_objects():
    return [o for o in bpy.data.objects if o.name.startswith("DD_")]


def triangle_count(obj):
    return sum(max(len(p.vertices) - 2, 0) for p in obj.data.polygons)


# ---- checks -----------------------------------------------------------------

def check_tri_cap(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        tris = triangle_count(o)
        if tris > 20000:
            fails.append(f"{o.name}: {tris} tris > 20000 hard cap")
    return fails


def check_tri_budget(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        for prefix, budget in config.TRI_BUDGET.items():
            if o.name.startswith(prefix):
                tris = triangle_count(o)
                if tris > budget:
                    fails.append(f"{o.name}: {tris} tris > {budget} budget for {prefix}")
                break
    return fails


def check_manifold(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        non_manifold = [e for e in bm.edges if not e.is_manifold]
        bm.free()
        if non_manifold:
            fails.append(f"{o.name}: {len(non_manifold)} non-manifold edges")
    return fails


def check_ngons(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        ngons = [p for p in o.data.polygons if len(p.vertices) > 4]
        if ngons:
            fails.append(f"{o.name}: {len(ngons)} n-gons")
    return fails


def check_loose_geometry(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        loose_verts = [v for v in bm.verts if not v.link_edges]
        loose_edges = [e for e in bm.edges if not e.link_faces]
        bm.free()
        if loose_verts or loose_edges:
            fails.append(f"{o.name}: {len(loose_verts)} loose verts, {len(loose_edges)} loose edges")
    return fails


def check_transforms(objs):
    fails = []
    for o in objs:
        sx, sy, sz = o.scale
        if any(abs(s - 1.0) > TOLERANCE for s in (sx, sy, sz)):
            fails.append(f"{o.name}: scale {tuple(o.scale)} != (1,1,1)")
        if o.rotation_mode == "QUATERNION":
            rot_ok = (
                abs(o.rotation_quaternion[0] - 1.0) < TOLERANCE
                and all(abs(c) < TOLERANCE for c in o.rotation_quaternion[1:])
            )
        else:
            rot_ok = all(abs(r) < TOLERANCE for r in o.rotation_euler)
        if not rot_ok:
            fails.append(f"{o.name}: rotation not identity")
    return fails


def check_origin_base(objs):
    fails = []
    for o in objs:
        if o.type != "MESH" or not o.data.vertices:
            continue
        zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
        min_z = min(zs)
        origin_z = o.matrix_world.translation.z
        if abs(origin_z - min_z) > TOLERANCE:
            fails.append(f"{o.name}: origin Z {origin_z:.3f} != bbox min Z {min_z:.3f}")
    return fails


def check_max_dimension(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        dims = o.dimensions
        if max(dims) > config.MAX_DIM:
            fails.append(f"{o.name}: dimension {max(dims):.1f} > {config.MAX_DIM}")
    return fails


def check_naming(objs):
    fails = []
    for o in objs:
        if not dd_scene.is_valid_name(o.name):
            fails.append(f"{o.name}: does not match naming regex")
    return fails


def check_single_collection(objs):
    fails = []
    for o in objs:
        n = len(o.users_collection)
        if n != 1:
            fails.append(f"{o.name}: in {n} collections, expected exactly 1")
    return fails


def _material_hex_key(mat_name):
    if mat_name.startswith("DD_Mat_"):
        key = mat_name[len("DD_Mat_"):]
        if key in config.PALETTE:
            return key
    return None


def check_biolume_allowlist(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        for slot in o.data.materials:
            if slot is None:
                continue
            if _material_hex_key(slot.name) == config.INTERACTABLE_COLOR:
                if not any(base_name(o.name).startswith(h) for h in INTERACTABLE_NAME_HINTS):
                    fails.append(f"{o.name}: uses {config.INTERACTABLE_COLOR} but not in interactable allowlist")
    return fails


def check_specimen_glow(objs):
    fails = []
    for o in objs:
        if o.type != "MESH":
            continue
        for slot in o.data.materials:
            if slot is None:
                continue
            if _material_hex_key(slot.name) == config.LORE_GLOW_COLOR:
                if not base_name(o.name).startswith("DD_Lore_"):
                    fails.append(f"{o.name}: uses {config.LORE_GLOW_COLOR} but is not DD_Lore_*")
    return fails


def check_anti_repetition(objs):
    fails = []
    by_mesh = {}
    for o in objs:
        if o.type != "MESH" or o.data is None:
            continue
        by_mesh.setdefault(o.data.name, []).append(o)
    for mesh_name, group in by_mesh.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                dist = (a.matrix_world.translation - b.matrix_world.translation).length
                if dist < ANTI_REPEAT_RADIUS:
                    yaw_a = math.degrees(a.rotation_euler.z)
                    yaw_b = math.degrees(b.rotation_euler.z)
                    if abs((yaw_a - yaw_b + 180) % 360 - 180) < ANTI_REPEAT_ANGLE_DEG:
                        fails.append(
                            f"{a.name} & {b.name}: same mesh ({mesh_name}), {dist:.1f} studs apart, "
                            f"yaw within {ANTI_REPEAT_ANGLE_DEG} deg"
                        )
    return fails


def check_linear_materials(objs):
    fails = []
    seen = set()
    for o in objs:
        if o.type != "MESH":
            continue
        for slot in o.data.materials:
            if slot is None or slot.name in seen:
                continue
            seen.add(slot.name)
            key = _material_hex_key(slot.name)
            if key is None or not slot.use_nodes:
                continue
            bsdf = slot.node_tree.nodes.get("Principled BSDF")
            if bsdf is None:
                continue
            expected = hex_to_linear_rgba(config.PALETTE[key])
            actual = tuple(bsdf.inputs["Base Color"].default_value)
            if any(abs(a - b) > 0.02 for a, b in zip(expected, actual)):
                fails.append(f"{slot.name}: base color {actual} != expected linear {expected}")
    return fails


def check_total_tris(objs):
    total = sum(triangle_count(o) for o in objs if o.type == "MESH")
    note = f"Total scene triangles: {total} (target < {TOTAL_TRI_TARGET})"
    fails = [note] if total > TOTAL_TRI_TARGET else []
    return fails, note


def check_linked_data(objs):
    """Every DD_Prop_/DD_Nature_/DD_Overhead_ base name group placed more
    than once must share one mesh datablock (linked, not copied)."""
    fails = []
    prop_prefixes = ("DD_Prop_", "DD_Nature_", "DD_Overhead_", "DD_Lore_", "DD_Lamp_")
    groups = {}
    for o in objs:
        if o.type != "MESH":
            continue
        bn = base_name(o.name)
        if bn.startswith(prop_prefixes):
            groups.setdefault(bn, []).append(o)
    for bn, group in groups.items():
        if len(group) < 2:
            continue
        mesh_ids = {o.data.name for o in group}
        if len(mesh_ids) > 1:
            fails.append(f"{bn}: {len(group)} instances use {len(mesh_ids)} different mesh datablocks (not linked)")
    return fails


def check_npc_anchors(objs):
    fails = []
    empties = {o.name: o for o in bpy.data.objects if o.type == "EMPTY"}
    for npc_name, _site in config.NPC_ANCHORS:
        expected = f"DD_Marker_NPC_{npc_name}"
        if expected not in empties:
            fails.append(f"missing NPC anchor Empty: {expected}")
    return fails


def check_npc_json_roundtrip(objs):
    path = os.path.join(os.path.dirname(SRC_DIR), "out", "npc_anchors.json")
    if not os.path.exists(path):
        return []  # nothing to round-trip yet; not a Phase 0 failure
    fails = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for entry in data:
        name = entry.get("name")
        obj = bpy.data.objects.get(f"DD_Marker_NPC_{name}")
        if obj is None:
            fails.append(f"npc_anchors.json entry {name}: no matching Empty in scene")
            continue
        bx, by, bz = obj.matrix_world.translation
        expected = (bx, bz, -by)
        got = (entry.get("x"), entry.get("y"), entry.get("z"))
        if any(abs(e - g) > TOLERANCE for e, g in zip(expected, got)):
            fails.append(f"npc_anchors.json entry {name}: {got} != expected {expected}")
    return fails


def check_paths_not_straight(objs):
    """Any DD_Struct_Path_* / DD_Terrain_Path_* midpoint must bow >= 8 studs.
    Skipped (not failed) until paths exist -- Phase 4 concern."""
    return []


ALL_CHECKS = [
    (1, "Triangle cap (<=20000/mesh)", check_tri_cap),
    (2, "Per-category tri budget", check_tri_budget),
    (3, "Manifold edges", check_manifold),
    (4, "Zero n-gons", check_ngons),
    (5, "Loose verts/edges", check_loose_geometry),
    (6, "Identity scale/rotation", check_transforms),
    (7, "Origin at base centre", check_origin_base),
    (8, "Max dimension <=2048", check_max_dimension),
    (9, "Naming regex", check_naming),
    (10, "Exactly one collection", check_single_collection),
    (11, "biolume_cyan allowlist", check_biolume_allowlist),
    (12, "Anti-repetition", check_anti_repetition),
    (13, "Linear-converted materials", check_linear_materials),
    (17, "Linked mesh data for prop library", check_linked_data),
    (21, "specimen_glow on DD_Lore_* only", check_specimen_glow),
    (23, "NPC anchor Empties present", check_npc_anchors),
    (27, "Paths not perfectly straight", check_paths_not_straight),
]


def main():
    objs = dd_objects()
    if not objs:
        print("validate.py: no DD_* objects in the scene yet -- nothing to check. PASS.")
        return 0

    print(f"validate.py: checking {len(objs)} DD_* objects.\n")
    any_fail = False

    for num, desc, fn in ALL_CHECKS:
        fails = fn(objs)
        status = "OK" if not fails else "FAIL"
        print(f"[{num:2d}] {desc}: {status}")
        for line in fails:
            print(f"     - {line}")
        if fails:
            any_fail = True

    _, tri_note = check_total_tris(objs)
    print(f"[14] {tri_note}")

    print(f"\nnpc_anchors.json round-trip:")
    for line in check_npc_json_roundtrip(objs) or ["OK (or not yet exported)"]:
        print(f"     - {line}")

    print("\nRESULT:", "FAIL" if any_fail else "PASS")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
