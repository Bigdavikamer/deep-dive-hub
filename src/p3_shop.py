"""Phase 3 -- Shop + spire. The landmark; everything else is scaled
against it.

Ground floor is a genuine open arcade -- 4 corner stone piers with a true
arched stone lintel (half-ellipse, built as a solid loft via lib.mesh.
arch_beam) spanning each side, and NOTHING filling the gap below/around the
arch. That satisfies "open on all four sides, enterable from any approach"
without a single boolean cut -- CLAUDE.md explicitly flags the shop arches
as a top boolean-cut risk (n-gons, non-manifold edges), so this phase
avoids the operation entirely rather than adding a cleanup pass to catch
its failures.

Second storey is a solid box (no interior fitout -- shop interior layout
is explicitly an "ASK ME ABOUT" item in CLAUDE.md, so it stays an empty
shell here). Hip roof (a short ridge, not a single pyramid apex, matching
"roof ridge" in the brief). Spire: a short drum + tapering octagonal cone
to the exact SPIRE_PEAK_Z.

Proportions inferred (not in config.py, flagged rather than guessed):
  PIER_SIZE          = 6.0   studs (corner pier footprint)
  ARCH_SPRINGLINE_Z   = 14.0  studs (where the arch curve begins)
  ARCH_RISE           = 10.0  studs (springline -> apex, so apex = pier top = 24)
  ARCH_THICKNESS       = 4.0   studs (radial thickness of the arch band)
  UPPER_FLOOR_H        = 14.0  studs (24 -> 38, second storey wall height)
  ROOF_RIDGE_LEN        = 20.0  studs (hip roof ridge length)
  SPIRE_DRUM_R / _H      = 6.0 / 4.0 studs (transition drum, roof to taper)
These interlock (pier top == arch apex == 24; upper floor top == roof eave
== 38) so re-tuning one requires re-deriving the others -- see the
constants block below, all in one place.

Idempotent: purges "DD_Struct_Shop" (catches Phase 1's old single box AND
all of this phase's Pier/Arch/Upper/Roof sub-objects) and "DD_Struct_Spire"
before rebuilding.
"""
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

PIER_SIZE = 6.0
ARCH_SPRINGLINE_Z = 14.0
ARCH_RISE = 10.0
ARCH_APEX_Z = ARCH_SPRINGLINE_Z + ARCH_RISE          # 24.0 -- also the pier height
ARCH_THICKNESS = 4.0
ARCH_SPAN = config.SHOP_FOOTPRINT - 2.0 * PIER_SIZE   # 48.0, inner-face to inner-face

UPPER_FLOOR_H = 14.0
UPPER_TOP_Z = ARCH_APEX_Z + UPPER_FLOOR_H              # 38.0 -- also the roof eave

ROOF_RIDGE_LEN = 20.0

SPIRE_DRUM_R = 6.0
SPIRE_DRUM_H = 4.0

# Beacon lantern room, glazed, wrapping the spire drum -- the classic
# lighthouse arrangement of a gallery, a glazed room, and a cornice under the
# taper. This is "spire_beacon" in config.LIT_LANTERN_SITES: the map's
# orientation anchor and one of only five lights left burning, so it is the
# single most important lit surface in the build.
BEACON_GALLERY_R = 7.6
BEACON_GLASS_R = 6.6
BEACON_CORNICE_R = 7.4
BEACON_GALLERY_H = 0.8
BEACON_GLASS_H = 3.2
BEACON_CORNICE_H = 0.8
BEACON_BASE_Z = config.SHOP_ROOF_Z - 0.4

OWNED_PREFIXES = [
    "DD_Struct_Shop",   # catches Phase 1's single box + all sub-parts below
    "DD_Struct_Spire",
    "DD_Lamp_SpireBeacon",
]


def purge():
    for prefix in OWNED_PREFIXES:
        dd_scene.purge_by_prefix(prefix)


def _finish(obj):
    dd_mesh.shade_flat(obj)
    dd_scene.set_origin_to_base(obj)
    dd_scene.link_to_collection(obj, "Structures")
    return obj


def build_piers():
    half = config.SHOP_FOOTPRINT / 2.0
    corner_offset = half - PIER_SIZE / 2.0
    corners = {
        "NE": (corner_offset, corner_offset),
        "NW": (-corner_offset, corner_offset),
        "SE": (corner_offset, -corner_offset),
        "SW": (-corner_offset, -corner_offset),
    }
    objs = []
    for suffix, (x, y) in corners.items():
        obj = dd_mesh.box(f"DD_Struct_ShopPier_{suffix}", PIER_SIZE, PIER_SIZE, ARCH_APEX_Z, base_z=0.0)
        obj.location = (x, y, 0.0)
        objs.append(_finish(obj))
    return objs


def build_arches():
    half = config.SHOP_FOOTPRINT / 2.0
    pier_center_offset = half - PIER_SIZE / 2.0
    walls = {
        "N": (0.0, pier_center_offset, 0.0),
        "S": (0.0, -pier_center_offset, 0.0),
        "E": (pier_center_offset, 0.0, 1.5707963267948966),   # 90 deg
        "W": (-pier_center_offset, 0.0, 1.5707963267948966),
    }
    objs = []
    for suffix, (x, y, yaw) in walls.items():
        obj = dd_mesh.arch_beam(
            f"DD_Struct_ShopArch_{suffix}",
            span=ARCH_SPAN,
            rise=ARCH_RISE,
            thickness=ARCH_THICKNESS,
            depth=PIER_SIZE,
            base_z=ARCH_SPRINGLINE_Z,
            yaw=yaw,
            samples=16,
        )
        obj.location = (x, y, 0.0)
        objs.append(_finish(obj))
    return objs


def build_upper_floor():
    obj = dd_mesh.box("DD_Struct_ShopUpper", config.SHOP_FOOTPRINT, config.SHOP_FOOTPRINT, UPPER_FLOOR_H, base_z=0.0)
    obj.location = (0.0, 0.0, ARCH_APEX_Z)
    return _finish(obj)


def build_roof():
    obj = dd_mesh.hip_roof(
        "DD_Struct_ShopRoof",
        footprint_x=config.SHOP_FOOTPRINT,
        footprint_y=config.SHOP_FOOTPRINT,
        eave_z=UPPER_TOP_Z,
        ridge_z=config.SHOP_ROOF_Z,
        ridge_len=ROOF_RIDGE_LEN,
    )
    return _finish(obj)


def build_spire():
    drum = dd_mesh.cylinder("DD_Struct_SpireDrum", SPIRE_DRUM_R, SPIRE_DRUM_H, base_z=0.0, segments=8)
    drum.location = (0.0, 0.0, config.SHOP_ROOF_Z)
    _finish(drum)

    cone_height = config.SPIRE_PEAK_Z - (config.SHOP_ROOF_Z + SPIRE_DRUM_H)
    cone = dd_mesh.cone("DD_Struct_SpireCone", SPIRE_DRUM_R, cone_height, base_z=0.0, segments=8)
    cone.location = (0.0, 0.0, config.SHOP_ROOF_Z + SPIRE_DRUM_H)
    _finish(cone)
    return [drum, cone]


def build_beacon():
    """Glazed lantern room wrapping the spire drum: gallery, glass, cornice,
    merged into one object so the glass is a Z band that lib.mood.mark_glass
    can send to the glass slot. Named DD_Lamp_SpireBeacon because that is what
    lib.mood.LIT_SITE_OBJECTS maps config's "spire_beacon" to -- without this
    object that entry in LIT_LANTERN_SITES pointed at nothing."""
    import bmesh

    from lib import mood as dd_mood

    bm = bmesh.new()
    z = 0.0
    for radius, height in ((BEACON_GALLERY_R, BEACON_GALLERY_H),
                           (BEACON_GLASS_R, BEACON_GLASS_H),
                           (BEACON_CORNICE_R, BEACON_CORNICE_H)):
        ring = bmesh.new()
        bmesh.ops.create_cone(ring, cap_ends=True, cap_tris=True, segments=8,
                              radius1=radius, radius2=radius, depth=height)
        bmesh.ops.translate(ring, verts=ring.verts, vec=(0.0, 0.0, z + height / 2.0))
        tmp = bpy.data.meshes.new("_tmp_beacon")
        ring.to_mesh(tmp)
        ring.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        z += height

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    obj = dd_mesh.bm_to_object("DD_Lamp_SpireBeacon", bm)
    obj.location = (0.0, 0.0, BEACON_BASE_Z)
    _finish(obj)
    dd_mood.mark_glass(obj, BEACON_GALLERY_H + 0.01,
                       BEACON_GALLERY_H + BEACON_GLASS_H - 0.01)
    return obj


def build():
    dd_scene.ensure_collections()
    purge()
    build_piers()
    build_arches()
    build_upper_floor()
    build_roof()
    build_spire()
    build_beacon()


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    dd_objs = [o for o in bpy.data.objects if o.name.startswith("DD_")]
    dd_palette.apply_debug_colors(dd_objs)

    top_cam = dd_scene.setup_ortho_top_camera("RenderCam_Top", ortho_scale=1000.0, height=700.0)
    dd_scene.render_to_file(top_cam, os.path.join(renders_dir, "p3_top_ortho.png"), xray=True)

    eye_cam = dd_scene.setup_eye_camera(
        "RenderCam_SpawnEye",
        location=(config.SPAWN_XY[0], config.SPAWN_XY[1], 5.0),
        facing_deg=config.SPAWN_FACING_DEG,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(eye_cam, os.path.join(renders_dir, "p3_spawn_eye.png"), xray=False)

    # Phase 3's explicit check: spire visible above the horizon from
    # (600, 0, 5) looking back toward the island.
    sea_cam = dd_scene.setup_eye_camera(
        "RenderCam_Sea600",
        location=(600.0, 0.0, 5.0),
        facing_deg=180.0,
        fov_deg=70.0,
    )
    dd_scene.render_to_file(sea_cam, os.path.join(renders_dir, "p3_sea600_lookback.png"), xray=False)

    # A close-up of the shop itself, to actually see the arches/roof/spire.
    close_cam = dd_scene.setup_eye_camera(
        "RenderCam_ShopClose",
        location=(90.0, -90.0, 12.0),
        facing_deg=135.0,
        fov_deg=60.0,
    )
    dd_scene.render_to_file(close_cam, os.path.join(renders_dir, "p3_shop_close.png"), xray=False)


if __name__ == "__main__":
    build()
    capture_renders()
