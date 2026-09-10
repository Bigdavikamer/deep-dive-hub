"""Phase 8 -- Materials, the biolume audit, and MANIFEST.md.

Assigns the real PALETTE materials for the first time. Every phase before this
one deliberately left geometry unpainted and let lib.palette.apply_debug_colors
put category-coded swatches on for verification renders; this replaces those
with linear-converted PALETTE colours.

MATERIAL SLOTS ARE THE CONTRACT. lib.mood put lantern glass in slot 1, rationed
cloth in slot 2 and specimen glass in slot 3 while the geometry was being
built, precisely so this pass would not have to identify them geometrically.
So slot 0 takes the object's base material, and the others are resolved from
what LIT_SITE_OBJECTS says about that specific object: the five lit lanterns
get lantern_gold with emission, the other eleven get dark iron glass from the
same mesh.

BIOLUME_CYAN IS RATIONED BY NAME, not by eye. It goes only to objects on
validate.py's interactable allowlist -- dive docks, plot marker plaques,
leaderboard stelae, shop and row counters. The moment a decorative prop glows
cyan the colour stops meaning "you can use this", so the audit here is a hard
check rather than a spot inspection.

specimen_glow is the deliberate second glow colour and lands only on DD_Lore_*
so it can never be mistaken for an interactable.
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
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import scene as dd_scene

GLOW_STRENGTH = 1.6
LORE_GLOW_STRENGTH = 0.9

# Longest prefix wins, so specific entries can sit above general ones.
BASE_MATERIAL = [
    ("DD_Terrain_BeachDry", "sand_dry"),
    ("DD_Terrain_BeachWet", "sand_wet"),
    ("DD_Terrain_BeachShallow", "water_shallow"),
    ("DD_Terrain_ShelfLip", "water_mid"),
    ("DD_Terrain_OceanFloor", "water_deep"),
    ("DD_Terrain_TidePool", "water_shallow"),
    ("DD_Terrain_Foreshore", "stone_light"),
    ("DD_Terrain_Island", "stone_light"),

    ("DD_Struct_PlazaFloor", "stone_light"),
    ("DD_Struct_PlazaStep", "stone_light"),
    ("DD_Struct_Path_", "stone_dark"),
    ("DD_Struct_WheelRut", "stone_dark"),
    ("DD_Struct_TideLine", "barnacle"),
    ("DD_Struct_MooringStone", "stone_dark"),
    ("DD_Struct_Breakwater", "stone_dark"),
    ("DD_Struct_CargoCrane", "timber_dark"),
    ("DD_Struct_CellarDoor", "iron_dark"),
    ("DD_Struct_CellarLedge", "stone_dark"),
    ("DD_Struct_Kiosk", "tar_pitch"),
    ("DD_Struct_MarketCross", "stone_light"),
    ("DD_Struct_LaneSign", "timber_warm"),
    ("DD_Struct_RowRoof", "roof_slate"),
    ("DD_Struct_RowPiers", "stone_light"),
    ("DD_Struct_Row", "timber_warm"),
    ("DD_Struct_Inn", "timber_warm"),
    ("DD_Struct_Warehouse", "timber_warm"),
    ("DD_Struct_BoatShed", "timber_dark"),
    ("DD_Struct_NetLoft", "timber_warm"),
    ("DD_Struct_SaltHouse", "salt_pale"),
    ("DD_Struct_Cooperage", "timber_warm"),
    ("DD_Struct_MerchantCart", "timber_warm"),
    ("DD_Struct_ShopRoof", "roof_slate"),
    ("DD_Struct_ShopUpper", "timber_warm"),
    ("DD_Struct_Shop", "stone_light"),
    ("DD_Struct_Spire", "roof_slate"),
    ("DD_Struct_Foreshore", "stone_light"),

    ("DD_Plot_Kerb", "stone_dark"),
    ("DD_Plot_Steps", "stone_light"),
    ("DD_Plot_Pad", "stone_light"),

    ("DD_Dock_", "timber_warm"),
    ("DD_Marker_Plot", "timber_warm"),
    ("DD_UI_Leaderboard", "stone_light"),
    ("DD_UI_Gamepass", "timber_dark"),
    ("DD_UI_Row", "tar_pitch"),
    ("DD_UI_NoticeBoard", "timber_warm"),
    ("DD_UI_TallyBoard", "tar_pitch"),
    ("DD_Lamp_", "iron_dark"),
    ("DD_Overhead_RopeLine", "rope_canvas"),
    ("DD_Overhead_HangingLantern", "iron_dark"),
    ("DD_Lore_", "stone_dark"),
]

# per prop asset key
PROP_MATERIAL = {
    "Barrel": "timber_warm", "Crate": "timber_warm", "RopeCoil": "rope_canvas",
    "Net": "rope_canvas", "Bollard": "stone_dark", "MarketStall": "timber_warm",
    "Well": "stone_light", "TimberStack": "timber_warm", "Sawhorse": "timber_dark",
    "HullRepair": "timber_dark", "Rowboat": "timber_warm", "Tool": "iron_dark",
    "GuttingTable": "timber_dark", "SaltVat": "salt_pale", "DryingRack": "timber_dark",
    "HangingFish": "sand_wet", "Awning": "cloth_blue", "Story": "timber_dark",
    "Rock": "stone_light", "CrabPot": "rope_canvas", "Buoy": "cloth_blue",
    "Anchor": "iron_dark", "Kelp": "sea_grass", "Coral": "roof_patina",
    "Ballast": "stone_dark", "SeaGrass": "sea_grass", "Heather": "moss_damp",
    "Pine": "sea_grass", "Gull": "salt_pale", "BannerPole": "timber_dark",
    "LanternPost": "iron_dark", "NoticeBoard": "timber_warm",
    "TallyBoard": "tar_pitch", "TrophyRack": "timber_dark", "JarShelf": "timber_dark",
    "Shrine": "stone_dark", "FossilArch": "barnacle", "RopeLine": "rope_canvas",
    "HangingLantern": "iron_dark",
}

# Objects allowed to carry biolume_cyan -- mirrors validate.py's allowlist.
INTERACTABLE_HINTS = ("DD_Dock_", "DD_UI_LeaderboardStele", "DD_Marker_Plot",
                      "DD_Struct_ShopCounter", "DD_Struct_RowCounter",
                      "DD_Struct_RowBay")
# and within those, only the surfaces a player actually uses
INTERACTABLE_EXACT = ("DiveMarker", "Plaque", "Stele", "Counter")


def base_key(name):
    return name.split(".")[0]


def asset_key(name):
    bits = base_key(name).split("_")
    return bits[2] if len(bits) >= 3 else None


def wants_cyan(name):
    bn = base_key(name)
    if not bn.startswith(INTERACTABLE_HINTS):
        return False
    return any(tok in bn for tok in INTERACTABLE_EXACT)


def base_material_key(obj):
    """Per-asset first, then longest matching prefix.

    The other order looked fine and was wrong: the broad "DD_Lore_" ->
    stone_dark entry outranked every specific lore asset, so the fossil arch
    came out as plain dark stone instead of barnacle. An asset key is the more
    specific statement whenever there is one.
    """
    bn = base_key(obj.name)
    if wants_cyan(obj.name):
        return config.INTERACTABLE_COLOR
    ak = asset_key(obj.name)
    if ak and ak in PROP_MATERIAL:
        return PROP_MATERIAL[ak]
    best = None
    for prefix, key in BASE_MATERIAL:
        if bn.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, key)
    return best[1] if best else "stone_light"


def resolve_slots(obj):
    """The material for each slot, keyed off which slots the faces actually use.

    lib.mood._ensure_slots pads up to whatever index it needs, so a lore prop
    marked into the glow slot (3) also carries empty slots 1 and 2. Painting
    those by index alone handed jar shelves a cloth_red slot no face
    references -- inert, but it ships in the FBX and reads as a mistake.
    Unused slots get the base material instead.
    """
    n_slots = max(len(obj.data.materials), 1)
    used = {p.material_index for p in obj.data.polygons}
    out = []
    for i in range(n_slots):
        if i not in used:
            key = base_material_key(obj)
            emit = GLOW_STRENGTH * 0.5 if key == config.INTERACTABLE_COLOR else 0.0
            out.append((key, emit))
        elif i == dd_mood.GLASS_SLOT:
            if dd_mood.is_lit(base_key(obj.name)):
                out.append(("lantern_gold", GLOW_STRENGTH))
            else:
                out.append(("tar_pitch", 0.0))     # dark, unlit glass
        elif i == dd_mood.WARM_SLOT:
            out.append(("cloth_red", 0.0))
        elif i == dd_mood.GLOW_SLOT:
            out.append((config.LORE_GLOW_COLOR, LORE_GLOW_STRENGTH))
        else:
            key = base_material_key(obj)
            emit = GLOW_STRENGTH * 0.5 if key == config.INTERACTABLE_COLOR else 0.0
            out.append((key, emit))
    return out


def apply_materials():
    """Paint every DD_ mesh. Objects sharing mesh data are painted once --
    materials live on the mesh, so writing them per instance would just
    overwrite the same datablock 300 times."""
    painted_meshes = set()
    count = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.name.startswith("DD_"):
            continue
        if obj.data.name in painted_meshes:
            continue
        slots = resolve_slots(obj)
        mesh = obj.data
        # Assign into existing slots; never clear. Clearing the material list
        # resets every polygon's material_index to 0, which silently destroys
        # the glass/warm/glow slot assignments lib.mood baked in during the
        # build -- all sixteen lanterns came out with no glass at all the first
        # time this ran. Same trap apply_debug_colors had.
        while len(mesh.materials) < len(slots):
            mesh.materials.append(None)
        for i, (key, emit) in enumerate(slots):
            mesh.materials[i] = dd_palette.material_for(
                config.PALETTE, key, emission_strength=emit)
        painted_meshes.add(mesh.name)
        count += 1
    return count


def audit_glow():
    """Hard check, not a spot inspection: biolume_cyan only on the interactable
    allowlist, specimen_glow only on DD_Lore_*."""
    cyan_name = f"DD_Mat_{config.INTERACTABLE_COLOR}"
    glow_name = f"DD_Mat_{config.LORE_GLOW_COLOR}"
    cyan_bad, glow_bad, cyan_ok = [], [], []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.name.startswith("DD_"):
            continue
        names = {s.name for s in obj.data.materials if s}
        if cyan_name in names:
            (cyan_ok if wants_cyan(obj.name) else cyan_bad).append(obj.name)
        if glow_name in names and not base_key(obj.name).startswith("DD_Lore_"):
            glow_bad.append(obj.name)
    print(f"[11] biolume_cyan on {len(set(base_key(n) for n in cyan_ok))} distinct "
          f"interactable meshes; violations: {len(cyan_bad)} "
          f"{'OK' if not cyan_bad else cyan_bad[:6]}")
    print(f"[21] specimen_glow violations: {len(glow_bad)} "
          f"{'OK' if not glow_bad else glow_bad[:6]}")
    return not cyan_bad and not glow_bad


# ---- collision fidelity ----------------------------------------------------

# Anything a player walks through or into needs real collision; simple solids
# can be Box, which is by far the cheapest for Roblox to simulate.
PRECISE_HINTS = ("DD_Struct_ShopArch", "DD_Struct_ShopPier", "DD_Lore_FossilArch",
                 "DD_Struct_Breakwater", "DD_Struct_Row", "DD_Struct_Kiosk",
                 "DD_Struct_CellarDoor", "DD_Struct_Well", "DD_Prop_Well")
HULL_HINTS = ("DD_Terrain_", "DD_Struct_Inn", "DD_Struct_Warehouse",
              "DD_Struct_BoatShed", "DD_Struct_NetLoft", "DD_Struct_SaltHouse",
              "DD_Struct_Cooperage", "DD_Struct_CargoCrane", "DD_Prop_HullRepair")


def collision_fidelity(name):
    bn = base_key(name)
    if bn.startswith(PRECISE_HINTS):
        return "PreciseConvexDecomposition"
    if bn.startswith(HULL_HINTS):
        return "Hull"
    return "Box"


# ---- manifest --------------------------------------------------------------

def write_manifest():
    """Every object with stud position, rotation, collection, tri count and its
    collision-fidelity flag -- the handoff document for Studio."""
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if not obj.name.startswith("DD_"):
            continue
        colls = [c.name for c in obj.users_collection]
        coll = colls[0] if colls else "-"
        if obj.type == "MESH":
            tris = dd_mesh.triangle_count(obj)
            mesh_id = obj.data.name
        else:
            tris, mesh_id = 0, "-"
        rot = tuple(round(math.degrees(a), 1) for a in obj.rotation_euler)
        rows.append((obj.name, obj.location, rot, coll, tris, mesh_id,
                     collision_fidelity(obj.name) if obj.type == "MESH" else "-"))

    total_tris = sum(r[4] for r in rows)
    meshes = {r[5] for r in rows if r[5] != "-"}
    instances = [r for r in rows if dd_scene.is_placed_instance(r[0])]

    path = os.path.join(REPO_ROOT, "MANIFEST.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# DEEP DIVE — Hub Map Manifest\n\n")
        fh.write("Generated by `src/p8_materials.py`. Positions are in Roblox studs "
                 "(1 Blender unit = 1 stud), Blender axes: +X east, +Y north, Z up.\n"
                 "Roblox conversion is `x, z, -y` — see `out/npc_anchors.json`, "
                 "which is already converted.\n\n")
        fh.write(f"- Objects: **{len(rows)}**\n")
        fh.write(f"- Unique mesh datablocks: **{len(meshes)}**\n")
        fh.write(f"- Placed instances (linked): **{len(instances)}**\n")
        fh.write(f"- Total triangles: **{total_tris:,}** (target < 400,000)\n\n")
        fh.write(f"Triangle counts are for the AUTHORED source. `export_fbx.py` adds the "
                 f"{config.BEVEL_WIDTH}-stud structural bevel "
                 f"({config.BEVEL_SEGMENTS} segment, clamped) when it writes the FBX, "
                 f"which multiplies them by roughly 1.7x on large terrain and up to "
                 f"3.7x on small props. The bevel is deliberately not in the build "
                 f"scripts, so the sources stay editable and re-runnable.\n\n")
        fh.write("Instancing is preserved through export: objects sharing a mesh "
                 "datablock share one geometry in the FBX and become one reused "
                 "`MeshId` in Studio.\n\n")
        fh.write("`CollisionFidelity`: `Box` for simple solids, `Hull` for terrain "
                 "and building masses, `PreciseConvexDecomposition` for anything a "
                 "player walks through — arches, the colonnade, the fossil arch.\n\n")
        fh.write("| Object | X | Y | Z | Rot Z° | Collection | Tris | Mesh | CollisionFidelity |\n")
        fh.write("|---|---:|---:|---:|---:|---|---:|---|---|\n")
        for name, loc, rot, coll, tris, mesh_id, fid in rows:
            fh.write(f"| `{name}` | {loc.x:.1f} | {loc.y:.1f} | {loc.z:.1f} | "
                     f"{rot[2]:.1f} | {coll} | {tris} | `{mesh_id}` | {fid} |\n")
    print(f"MANIFEST.md: {len(rows)} objects, {len(meshes)} meshes, {total_tris:,} tris")
    return path


def capture_renders():
    """The first renders of the real thing. Every earlier phase shot with
    apply_debug_colors' category swatches; these use the PALETTE materials, so
    this is the first look at the cool palette and the scarce-light rule
    together."""
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], config.PLAZA_LIFT + 5.0),
        facing_deg=config.SPAWN_FACING_DEG, fov_deg=70.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p8_spawn_sightline.png"))

    cam = dd_scene.setup_look_at_camera(
        "RenderCam_Sea600", location=(600.0, 0.0, 5.0), target=(0.0, 0.0, 60.0),
        fov_deg=45.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p8_sea600.png"))

    cam = dd_scene.setup_look_at_camera(
        "RenderCam_DockBack", location=(400.0, -58.0, 10.0), target=(60.0, 0.0, 30.0),
        fov_deg=62.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p8_dock_lookback.png"))

    a = math.radians(172.0)
    cam = dd_scene.setup_eye_camera(
        "RenderCam_Q_market_w",
        location=(44.0 * math.cos(a), 44.0 * math.sin(a), config.PLAZA_LIFT + 5.5),
        facing_deg=172.0, fov_deg=75.0)
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p8_market_w.png"))

    top = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=560.0, height=700.0)
    dd_scene.render_to_file(top, os.path.join(renders_dir, "p8_top_ortho.png"))


def build():
    painted = apply_materials()
    ok = audit_glow()
    write_manifest()
    print(f"painted {painted} mesh datablocks; glow audit {'OK' if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    build()
