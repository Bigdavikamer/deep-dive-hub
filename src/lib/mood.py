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
"""
import bpy

COLOR_ATTR = "DepthDarken"
GLASS_SLOT = 1
WARM_SLOT = 2   # cloth_red / lantern_gold; rationed by WarmBudget

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
