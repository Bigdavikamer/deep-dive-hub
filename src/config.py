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
    "water_deep":    "#081E2C",
    "water_mid":     "#1A4F63",
    "water_shallow": "#4FB8C4",
    "foam":          "#DCEEEC",
    "sand_wet":      "#B7A788",
    "sand_dry":      "#D8CBA0",
    "stone_light":   "#7C8D9B",
    "stone_dark":    "#47535D",
    "timber_warm":   "#6B4A30",
    "timber_dark":   "#3A2A22",
    "roof_slate":    "#33414D",
    "roof_patina":   "#3F8F8A",
    "rope_canvas":   "#C9BFA0",
    "sea_grass":     "#3E6B5C",
    "lantern_gold":  "#E8B85C",
    "biolume_cyan":  "#5FDCD0",   # INTERACTABLES ONLY
    # --- dressing extensions ---
    "specimen_glow": "#93D9B8",   # lore props only; must NOT read as cyan
    "tar_pitch":     "#211E1D",
    "iron_dark":     "#33383C",
    "brass_worn":    "#8F7238",
    "cloth_red":     "#8F4034",   # awnings, banners, pennants
    "cloth_blue":    "#345E78",
    "salt_pale":     "#D2D6D2",
    "moss_damp":     "#335048",
    "barnacle":      "#A8AEA8",
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
# Moved off the brief's (-196, 44) r=28: that overlapped plot 4's pad by a
# 33x17 stud bite AND put the pool's far edge 2 studs past the coastline. The
# plot ring leaves only ~53-stud angular gaps between 70-stud pads, so a
# 56-diameter pool fits nowhere in it; pushed out to r=188 in the gap between
# plots 3 and 4 (angle 159.2, the smallest move off the original 167.3
# bearing) a 26-radius pool clears plot 3 and the shore by ~7 studs each.
# p2_terrain derives the coastline notch angle from POOL_XY, so the notch
# follows this on its own.
POOL_XY            = (-176.0, 67.0)
POOL_RADIUS        = 26.0
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

# ---- per-asset triangle budgets (the Phase 7a prop library table) ----------
# TRI_BUDGET above is per CATEGORY, and its DD_Prop entry (150) was written for
# small scatter props. The prop library table in CLAUDE.md gives per-ASSET
# budgets an order of magnitude larger for the set pieces -- a 900-tri market
# stall, an 1800-tri hull under repair. Both are in the brief and they
# contradict each other for anything big named DD_Prop_*. The per-asset figure
# is the more specific of the two, so validate.py check 2 prefers it and falls
# back to the category budget for anything not listed here. Keyed by the asset
# token in DD_<Category>_<Asset>_<Variant>.
PROP_TRI_BUDGET = {
    "Barrel": 150, "Crate": 140, "RopeCoil": 120, "RopeLine": 400,
    "DryingRack": 500, "HangingFish": 60, "Net": 350, "LanternPost": 250,
    "HangingLantern": 120, "Bollard": 130, "MarketStall": 900,
    "NoticeBoard": 300, "Well": 700, "TimberStack": 200, "Sawhorse": 120,
    "HullRepair": 1800, "Rowboat": 400, "Tool": 80, "GuttingTable": 450,
    "SaltVat": 200, "TallyBoard": 200, "TrophyRack": 900, "JarShelf": 350,
    "Shrine": 800, "FossilArch": 2200, "BannerPole": 250, "Awning": 180,
    "CrabPot": 160, "Buoy": 130, "Anchor": 400, "Kelp": 110, "Coral": 120,
    "Ballast": 100, "SeaGrass": 60, "Heather": 70, "Pine": 900, "Rock": 120,
    "Story": 90, "Gull": 90,
}

# ---- mood: abyss and restraint ---------------------------------------------
LIT_LANTERN_SITES = [
    "spire_beacon", "breakwater_north_cap", "breakwater_south_cap",
    "dock_north_head", "innkeeper_frontage",
]
WARM_ACCENT_MAX_PER_DISTRICT = 2
DEPTH_DARKEN_STRENGTH = 0.35

# ---- style -----------------------------------------------------------------
BEVEL_WIDTH       = 0.6      # studs; applied to all hard structural edges
BEVEL_SEGMENTS    = 1
SCATTER_SEED      = 20260908
SCATTER_ROT_JITTER = 15.0    # deg
SCATTER_SCALE_JITTER = 0.08  # fraction
