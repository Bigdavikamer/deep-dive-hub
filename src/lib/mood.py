"""Mood directive: abyss and restraint. See CLAUDE.md "MOOD DIRECTIVE".

Three levers, and this module is where each becomes machine-readable so that
Phase 8's material pass has something concrete to act on rather than a prose
rule someone has to remember.

1. LIGHT IS SCARCE. Lanterns are modelled identically whether lit or not --
   the difference is which material their glass takes. Since no build script
   assigns PALETTE materials (Phase 8 owns that, and the DDPreview_* swatches
   in the scene are render-time only and get reapplied on every capture), the
   distinction cannot live in a material today. It lives instead in the mesh:
   mark_glass() puts every lantern's glass faces in material slot 1, leaving
   the ironwork in slot 0, and LIT_SITE_OBJECTS records which of those slot-1
   surfaces are the five that stay lit. Phase 8 then paints slot 1 as
   lantern_gold with emission for the lit five and dark unlit glass for
   everything else, without having to identify glass geometrically.

2. WARM COLOUR IS RATIONED. WarmBudget enforces
   config.WARM_ACCENT_MAX_PER_DISTRICT per plaza quarter at placement time,
   so the cap is applied while things are being positioned rather than audited
   afterwards when it is too late to move anything.

3. DEPTH GETS DARKER. apply_depth_darken() bakes a per-vertex multiply that
   falls off with Z, independent of Studio's lighting -- the hub has to read
   as sitting above something dark even with scene lighting switched off,
   which is exactly the case in the Workbench verification renders.

POLISH PASS (post-Phase-8): two more vertex-colour bakes, same philosophy --
data for Studio to consume on import, not wired into a Blender shader node
graph, because Workbench's MATERIAL preview reads a material's flat
diffuse_color and cannot evaluate a procedural node graph anyway (see the
existing DepthDarken bake, which is already invisible in every MATERIAL-mode
render for the same reason).

4. CAVITY/AO. apply_cavity_darken() extends the "depth gets darker" lever to
   the WHOLE scene: concave interior corners and every mesh's own base (where
   a prop touches the ground) darken, multiplied into the same COLOR_ATTR
   channel any object already carries from lever 3. Computed purely from
   local mesh geometry, never world position, so one bake per shared mesh
   datablock holds correctly across every linked, differently-placed
   instance.

5. TERRAIN GETS A GRADIENT, NOT A FLAT TONE. apply_terrain_blend() replaces
   the island terrain's single "stone_light" material read with a per-vertex
   blend across config.TERRAIN_BLEND_BANDS -- wet sand low and near the
   water, drier sand and stone climbing the west terraces, dark stone on the
   steep terrace risers, moss on north-facing rock. Written to its own
   TERRAIN_TINT_ATTR layer (a base-colour replacement) rather than into
   COLOR_ATTR (a darken multiplier) -- mixing the two into one channel would
   make either unrecoverable from the other.
"""
import math

import bmesh
import bpy

COLOR_ATTR = "DepthDarken"
TERRAIN_TINT_ATTR = "TerrainTint"
GLASS_SLOT = 1
WARM_SLOT = 2   # cloth_red / lantern_gold; rationed by WarmBudget
GLOW_SLOT = 3   # specimen_glow; DD_Lore_* only, never biolume_cyan
# Weathering marks (rowboat / hull-under-repair only, see p7a_kit._hull_weather
# and p8_materials.resolve_slots): a tarred seam, a patched plank in a
# different tone, and a barnacle/waterline ring at the mesh's own base.
WEATHER_DARK_SLOT = 4
WEATHER_LIGHT_SLOT = 5
WEATHER_RING_SLOT = 6

# Which object carries each site named in config.LIT_LANTERN_SITES. Entries may
# name objects that later phases build; is_lit() simply never matches those
# until they exist, and audit_lit_sites() reports which are still missing.
LIT_SITE_OBJECTS = {
    "spire_beacon":         "DD_Lamp_SpireBeacon",
    "breakwater_north_cap": "DD_Lamp_BreakwaterNorth",
    "breakwater_south_cap": "DD_Lamp_BreakwaterSouth",
    "dock_north_head":      "DD_Lamp_DockNorthHead",
    "innkeeper_frontage":   "DD_Lamp_InnFrontage",
}


def is_lit(object_name):
    """True only for the handful of lanterns that stay lit. Everything else in
    the kit is modelled with dark glass."""
    return object_name in set(LIT_SITE_OBJECTS.values())


def audit_lit_sites(config):
    """Report which of config.LIT_LANTERN_SITES have a real object yet.
    Returns (present, missing) as lists of site keys."""
    present, missing = [], []
    for site in config.LIT_LANTERN_SITES:
        name = LIT_SITE_OBJECTS.get(site)
        (present if name and bpy.data.objects.get(name) else missing).append(site)
    return present, missing


def _ensure_slots(obj, count):
    while len(obj.data.materials) < count:
        obj.data.materials.append(None)


def mark_glass(obj, z_min, z_max, local=True):
    """Put every face whose centre falls in the [z_min, z_max] band into the
    glass material slot. The lantern builders merge plate/body/roof/finial into
    one mesh, so the glass is a Z band rather than a separate object -- this
    assigns slot indices only and never touches topology, which is what makes
    it a legal edit on already-built geometry.

    Returns the number of faces marked.
    """
    mesh = obj.data
    _ensure_slots(obj, GLASS_SLOT + 1)
    offset = 0.0 if local else -obj.location.z
    marked = 0
    for poly in mesh.polygons:
        z = poly.center.z + offset
        if z_min <= z <= z_max:
            poly.material_index = GLASS_SLOT
            marked += 1
    mesh.update()
    return marked


def mark_all(obj, slot):
    """Put every face of `obj` in `slot`. For whole-object surfaces such as an
    awning or a pennant, where the entire mesh is the cloth."""
    _ensure_slots(obj, slot + 1)
    for poly in obj.data.polygons:
        poly.material_index = slot
    obj.data.update()
    return len(obj.data.polygons)


def mark_where(obj, predicate, slot):
    """Set material_index = slot for every polygon whose LOCAL-space centre
    satisfies predicate(center). Generic selective-face marking for one-off
    weathering details (a tarred seam, a patched plank, a waterline ring)
    that aren't a simple Z band, unlike mark_glass."""
    mesh = obj.data
    _ensure_slots(obj, slot + 1)
    marked = 0
    for poly in mesh.polygons:
        if predicate(poly.center):
            poly.material_index = slot
            marked += 1
    mesh.update()
    return marked


def apply_depth_darken(obj, strength, z_light, z_dark):
    """Bake a per-vertex multiply that darkens with depth: 1.0 at z_light,
    (1 - strength) at z_dark, linear between and clamped outside. Written to
    the COLOR_ATTR layer as greyscale; Phase 8 multiplies base colour by it.

    Z is read in world space, so a mesh keeps the same darkening regardless of
    where its origin sits -- these are terrain and water meshes whose origins
    were moved to base centre.
    """
    mesh = obj.data
    attr = mesh.color_attributes.get(COLOR_ATTR)
    if attr is None:
        attr = mesh.color_attributes.new(name=COLOR_ATTR, type="FLOAT_COLOR", domain="POINT")
    span = (z_dark - z_light) or 1.0
    z_off = obj.location.z
    for i, vert in enumerate(mesh.vertices):
        t = (vert.co.z + z_off - z_light) / span
        t = min(max(t, 0.0), 1.0)
        f = 1.0 - strength * t
        attr.data[i].color = (f, f, f, 1.0)
    mesh.update()
    return attr


def apply_flat_darken(obj, factor):
    """Uniform multiply for geometry that is shadowed by enclosure rather than
    by depth -- under the arcade, the cellar ledge, recessed niches."""
    mesh = obj.data
    attr = mesh.color_attributes.get(COLOR_ATTR)
    if attr is None:
        attr = mesh.color_attributes.new(name=COLOR_ATTR, type="FLOAT_COLOR", domain="POINT")
    for i in range(len(mesh.vertices)):
        attr.data[i].color = (factor, factor, factor, 1.0)
    mesh.update()
    return attr


def apply_cavity_darken(obj, strength, contact_band=2.0):
    """Approximate cavity/AO baked into vertex colour: darkens concave
    interior edges (corners, recesses) and vertices near the mesh's own
    local base (every prop-to-ground contact reads as a soft contact
    shadow). Both signals are pure functions of the mesh's LOCAL geometry,
    never world position, so this can run once per shared mesh datablock and
    hold correctly across every linked instance regardless of where the
    scatter placed it -- no raytrace/bake-to-scene AO pass needed, which
    would have to run per placement instead of per datablock.

    Multiplies into whatever DepthDarken/flat-darken bake the mesh already
    carries (water, recessed geometry) rather than overwriting it -- cavity
    is meant to stack with those, not replace them. A mesh with no prior
    bake starts from a clean 1.0 and just gets the cavity/contact darkening
    on its own.
    """
    mesh = obj.data
    if not mesh.vertices:
        return None

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    cap = math.radians(75.0)
    concavity = [0.0] * len(bm.verts)
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            continue
        angle = edge.calc_face_angle_signed()
        if angle >= 0.0:
            continue  # convex or flat; only concave corners darken
        factor = min(-angle / cap, 1.0)
        for v in edge.verts:
            if factor > concavity[v.index]:
                concavity[v.index] = factor
    bm.free()

    zs = [v.co.z for v in mesh.vertices]
    z_min = min(zs)
    band = max(min(contact_band, max(zs) - z_min), 1e-4)

    had_attr = COLOR_ATTR in mesh.color_attributes
    attr = mesh.color_attributes.get(COLOR_ATTR)
    if attr is None:
        attr = mesh.color_attributes.new(name=COLOR_ATTR, type="FLOAT_COLOR", domain="POINT")

    for i, vert in enumerate(mesh.vertices):
        contact = max(0.0, 1.0 - (vert.co.z - z_min) / band)
        ao = max(concavity[i], contact)
        existing = attr.data[i].color[0] if had_attr else 1.0
        f = existing * (1.0 - strength * ao)
        attr.data[i].color = (f, f, f, 1.0)
    mesh.update()
    return attr


def _smoothstep(edge0, edge1, x):
    if edge0 >= edge1:
        return 1.0 if x >= edge0 else 0.0
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def apply_terrain_blend(obj, bands, palette, north_bias, moss_key="moss_damp"):
    """Height/slope-driven vertex-colour gradient for terrain, replacing a
    flat single material tone. `bands` is config.TERRAIN_BLEND_BANDS: keys
    are (z_min, z_max, max_slope_deg) tuples mapped to a PALETTE key. For
    each vertex, every band whose z-range contains the vertex's WORLD height
    contributes a soft weight -- smoothstepped across a small margin at every
    edge, including the slope cap -- and the result is a weighted blend of
    those bands' colours: a gradient, not a hard per-vertex cutoff, which is
    what keeps a coarse low-poly mesh from banding visibly. Rock bands
    (stone_light/stone_dark) additionally pick up a moss tint on
    north-facing slopes (+Y), scaled by `north_bias`.

    Written to its own TERRAIN_TINT_ATTR layer rather than into COLOR_ATTR --
    see the module docstring, lever 5.
    """
    from lib import palette as dd_palette

    mesh = obj.data
    if not mesh.vertices:
        return None

    z_margin = 1.0
    slope_margin = 8.0
    rock_keys = {"stone_light", "stone_dark"}

    band_list = list(bands.items())
    linear = {key: dd_palette.hex_to_linear_rgba(palette[key])[:3] for _, key in band_list}
    moss_rgb = dd_palette.hex_to_linear_rgba(palette[moss_key])[:3]

    attr = mesh.color_attributes.get(TERRAIN_TINT_ATTR)
    if attr is None:
        attr = mesh.color_attributes.new(name=TERRAIN_TINT_ATTR, type="FLOAT_COLOR", domain="POINT")

    z_off = obj.location.z
    for i, vert in enumerate(mesh.vertices):
        z = vert.co.z + z_off
        nrm = vert.normal
        slope_deg = math.degrees(math.acos(min(max(nrm.z, -1.0), 1.0)))
        north = max(nrm.y, 0.0)

        weights = []
        for (z0, z1, cap), key in band_list:
            in_z = _smoothstep(z0 - z_margin, z0, z) * (1.0 - _smoothstep(z1, z1 + z_margin, z))
            in_slope = 1.0 - _smoothstep(cap, cap + slope_margin, slope_deg)
            weights.append((key, in_z * in_slope))
        total = sum(w for _, w in weights)

        if total < 1e-6:
            # No band's soft window reached this vertex (an extreme
            # slope/height combination the config didn't cover) -- fall back
            # to whichever band is nearest, so nothing is left unpainted.
            def _dist(item):
                (z0, z1, cap), key = item
                zc = min(max(z, z0), z1)
                return abs(z - zc) + max(slope_deg - cap, 0.0)
            (_, _, _), nearest_key = min(band_list, key=_dist)
            r, g, b = linear[nearest_key]
            rock_frac = 1.0 if nearest_key in rock_keys else 0.0
        else:
            r = sum(linear[k][0] * w for k, w in weights) / total
            g = sum(linear[k][1] * w for k, w in weights) / total
            b = sum(linear[k][2] * w for k, w in weights) / total
            rock_frac = sum(w for k, w in weights if k in rock_keys) / total

        moss = min(max(north_bias * north * rock_frac, 0.0), 1.0)
        r = r * (1.0 - moss) + moss_rgb[0] * moss
        g = g * (1.0 - moss) + moss_rgb[1] * moss
        b = b * (1.0 - moss) + moss_rgb[2] * moss
        attr.data[i].color = (r, g, b, 1.0)

    mesh.update()
    return attr


class WarmBudget:
    """Rations cloth_red / lantern_gold to WARM_ACCENT_MAX_PER_DISTRICT per
    plaza quarter. Ask before placing a warm accent; if it returns False the
    caller falls back to cloth_blue or bare stone/timber.

    Districts are the four plaza quarters named in CLAUDE.md: N Catch & Cure,
    E Outfitters, S Ballast & Repair, W Market & Notices.
    """

    def __init__(self, cap):
        self.cap = cap
        self.used = {}

    @staticmethod
    def district_for(x, y):
        """Which plaza quarter a point falls in. E is the gate side (+X)."""
        import math
        a = math.degrees(math.atan2(y, x)) % 360.0
        if a < 45.0 or a >= 315.0:
            return "E"
        if a < 135.0:
            return "N"
        if a < 225.0:
            return "W"
        return "S"

    def take(self, district):
        """Claim one warm accent for `district`. True if granted."""
        n = self.used.get(district, 0)
        if n >= self.cap:
            return False
        self.used[district] = n + 1
        return True

    def report(self):
        return dict(self.used)
