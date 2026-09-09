"""Single source of truth. All distances in Roblox studs (1 Blender unit = 1 stud)."""
from math import radians, cos, sin

# ---- world -----------------------------------------------------------------
GROUND_Z          = 0.0      # island top surface
PLAZA_LIFT        = 1.5      # plaza raised above plot terraces
PLOT_Z            = -1.5     # plot pad height
OCEAN_FLOOR_NEAR  = -40.0    # at the gate mouth
OCEAN_FLOOR_FAR   = -120.0   # at x = 700
MAX_DIM           = 2048.0   # Roblox hard limit, any axis

# ---- island ----------------------------------------------------------------
ISLAND_RADIUS     = 235.0
COAST_JITTER      = 25.0     # +/- irregularity on the rim
COAST_SEGMENTS    = 96
RIM_WALK_WIDTH    = 25.0

# ---- centre / landmark -----------------------------------------------------
SHOP_FOOTPRINT    = 60.0     # square, centred on origin
SHOP_ROOF_Z       = 48.0
SPIRE_PEAK_Z      = 95.0     # the landmark. visible from 400 studs at sea.

# ---- plaza -----------------------------------------------------------------
PLAZA_INNER_R     = 30.0     # = SHOP_FOOTPRINT / 2
PLAZA_OUTER_R     = 135.0    # = PLOT_RING_R - PLOT_SIZE/2
PLAZA_WIDTH       = 105.0    # derived; the "more space" fix

# ---- plots -----------------------------------------------------------------
PLOT_COUNT        = 7
PLOT_SIZE         = 70.0     # square pad
PLOT_RING_R       = 170.0
PLOT_KERB_H       = 2.0
# angles measured CCW from +X (east). Gate occupies +/- GATE_HALF_ANGLE.
GATE_HALF_ANGLE   = 34.4
_ARC              = 360.0 - 2 * GATE_HALF_ANGLE      # 291.2 deg usable
_SLOT             = _ARC / PLOT_COUNT                # 41.6 deg
PLOT_ANGLES_DEG   = [GATE_HALF_ANGLE + _SLOT * (i + 0.5) for i in range(PLOT_COUNT)]
# -> [55.2, 96.8, 138.4, 180.0, 221.6, 263.2, 304.8]

def plot_xy(i):
    """Centre of plot i (0-indexed). Plot 1 = index 0 = north side of the gate."""
    a = radians(PLOT_ANGLES_DEG[i])
    return (PLOT_RING_R * cos(a), PLOT_RING_R * sin(a))

def plot_yaw(i):
    """Z-rotation so the pad's local +Y faces the plaza centre."""
    return radians(PLOT_ANGLES_DEG[i] + 90.0)

# ---- ocean gate (east) -----------------------------------------------------
GATE_WIDTH        = 260.0
BEACH_RUN         = 70.0     # horizontal run of the ramp
BEACH_DROP        = -6.0     # end Z of the ramp
BREAKWATER_REACH  = 90.0     # how far the arms curve out
DOCK_OFFSET_Y     = 45.0     # two docks at +/- this
DOCK_LENGTH       = 110.0
DOCK_MODULE_LEN   = 20.0

# ---- leaderboards ----------------------------------------------------------
LB_COURT_R        = 105.0
LB_COURT_ANGLE    = 110.0    # deg CCW from +X; NW plaza, on the spawn->shop line
LB_STELE_COUNT    = 3
LB_STELE_W        = 24.0
LB_STELE_H        = 34.0
LB_STELE_FAN      = 12.0     # deg of inward fan between stelae
LB_DAIS_H         = 3.0

# ---- spawn -----------------------------------------------------------------
SPAWN_XY          = (-125.0, 0.0)
SPAWN_FACING_DEG  = 0.0      # facing +X, toward shop and ocean gate

# ---- triangle budgets (Roblox hard cap is 20000 per mesh) -------------------
TRI_BUDGET = {
    "DD_Terrain":   8000,    # per quadrant mesh
    "DD_Struct":   12000,
    "DD_UI":         600,
    "DD_Dock":       400,
    "DD_Marker":     300,
    "DD_Prop":       150,
    "DD_Lamp":       250,
    "DD_Nature":     120,
}

# ---- palette (sRGB hex; convert to linear before assigning) ----------------
PALETTE = {
    "water_deep":    "#0B2A3D",
    "water_mid":     "#1E5A73",
    "water_shallow": "#57C7D4",
    "foam":          "#E8F4F2",
    "sand_wet":      "#C9B183",
    "sand_dry":      "#E3D2A8",
    "stone_light":   "#8E9AA3",
    "stone_dark":    "#5A6670",
    "timber_warm":   "#7A4E2E",
    "timber_dark":   "#4A2E1C",
    "roof_slate":    "#3E4C59",
    "roof_patina":   "#4FA396",
    "rope_canvas":   "#D8C8A6",
    "sea_grass":     "#4E7D52",
    "lantern_gold":  "#F2C46B",
    "biolume_cyan":  "#66E2D5",   # INTERACTABLES ONLY
    # --- dressing extensions ---
    "specimen_glow": "#A8E6C8",   # lore props only; must NOT read as cyan
    "tar_pitch":     "#2B2721",
    "iron_dark":     "#3B3F42",
    "brass_worn":    "#9C7A3C",
    "cloth_red":     "#A34B3C",   # awnings, banners, pennants
    "cloth_blue":    "#3D6B8C",
    "salt_pale":     "#DCD8CC",
    "moss_damp":     "#3F5F42",
    "barnacle":      "#B8B0A0",
}

INTERACTABLE_COLOR = "biolume_cyan"
LORE_GLOW_COLOR    = "specimen_glow"

# ---- dressing / scatter ----------------------------------------------------
TRAFFIC_LANE_WIDTH = 16.0    # radial paths, beach ramp, shop entrances
LANE_CLEARANCE     = 2.0     # extra buffer; NOTHING is placed inside lane+buffer
PLAZA_MIN_EMPTY    = 0.30    # >= 30% of plaza floor area stays clear

# props per 1000 sq studs, by zone
ZONE_DENSITY = {
    "traffic_lane":     0.0,
    "plaza_open":       1.5,
    "plaza_edge":       6.0,
    "district_core":   11.0,
    "quay_rim":         9.0,
    "beach":            4.0,
    "plot_surround":    3.0,
    "underwater_near":  7.0,
    "island_rim":       5.0,
}

SCATTER_MIN_SPACING = 6.0    # poisson-disc radius between props, studs
SCATTER_SINK        = -0.2   # sink props into ground so nothing floats
WIND_LEAN_DEG       = 8.0    # vegetation leans this far AWAY from the ocean
OVERHEAD_MIN_SITES  = 4      # minimum distinct overhead-layer locations

# ---- merchant row (the mini shop housing vendor NPCs) ----------------------
ROW_ANGLE_DEG      = 25.0    # plaza periphery, between gate lane and plot 1 lane
ROW_RADIUS         = 112.0
ROW_LENGTH         = 70.0    # along the arc (~35.8 deg at this radius)
ROW_DEPTH          = 24.0
ROW_BAYS           = 4
ROW_BAY_W          = 15.0
ROW_PIER_W         = 2.0
ROW_COUNTER_H      = 4.5
ROW_ARCADE_H       = 14.0    # underside of the arcade beam
ROW_ROOF_Z         = 22.0

# ---- dockside kiosk --------------------------------------------------------
KIOSK_XY           = (205.0, -38.0)   # top of the beach ramp, south side
KIOSK_FOOTPRINT    = 18.0

# ---- plaza enclosure (medieval square principle) ---------------------------
ENCLOSURE_COVERAGE = 0.55    # fraction of plaza outer rim backed by built mass
ENCLOSURE_H_MIN    = 18.0
ENCLOSURE_H_MAX    = 30.0    # must stay well below SHOP_ROOF_Z so the spire wins

# ---- terracing (town sits above the water; you descend to dive) ------------
WEST_TERRACE_LIFT  = 8.0
TERRACE_STEP_COUNT = 3

# ---- tide pool (second water body, west rim) -------------------------------
POOL_XY            = (-196.0, 44.0)
POOL_RADIUS        = 28.0
POOL_DEPTH         = -5.0

# ---- NPC anchors -----------------------------------------------------------
# Empties named DD_Anchor_NPC_<Name>. Exported to out/npc_anchors.json.
NPC_ANCHORS = [
    ("Tidewright",    "row_bay_1"),          # gear / equipment
    ("Fishmonger",    "row_bay_2"),          # buys catch
    ("Assayer",       "row_bay_3"),          # appraise / reroll
    ("Traveller",     "row_bay_4"),          # rotating; bay dressed as often-empty
    ("Curator",       "shop_interior_north"),# The Index
    ("Harbourmaster", "shop_interior_east"), # Depth Log / missions
    ("Innkeeper",     "plaza_west_inn"),     # set spawn
    ("Shipwright",    "kiosk"),              # dockside
    ("Deckhand",      "dock_north_head"),    # tutorial guide, first NPC seen
    ("LampTender",    "wander"),             # roams between 5 candidate anchors
]

# ---- style -----------------------------------------------------------------
BEVEL_WIDTH       = 0.6      # studs; applied to all hard structural edges
BEVEL_SEGMENTS    = 1
SCATTER_SEED      = 20260908
SCATTER_ROT_JITTER = 15.0    # deg
SCATTER_SCALE_JITTER = 0.08  # fraction
