"""sRGB -> linear conversion and cached material creation.

Blender's Principled BSDF expects LINEAR colour. Assigning sRGB hex values
straight from the PALETTE dict is the #1 reason AI-built Blender scenes come
out washed out (see CLAUDE.md "known failure modes"). Always go through
hex_to_linear_rgba() / get_material() / material_for().
"""
import bpy

_MATERIAL_CACHE = {}


def srgb_to_linear(c):
    """Convert a single sRGB channel value (0-1) to linear light."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(hex_color, alpha=1.0):
    """'#RRGGBB' -> (r, g, b, a) in linear space, 0-1 floats."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), alpha)


def get_material(name, hex_color, emission_strength=0.0):
    """Return a cached Principled BSDF material for `hex_color`, creating it
    if needed. Pass emission_strength > 0 for interactable/lore glow colours
    (biolume_cyan, specimen_glow)."""
    cache_key = (name, hex_color, emission_strength)
    cached = _MATERIAL_CACHE.get(cache_key)
    if cached is not None and cached.name in bpy.data.materials:
        return cached

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    rgba = hex_to_linear_rgba(hex_color)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = rgba
        if emission_strength > 0.0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = rgba
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = rgba
    _MATERIAL_CACHE[cache_key] = mat
    return mat


def material_for(palette, key, emission_strength=0.0):
    """Convenience wrapper: material_for(config.PALETTE, 'timber_warm')."""
    mat_name = f"DD_Mat_{key}"
    return get_material(mat_name, palette[key], emission_strength=emission_strength)


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---- greybox/debug review colours (Phase 1-7 only; Phase 8 replaces these
# with the real PALETTE-driven materials) ------------------------------------
DEBUG_CATEGORY_COLORS = {
    "Terrain": "#8E9AA3",
    "Struct": "#C97B4A",
    "Plaza": "#D8C8A6",
    "Plot": "#4E7D52",
    "Dock": "#7A4E2E",
    "Prop": "#B8B0A0",
    "Nature": "#3F5F42",
    "Marker": "#A34B3C",
    "UI": "#F2C46B",
    "Lamp": "#F2C46B",
    "Overhead": "#3D6B8C",
    "Lore": "#A8E6C8",
    "Sub": "#57C7D4",
}


def debug_color_for(obj_name):
    for cat, hex_color in DEBUG_CATEGORY_COLORS.items():
        if obj_name.startswith(f"DD_{cat}_"):
            return hex_color
    return "#FFFFFF"


def apply_debug_colors(objs):
    """Assign a category-coded flat colour to each object for greybox/gate
    renders. Relying on Workbench's random per-object colouring turned out
    to be unreliable across Blender versions; explicit materials always
    render distinctly and cost nothing (Phase 8 overwrites them)."""
    for o in objs:
        if o.type != "MESH":
            continue
        hex_color = debug_color_for(o.name)
        mat = get_material(f"DDPreview_{hex_color.lstrip('#')}", hex_color)
        assign_material(o, mat)
