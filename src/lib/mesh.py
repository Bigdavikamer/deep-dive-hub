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


def box(name, size_x, size_y, size_z, base_z=0.0, yaw=0.0, collection=None):
    """Axis-aligned (or footprint-yawed) box, origin at base centre.

    `yaw` (radians) is baked into the LOCAL vertex data, not the object
    transform -- source kit / structural objects must keep identity
    rotation (see CLAUDE.md HARD CONSTRAINTS > Transforms), so any rotation
    a structural build needs (e.g. a plot pad facing the plaza) has to live
    in the mesh itself. Use obj.location for translation-only placement
    afterward; that's always allowed regardless.
    """
    hx, hy = size_x / 2.0, size_y / 2.0
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    if yaw:
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        corners = [(x * cos_y - y * sin_y, x * sin_y + y * cos_y) for x, y in corners]
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners
    verts = [
        (x0, y0, base_z), (x1, y1, base_z), (x2, y2, base_z), (x3, y3, base_z),
        (x0, y0, base_z + size_z), (x1, y1, base_z + size_z),
        (x2, y2, base_z + size_z), (x3, y3, base_z + size_z),
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


def wedge_solid(name, radius, angle_start_deg, angle_end_deg, thickness, segments=48, base_z=0.0, collection=None):
    """A solid pie-wedge disc spanning [angle_start_deg, angle_end_deg] (CCW
    from +X), full `radius`, extruded down by `thickness` below `base_z`.
    Fully manifold, quads + triangle fans only, built directly (no boolean)
    -- this is how the island greybox gets its gate notch without hitting
    the boolean-cut n-gon/non-manifold failure mode CLAUDE.md warns about."""
    bm = bmesh.new()
    a0, a1 = math.radians(angle_start_deg), math.radians(angle_end_deg)
    arc_top, arc_bot = [], []
    for i in range(segments + 1):
        t = a0 + (a1 - a0) * i / segments
        x, y = radius * math.cos(t), radius * math.sin(t)
        arc_top.append(bm.verts.new((x, y, base_z)))
        arc_bot.append(bm.verts.new((x, y, base_z - thickness)))
    center_top = bm.verts.new((0.0, 0.0, base_z))
    center_bot = bm.verts.new((0.0, 0.0, base_z - thickness))
    bm.verts.ensure_lookup_table()

    for i in range(segments):
        bm.faces.new((center_top, arc_top[i], arc_top[i + 1]))
        bm.faces.new((center_bot, arc_bot[i + 1], arc_bot[i]))
        bm.faces.new((arc_top[i], arc_top[i + 1], arc_bot[i + 1], arc_bot[i]))
    bm.faces.new((center_top, arc_top[0], arc_bot[0], center_bot))
    bm.faces.new((center_top, center_bot, arc_bot[segments], arc_top[segments]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm_to_object(name, bm, collection=collection)


def terrain_quadrant(name, angle_start_deg, angle_end_deg, segments, mid_radius, outer_radius_fn, outer_z_fn, thickness, base_z=0.0, collection=None):
    """One quadrant of undulating terrain: a flat disc from the centre out
    to `mid_radius`, then a variable-radius / variable-height band from
    `mid_radius` out to `outer_radius_fn(angle)` at height `base_z +
    outer_z_fn(angle)`. Fully solid/watertight (top, bottom, rim wall, two
    radial end walls), built directly with bmesh -- this is how the island's
    coastline gets per-angle noise/terracing without a boolean.

    `outer_radius_fn`/`outer_z_fn` take an angle in degrees and must return
    the exact same value for a shared boundary angle between two adjacent
    quadrant calls, or the quadrants won't line up seamlessly.
    """
    bm = bmesh.new()
    mid_top, mid_bot, outer_top, outer_bot = [], [], [], []
    for i in range(segments + 1):
        t_deg = angle_start_deg + (angle_end_deg - angle_start_deg) * i / segments
        t = math.radians(t_deg)
        cos_t, sin_t = math.cos(t), math.sin(t)

        mx, my = mid_radius * cos_t, mid_radius * sin_t
        mid_top.append(bm.verts.new((mx, my, base_z)))
        mid_bot.append(bm.verts.new((mx, my, base_z - thickness)))

        r_out = outer_radius_fn(t_deg)
        z_out = base_z + outer_z_fn(t_deg)
        ox, oy = r_out * cos_t, r_out * sin_t
        outer_top.append(bm.verts.new((ox, oy, z_out)))
        outer_bot.append(bm.verts.new((ox, oy, base_z - thickness)))

    center_top = bm.verts.new((0.0, 0.0, base_z))
    center_bot = bm.verts.new((0.0, 0.0, base_z - thickness))
    bm.verts.ensure_lookup_table()

    for i in range(segments):
        bm.faces.new((center_top, mid_top[i], mid_top[i + 1]))
        bm.faces.new((center_bot, mid_bot[i + 1], mid_bot[i]))
        bm.faces.new((mid_top[i], mid_top[i + 1], outer_top[i + 1], outer_top[i]))
        bm.faces.new((mid_bot[i], outer_bot[i], outer_bot[i + 1], mid_bot[i + 1]))
        bm.faces.new((outer_top[i], outer_top[i + 1], outer_bot[i + 1], outer_bot[i]))

    # two radial end walls (quadrant boundary edges)
    for idx in (0, segments):
        bm.faces.new((center_top, mid_top[idx], mid_bot[idx], center_bot) if idx == 0
                      else (center_top, center_bot, mid_bot[idx], mid_top[idx]))
        bm.faces.new((mid_top[idx], outer_top[idx], outer_bot[idx], mid_bot[idx]) if idx == 0
                      else (mid_top[idx], mid_bot[idx], outer_bot[idx], outer_top[idx]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm_to_object(name, bm, collection=collection)


def arch_beam(name, span, rise, thickness, depth, base_z, yaw=0.0, samples=16, collection=None):
    """A solid stone arch band (half-ellipse profile) spanning `span` studs
    wide and `rise` studs tall, `thickness` studs thick (radially) and
    `depth` studs deep. Local X = across the span (-span/2..span/2), local
    Y = depth, local Z = base_z (springline) up to base_z+rise (apex).
    `yaw` bakes footprint rotation into local vertex data (see box()) so the
    same beam can be reused for a wall running along X or along Y while the
    object keeps identity rotation. Built directly via bmesh (no boolean) --
    CLAUDE.md flags boolean cuts as the #1 risk for shop-arch geometry.
    """
    a_out, b_out = span / 2.0, rise
    a_in, b_in = max(a_out - thickness, 0.5), max(b_out - thickness, 0.5)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    def rot(x, y):
        return (x * cos_y - y * sin_y, x * sin_y + y * cos_y)

    bm = bmesh.new()
    outer_f, outer_b, inner_f, inner_b = [], [], [], []
    for i in range(samples + 1):
        t = math.pi * i / samples
        cos_t, sin_t = math.cos(t), math.sin(t)
        z_out, z_in = base_z + b_out * sin_t, base_z + b_in * sin_t
        ox, oy = rot(a_out * cos_t, -depth / 2.0)
        outer_f.append(bm.verts.new((ox, oy, z_out)))
        ox, oy = rot(a_out * cos_t, depth / 2.0)
        outer_b.append(bm.verts.new((ox, oy, z_out)))
        ix, iy = rot(a_in * cos_t, -depth / 2.0)
        inner_f.append(bm.verts.new((ix, iy, z_in)))
        ix, iy = rot(a_in * cos_t, depth / 2.0)
        inner_b.append(bm.verts.new((ix, iy, z_in)))
    bm.verts.ensure_lookup_table()

    for i in range(samples):
        j = i + 1
        bm.faces.new((outer_f[i], outer_f[j], outer_b[j], outer_b[i]))   # outer curved face
        bm.faces.new((inner_b[i], inner_b[j], inner_f[j], inner_f[i]))   # inner curved face
        bm.faces.new((inner_f[i], inner_f[j], outer_f[j], outer_f[i]))   # front flat face
        bm.faces.new((outer_b[i], outer_b[j], inner_b[j], inner_b[i]))   # back flat face
    bm.faces.new((outer_f[0], outer_b[0], inner_b[0], inner_f[0]))       # start end cap
    bm.faces.new((inner_f[samples], inner_b[samples], outer_b[samples], outer_f[samples]))  # end cap

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return bm_to_object(name, bm, collection=collection)


def hip_roof(name, footprint_x, footprint_y, eave_z, ridge_z, ridge_len, collection=None):
    """A simple hip roof: rectangular eave line, a short ridge centred and
    aligned along X, 4 sloped faces + a flat underside cap. Built directly
    via from_pydata (no boolean)."""
    hx, hy = footprint_x / 2.0, footprint_y / 2.0
    rh = ridge_len / 2.0
    verts = [
        (-hx, -hy, eave_z), (hx, -hy, eave_z), (hx, hy, eave_z), (-hx, hy, eave_z),  # 0-3 eave corners
        (-rh, 0.0, ridge_z), (rh, 0.0, ridge_z),  # 4,5 ridge ends
    ]
    faces = [
        (0, 1, 2, 3),      # underside cap
        (0, 1, 5, 4),      # south slope (trapezoid)
        (2, 3, 4, 5),      # north slope (trapezoid)
        (1, 2, 5),         # east hip (triangle)
        (3, 0, 4),         # west hip (triangle)
    ]
    obj = new_mesh_object(name, verts, faces, collection=collection)
    recalc_normals_outward(obj)
    return obj


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
