"""Primitive builders and mesh-level helpers.

Per CLAUDE.md operating rule 7: prefer bmesh / from_pydata over bpy.ops for
anything non-trivial. bpy.ops depends on context/selection state and breaks
silently in headless MCP execution.
"""
import math

import bmesh
import bpy


def new_mesh_object(name, verts, faces, collection=None):
    """Build a mesh object from raw vert/face lists via from_pydata. Faces
    may be tris or quads (from_pydata handles both; never emits n-gons if
    you don't pass any)."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def bm_to_object(name, bm, collection=None):
    """Write a bmesh to a new mesh object and free the bmesh."""
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def box(name, size_x, size_y, size_z, base_z=0.0, collection=None):
    """Axis-aligned box, origin at base centre (Roblox wants base-centre
    origins, not volume-centre)."""
    hx, hy = size_x / 2.0, size_y / 2.0
    verts = [
        (-hx, -hy, base_z), (hx, -hy, base_z), (hx, hy, base_z), (-hx, hy, base_z),
        (-hx, -hy, base_z + size_z), (hx, -hy, base_z + size_z),
        (hx, hy, base_z + size_z), (-hx, hy, base_z + size_z),
    ]
    faces = [
        (0, 1, 2, 3),   # bottom
        (4, 7, 6, 5),   # top
        (0, 4, 5, 1),   # -Y
        (1, 5, 6, 2),   # +X
        (2, 6, 7, 3),   # +Y
        (3, 7, 4, 0),   # -X
    ]
    return new_mesh_object(name, verts, faces, collection=collection)


def cylinder(name, radius, height, base_z=0.0, segments=16, cap_ends=True, collection=None):
    """Upright cylinder, origin at base centre. Caps are triangulated (fan)
    so the mesh never carries an n-gon."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=cap_ends, cap_tris=True, segments=segments,
        radius1=radius, radius2=radius, depth=height,
    )
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, height / 2.0 + base_z))
    return bm_to_object(name, bm, collection=collection)


def cone(name, radius, height, base_z=0.0, segments=16, collection=None):
    """Cone (e.g. the spire tip), origin at base centre."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=True, segments=segments,
        radius1=radius, radius2=0.0, depth=height,
    )
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, height / 2.0 + base_z))
    return bm_to_object(name, bm, collection=collection)


def disc(name, radius, base_z=0.0, segments=32, collection=None):
    """Flat disc, triangulated as a fan from the centre (e.g. island base)."""
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, cap_tris=True, segments=segments, radius=radius)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, base_z))
    return bm_to_object(name, bm, collection=collection)


def annulus(name, inner_radius, outer_radius, base_z=0.0, segments=64, collection=None):
    """Flat ring, quads only (the plaza floor shape)."""
    bm = bmesh.new()
    inner, outer = [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        inner.append(bm.verts.new((inner_radius * math.cos(a), inner_radius * math.sin(a), base_z)))
        outer.append(bm.verts.new((outer_radius * math.cos(a), outer_radius * math.sin(a), base_z)))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((inner[i], inner[j], outer[j], outer[i]))
    bm.normal_update()
    return bm_to_object(name, bm, collection=collection)


def shade_flat(obj):
    """Faceted shading -- the default for everything except water and rope."""
    for poly in obj.data.polygons:
        poly.use_smooth = False


def shade_smooth(obj):
    """Smooth shading -- water and rope only, per the art direction."""
    for poly in obj.data.polygons:
        poly.use_smooth = True


def recalc_normals_outward(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def cleanup_after_boolean(obj):
    """Limited dissolve -> triangulate any resulting n-gons -> recalc outward
    normals. Run this after every boolean op (gate cut, shop arches) per the
    brief's known-failure-modes list -- booleans are the main source of
    n-gons and non-manifold edges in this build."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(5.0), verts=bm.verts, edges=bm.edges)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def bevel_edges(obj, width, segments=1):
    """Add (but do NOT apply) a Bevel modifier. Applied later in
    export_fbx.py so the source mesh stays editable -- applying it in the
    build script is a known failure mode (unbeveled FBX ships silently)."""
    mod = obj.modifiers.new(name="DD_Bevel", type="BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30.0)
    return mod


def apply_transform(obj):
    """Bake scale/rotation into mesh data without bpy.ops.object.transform_apply
    (context-independent), leaving scale at (1,1,1) and rotation at (0,0,0)
    as the export contract requires."""
    import mathutils

    loc, rot, scale = obj.matrix_world.decompose()
    bake = mathutils.Matrix.Diagonal(scale).to_4x4() @ rot.to_matrix().to_4x4()
    obj.data.transform(bake)
    obj.data.update()
    obj.matrix_world = mathutils.Matrix.Translation(loc)


def triangle_count(obj):
    """Count triangles as exported (quads=2 tris, tris=1, n-gons fan-counted)."""
    total = 0
    for poly in obj.data.polygons:
        total += max(len(poly.vertices) - 2, 0)
    return total
