# DEEP DIVE — Hub Map Build Brief

**For: Claude Code + Blender MCP**

## How to use this file

1. `mkdir deep-dive-hub && cd deep-dive-hub && git init`
2. Save this file as `CLAUDE.md` in the repo root.
3. Open Blender, enable the MCP addon, click Connect. Confirm Claude Code sees the Blender tools.
4. Drop the blueprint image in `refs/blueprint.png`.
5. Start Claude Code and say: **"Read CLAUDE.md. Execute Phase 0, then stop."**
6. One phase per session. Commit between phases. Do not ask for the whole map in one go.

---

# MISSION

Build the surface hub map for **Deep Dive**, a Roblox ocean-exploration / fishing / RNG-collection game, as a modular low-poly asset kit in Blender, exported Studio-ready.

The hub is the safe harbour town where players spawn, own a base plot, buy gear, check leaderboards, and walk into the ocean to dive.

You are not generating meshes from text. You are **writing parameterized Python that builds geometry**, running it in Blender, looking at the result, and iterating. Every shape in this map is math. Treat it that way.

---

# OPERATING RULES

These are not suggestions. Violating them will waste hours.

1. **Every script is a file in this repo.** Never author geometry through one-off `execute_blender_code` calls that exist only in chat history. If it isn't on disk, it didn't happen.
2. **Every script is idempotent.** Each build script begins by deleting all objects whose name matches its own prefix, then rebuilds from scratch. I must be able to re-run any script at any time and get identical output.
3. **No manual Blender operations.** Do not ask me to click anything. If the scene state is wrong, fix the script and re-run.
4. **Verify visually before moving on.** After each script, capture a viewport screenshot (top-down ortho + one eye-level) and actually look at it. Describe what you see. If it doesn't match the spec, fix it before proceeding.
5. **Hard stop at every GATE.** Show me renders and wait for approval. Do not roll into the next phase.
6. **Commit after every phase** with a message naming the phase.
7. **Prefer `bmesh` and direct mesh construction over `bpy.ops`.** `bpy.ops` depends on context, selection state, and active object — it breaks silently in headless and MCP contexts. Use `bpy.data.meshes.new()` + `from_pydata()` or `bmesh` for anything non-trivial.
8. **One phase per session.** The MCP bridge degrades on long sessions with large scenes. If you feel the tool calls getting flaky, stop, commit, and tell me to start a fresh session.
9. **Ask before inventing.** If a dimension isn't in this brief and it matters, ask. Don't guess and don't silently pick.

---

# REPO STRUCTURE

Create exactly this:

```
deep-dive-hub/
├── CLAUDE.md                  # this file
├── refs/
│   └── blueprint.png
├── src/
│   ├── config.py              # ALL parameters — single source of truth
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── palette.py         # sRGB→linear, material creation
│   │   ├── mesh.py            # primitive builders, bevel, flat-shade helpers
│   │   ├── scatter.py         # seeded randomized placement
│   │   └── scene.py           # collection setup, purge-by-prefix, naming
│   ├── p1_greybox.py
│   ├── p2_terrain.py
│   ├── p3_shop.py
│   ├── p4_plaza.py
│   ├── p5_plots.py
│   ├── p6_gate.py
│   ├── p7_props.py
│   ├── p8_materials.py
│   ├── build_all.py           # runs p1..p8 in order
│   ├── validate.py            # acceptance checks, exits nonzero on failure
│   └── export_fbx.py
├── renders/                   # verification screenshots, phase-prefixed
├── out/                       # FBX exports
└── MANIFEST.md                # generated placement table
```

`config.py` is the **only** place numbers live. If a magic number appears in a build script, that's a bug.

---

# CONFIG — write this verbatim as `src/config.py`

```python
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
```

**Important:** Blender materials take **linear** RGB. Write `srgb_to_linear()` in `lib/palette.py` and run every hex through it. Assigning sRGB values directly is why AI-built Blender scenes come out washed out.

---

# HARD CONSTRAINTS (Roblox)

Non-negotiable. `validate.py` must check every one of these.

| Constraint | Rule |
|---|---|
| Triangles | **≤ 20,000 per individual mesh.** Split anything larger. |
| Watertight | No holes, no exposed backfaces, no non-manifold edges. |
| Topology | Quads wherever possible. **Zero n-gons.** |
| Volume | No zero-thickness geometry. Every mesh has thickness. |
| Transforms | Scale applied to `(1,1,1)`, rotation applied to `(0,0,0)` on every **source kit mesh** (structural builds and the Phase 7a prop-kit grid at (1000,0,0)). **Placed/scattered instances are exempt** — they legitimately carry the scatter algorithm's rotation and uniform ±`SCATTER_SCALE_JITTER` scale; that's how one linked mesh becomes 30 differently-oriented barrels. Resolves the tension with linked-mesh-data reuse (constraint below and check 17): baking rotation/scale into vertex data per instance would force unique mesh data per instance and break instancing. |
| Origins | At the object's **base centre**, not its volume centre — a property of the mesh's local vertex data (local min Z ≈ 0), independent of the object's world transform. Placed instances inherit this for free since they share the source mesh's data. |
| Size | Nothing exceeds 2048 studs on any axis. |
| Scale | Model at **1 Blender unit = 1 stud**. |

**FBX export settings** (from Roblox's own docs — use exactly these):

- Path Mode = **Copy**, **Embed Textures** enabled
- Transform → Apply Scalings = **FBX Unit Scale**
- Transform → Scale = **0.01**
- Armature → **Add Leaf Bones = off**
- **Bake Animation = off**
- Axis: `-Z forward, Y up` (Blender Z-up → Roblox Y-up)

Optionally set `scene.unit_settings.scale_length = 0.28` for live stud readouts — Roblox physics is 1 stud = 0.28 m — but **model at 1:1 unit-to-stud regardless.**

---

# LAYOUT SPEC

The blueprint in `refs/` is a **schematic**. Its proportions are the instruction. Its perfect circle is not — see the coastline rule below.

Coordinate frame: Blender Z-up. **+X = east = the ocean.** +Y = north. Origin = centre of the shop.

Three corrections to the blueprint are already agreed and are mandatory:

1. Far more space between plots and the centre shop (now 105 studs of plaza).
2. A much wider ocean opening (now 260 studs).
3. Leaderboards, placed where every player walks past them.

### Island shell
- Nominal radius **235**, broken open on the east across the gate arc.
- The rim is **not a circle.** Displace each of the 96 coastline vertices by up to ±25 studs using seeded noise. Add two rock outcrops and one tidepool notch. **No two coastline segments may be identical.** Perfect radial symmetry is the single thing that makes a hub read as a diagram instead of a place.
- Split the terrain into 4 quadrant meshes (`_NE`, `_NW`, `_SW`, `_SE`) to stay under budget.

### Shop + spire (centre, origin)
- 60 × 60 footprint, two storeys, roof ridge at Z = 48.
- Ground floor **open on all four sides** through arched stone openings — enterable from any approach.
- Beacon spire peaking at **Z = 95**. This is the map's landmark and the player's orientation anchor. It must be visible from every plot, the beach, and 400 studs out at sea.

### Plaza
- Annulus from r=30 to r=135. **105 studs wide.**
- Radial cobblestone, raised 1.5 studs above the plot terraces, single shallow step ring at the outer edge.
- Eight radial paths: seven to plots, one east to the gate.

### Plots (7)
Computed centres at r=170 — use `config.plot_xy(i)`, do not hardcode:

| Plot | Angle | X | Y |
|---|---|---|---|
| 1 | 55.2° | 97.0 | 139.6 |
| 2 | 96.8° | −20.1 | 168.8 |
| 3 | 138.4° | −127.1 | 112.9 |
| 4 | 180.0° | −170.0 | 0.0 |
| 5 | 221.6° | −127.1 | −112.9 |
| 6 | 263.2° | −20.1 | −168.8 |
| 7 | 304.8° | 97.0 | −139.6 |

Numbered counter-clockwise from the north side of the gate. Centre-to-centre arc spacing ≈ 123 studs, so ≈ 53 studs of gap between 70-stud pads.

**Build only:** the flat pad at Z = −1.5, a low stone kerb (2 studs), a plot marker post (timber post + hanging carved sign + unlit lantern), and a footpath to the plaza.
**Do not build houses.** Players and Studio scripts fill the pads.
Vary kerb stonework and sign carving per plot — no two identical.

### Ocean gate (east)
- Rim open across ±34.4°, a **260-stud** mouth.
- Beach ramp: Z 0 → −6 over 70 studs of run, centred on the +X axis. Dry sand → wet sand → shallow.
- Two stone breakwater arms curving 90 studs out from the rim edges, each capped with a lantern post. These frame the exit and give the sightline a target.
- Two timber dive docks on pilings at Y = ±45, 110 studs long, built from 20-stud modules. **These are the dive-entry points** — mark them with `biolume_cyan`.
- Beyond: three buoys, a half-sunk hull wreck, kelp and coral clusters. Ocean floor −40 at the mouth dropping to −120 by x=700.

### Leaderboard court
- Centre at r=105, θ=110° → **(−35.9, 98.7)**. NW plaza, directly on the spawn→shop walking line.
- 3 stone stelae, each **24 W × 34 H**, fanned 12° inward, on a 3-stud dais with steps.
- Each stele front face is **one clean quad with correct UVs** — Studio overlays a SurfaceGui onto it. Model the frame and the carved title band. **Do not model text.**
- Two banner poles flanking the court.

### Spawn
- **(−125, 0)**, facing +X.
- From that exact point, one camera frame at eye height (Z = 5, 70° FOV) must contain: the shop and spire, the leaderboard court, at least two plot markers, and open ocean through the gate. **Render this and check it.** If anything is occluded, move geometry, not the camera.

---

# ART DIRECTION

**Stylized low-poly medieval-nautical harbour town.** A fishing village on a sea-worn stone platform — timber framing, slate roofs, stone quays, rope, nets, lanterns, fish-drying racks. Warm and lived-in. Not realistic, not Roblox-parts blocky.

- **One material for the whole kit**, driven by a palette atlas or vertex colours. No PBR, no per-asset textures.
- **Flat / faceted shading throughout.** Smooth shading only on water and rope.
- **Bevel every hard structural edge at 0.6 studs, 1 segment.** This is the largest single difference between low-poly that looks intentional and low-poly that looks cheap. Bevels catch light and define silhouette.
- **Silhouette first.** Every prop must be identifiable as a black shape at 200 studs.
- **`biolume_cyan` is reserved for interactables only** — dive docks, shop counter, plot markers, leaderboard frames. Never decorative. This gives players a colour-coded language for "you can use this," and it ties the hub to Deep Dive's abyssal identity below the surface.
- **Break repetition.** Seeded ±15° rotation and ±8% scale on every scatter prop. Two identical barrels in the same orientation is a defect.
- **Vary height.** Terraces, steps, the raised dais, roof-line variation. A flat hub reads as dead.

### Explicitly out of scope — do not build
- Ocean water surface (Roblox Terrain water, Studio side)
- Sky, lighting, atmosphere, fog
- Anything scripted or animated
- Player structures on plots
- Collision meshes — instead, flag in `MANIFEST.md` which objects need `CollisionFidelity = Box`

---

# ENVIRONMENT DRESSING

This is the section that decides whether the map feels like a place or a diagram with objects on it. Read all of it before Phase 7.

**Core principle: build a small kit, place a lot.** Roughly **45 unique meshes → ~450 placed instances** via linked duplicates. You are not modelling 450 things. You are modelling 45 things well and placing them with intent.

## The three-layer rule

Every dressed zone needs all three. Most amateur maps have only the middle one, which is exactly why they read as flat.

| Layer | Height | Examples |
|---|---|---|
| **Ground** | 0–3 studs | Rope coils, spilled fish, crates, cobble variation, puddles, moss, tools, buckets, chain piles |
| **Mid** | 3–12 studs | Barrels, bollards, drying racks, stalls, lamp posts, sawhorses, stacked timber, wells |
| **Overhead** | 12+ studs | Rope lines strung between buildings with hanging lanterns and drying fish, banners, striped awnings, netting canopies, gull perches, hoist beams and pulleys |

The overhead layer is the highest-value, lowest-cost thing you will build. A rope line with six hanging lanterns is under 400 triangles and transforms the feel of an entire plaza quarter. **At least `OVERHEAD_MIN_SITES` distinct locations must have it.**

## Density zones — clutter belongs at the edges

Define **traffic lanes** as 16-stud corridors down: the eight radial plaza paths, the beach ramp, the four shop entrances, and each plot footpath. **Nothing is placed inside a lane plus its 2-stud buffer.** Density then rises with distance from the lane centreline, using `ZONE_DENSITY`.

This is the rule that separates "full" from "cluttered." A player must never have to navigate around your set dressing.

## District identity — the four quarters

The plaza is not uniform. Give each quarter a trade so a player can say "meet me by the drying racks" instead of "meet me at the shop."

| Quarter | District | Dressing |
|---|---|---|
| **N** | Catch & Cure | Fish-drying racks with hanging catch, salt barrels, gutting tables with scarred surfaces, hanging scales, brine vats, a chalk tally board |
| **E** (toward gate) | Outfitters | Rope coils on pegs, spare rod racks, tackle crates, weight stones, a tide-time board, sailcloth bolts |
| **S** | Ballast & Repair | Stacked timber, tar buckets and brushes, a hull under repair on trestles, sawhorses, wood shavings, an upturned rowboat |
| **W** (spawn arrival) | Market & Notices | Market stalls with striped `cloth_red` / `cloth_blue` awnings, notice board, produce crates, the stone well, benches |

Spawn faces east into the Market quarter, so **W gets the most careful pass** — it's the first thing every player sees.

## Environmental storytelling

Props that show use, not props that show existence. Each of these is cheap and does more work than ten generic barrels:

- Rope **wound around** a bollard in a figure-eight, not a coil sitting next to it
- A crate with one broken slat and its contents spilled in a small arc
- A tally board with chalk marks, some smudged out
- Boots left at the top of the dock ramp, pointing toward the water
- One chair on the rim facing the sea, with a mug beside it
- A drying net repaired with visibly mismatched twine
- **Barnacle and algae rings on the quay stones marking the tide line** — apply this consistently at a fixed Z and it reads as a real coastline instantly
- Wheel ruts worn into the cobbles where the barrows run
- A cargo hoist beam with a pulley, rope slack and hanging

Before placing any prop, answer: **who put this here, and why?** If there's no answer, don't place it.

## Deep Dive lore layer

The hub is above water in a game about what's below. The town should be visibly haunted by the deep:

- A **trophy rack** outside the shop: silhouette mounts of caught specimens, a few conspicuously empty with name plates
- A **dive-log wall** under the shop's east arch — carved boards, depth marks, names
- **Specimen jars** on shelves using `specimen_glow` (pale green). This is a deliberate second glow colour so it never competes with the interactable cyan. Do not use `biolume_cyan` for scenery, ever.
- A small **ex-voto shrine** in a stone niche on the rim: hanging tokens, tied cloth, offerings — for divers who didn't surface
- **Depth-marked mooring stones** along the breakwater, numbers deepening as they go out
- A **fossilised jaw arch** framing the top of the beach ramp. Players walk through it every single dive. Make it the threshold moment.

## Underwater dressing

Players are in this water constantly, so the first 150 studs past the docks are as visible as the plaza:

- Kelp forest in clusters, taller as depth increases
- Coral shelf along the breakwater footings
- Dropped anchors with chain runs half-buried in sand
- Ballast stone piles
- An abandoned crab-pot field, some pots collapsed
- The half-sunk hull, listing, with its mast broken toward shore
- A **scoured shelf lip** at the edge of the dressed zone — a clear sand-to-dark transition that reads as "the drop." This is the visual promise of the whole game. Do not make it subtle.

## Vegetation

Coastal, sparse, wind-shaped. Not a forest.

- Sea grass tufts in stone joints and along the rim
- Thrift and heather clumps on the terraces
- Exactly **two wind-bent pines** on the west rim — asymmetric, one taller, both leaning inland
- Lichen patches on north-facing stone, moss in the wet joints near the beach

**Lean all vegetation `WIND_LEAN_DEG` away from the ocean.** It costs one rotation value per instance and implies a prevailing wind across the whole island. It is the single cheapest atmosphere trick available.

## Prop library — build these

| Asset | Variants | Tri budget ea. | Notes |
|---|---|---|---|
| Barrel | 3 | 150 | Upright, on side, open/empty |
| Crate | 4 | 140 | One broken |
| Rope coil | 2 | 120 | Flat coil, hung loop |
| Rope line (overhead) | 3 | 400 | Modular span, with hangers |
| Fish-drying rack | 3 | 500 | Empty, half, full |
| Hanging fish | 2 | 60 | Instanced onto racks |
| Net (draped) | 3 | 350 | Wall, rack, ground pile |
| Lantern post | 2 | 250 | Plaza tall, quay short |
| Hanging lantern | 1 | 120 | For rope lines |
| Mooring bollard | 2 | 130 | With and without rope |
| Market stall | 3 | 900 | Striped awning variants |
| Notice board | 1 | 300 | Clean quad face for Studio GUI |
| Stone well | 1 | 700 | With bucket and rope |
| Timber stack | 2 | 200 | |
| Sawhorse / trestle | 2 | 120 | |
| Hull under repair | 1 | 1800 | S district centrepiece |
| Upturned rowboat | 1 | 400 | |
| Tar bucket, tools | 4 | 80 | |
| Gutting table | 1 | 450 | Scarred surface |
| Salt barrel / brine vat | 2 | 200 | |
| Tally / tide board | 2 | 200 | |
| Trophy rack | 1 | 900 | Specimen silhouette mounts |
| Specimen jar shelf | 2 | 350 | `specimen_glow` |
| Ex-voto shrine | 1 | 800 | |
| Fossil jaw arch | 1 | 2200 | Gate threshold landmark |
| Banner pole + pennant | 3 | 250 | |
| Awning (standalone) | 2 | 180 | |
| Crab pot | 2 | 160 | Intact, collapsed |
| Buoy | 3 | 130 | |
| Anchor + chain | 2 | 400 | |
| Kelp cluster | 4 | 110 | Height-graded |
| Coral cluster | 4 | 120 | |
| Ballast stone pile | 2 | 100 | |
| Sea grass tuft | 3 | 60 | |
| Thrift / heather clump | 3 | 70 | |
| Wind-bent pine | 2 | 900 | West rim only |
| Rock (shore) | 5 | 120 | |
| Boots, mug, chair, bucket | 4 | 90 | Story props |
| Gull | 2 | 90 | Perched, on rope line |

**Structures built in Phase 4b / 6, not scattered:**

| Asset | Tri budget | Notes |
|---|---|---|
| Merchant Row (whole arcade) | 6,500 | Split into 3 meshes if over budget |
| Vendor bay fitout | 700 ea. | ×4, each distinct |
| Merchant cart (movable) | 1,100 | Parks in bay 4 on a timer |
| Dockside kiosk | 1,400 | |
| Inn frontage | 2,200 | |
| Warehouse gable | 1,800 | ×2 variants |
| Boat shed | 1,600 | |
| Net loft | 1,300 | |
| Market cross | 1,200 | Octagonal plinth, 3 steps |
| Lane sign | 220 | ×8, carved icon + name |
| Cargo crane | 1,500 | North breakwater |
| Smuggler's cellar door | 800 | Barred iron, seawall, above tide line |
| Gamepass display wall | 400 | 3 clean quads, south arch |
| Temporary stall | 600 | ×3 variants, no NPC |

## Instancing rules

**Use linked mesh data for every repeat placement.** `bpy.data.objects.new(name, existing_mesh)` — never copy mesh data for a placement. One barrel mesh backing thirty objects becomes one reused `MeshId` in Studio. Duplicating the data instead means thirty uploads, thirty draw-call groups, and a Studio import that takes minutes.

## Scatter algorithm

Seeded with `SCATTER_SEED` so results are reproducible.

1. Build zone polygons (plaza quarters, quay rim, beach, plot surrounds, underwater near-field, island rim).
2. Subtract all traffic lanes plus `LANE_CLEARANCE`.
3. Poisson-disc sample each zone at `ZONE_DENSITY`, minimum spacing `SCATTER_MIN_SPACING`.
4. Assign prop classes by zone weighting — district identity drives which props are eligible where.
5. Jitter: rotation ±`SCATTER_ROT_JITTER`, uniform scale ±`SCATTER_SCALE_JITTER`.
6. Raycast down to terrain, place at hit point + `SCATTER_SINK` so nothing floats and everything sits.
7. Vegetation only: apply `WIND_LEAN_DEG` tilt on the axis pointing away from the ocean.

**Anti-repetition rule:** no two instances of the same mesh within 40 studs may share a rotation within 5°. Enforced in `validate.py`.

## Restraint

Two rules stop this becoming a junkyard:

1. **Every prop must have a reason to be where it is.** Ask the question before placing.
2. **At least `PLAZA_MIN_EMPTY` (30%) of plaza floor area stays empty.** Negative space is what makes the dressed areas read as dressed.

## Fullness acceptance checks

- From **any** point on the plaza, at least **3 visually distinct points of interest** are in frame. (POI diversity — the horizon should always offer choices.)
- Walking the rim path, something new appears roughly every **40 studs**.
- All three layers present in every district quarter.
- Overhead layer at ≥ 4 distinct sites.
- Zero props inside traffic lanes.
- Zero floating props (every prop's lowest vertex ≤ terrain surface).
- Every district quarter is identifiable from a single eye-level render without labels.

---

# MERCHANT ROW — the vendor mini-shop

The centre shop is the landmark and the main gear hall. It is not where every vendor stands. Cramming ten NPCs into one building makes it a menu, not a town.

**Merchant Row** is a covered arcade on the plaza's outer rim housing the seller NPCs.

This follows how medieval markets actually worked: temporary demountable stalls stood in the open square, while permanent retail sat at the periphery under a sheltered arcade or awning that extended into the marketplace. Two tiers of vendor architecture — build both.

### Structure

- Centred at **θ = 25°, r = 112** — plaza periphery, between the ocean-gate lane (0°) and the Plot 1 lane (55.2°). Clears both lanes with room to spare.
- **70 studs long along the arc × 24 deep**, gently curved to follow the plaza. Not a straight box.
- Ground floor is an **open colonnade facing inward**: stone piers, timber lintel at Z=14, slate roof ridge at Z=22.
- Above the arcade: a shallow second storey of shuttered windows, window boxes, and a hoist beam with pulley on the end gable. Storage over shops — the correct medieval arrangement and it adds the vertical layer.

### The four bays

Each bay is **15 studs wide** with 2-stud piers between:

| Bay | Vendor | Dressing |
|---|---|---|
| 1 | **Tidewright** — gear and equipment | Rod racks, line spools, weight stones, a hanging brass scale |
| 2 | **Fishmonger** — buys catch | Ice trough, hanging catch, gutting board, coin scale, chalk price list |
| 3 | **Assayer** — appraise and reroll | Lens on a stand, brass weights, ledger, specimen jars with `specimen_glow` |
| 4 | **Traveller** — rotating merchant | **Dressed as often-empty.** Bare counter, a folded awning, a hitching ring, cart ruts in the cobbles. Occupied only when the cart is parked. |

Bay 4 is the best idea in this section. Fisch runs an occasional travelling merchant who is only sometimes present, and an obviously vacant stall makes the town feel like it has a schedule. Build the **merchant cart** as a separate movable object so Studio can park it there on a timer.

### Per-bay geometry — every bay gets all of these

- Counter at Z=4.5, worn edge, `biolume_cyan` inlay strip on the customer side (interactable)
- Back shelf wall, 8 studs high, with bay-specific goods
- Hanging trade sign on an iron bracket, projecting into the arcade — **carved icon, no text**
- A **chalk board with a clean quad face** and correct UVs for a Studio SurfaceGui price list
- An NPC anchor Empty behind the counter, facing out
- A stool, a lantern, and one story prop per bay

### NPC anchors — the handoff to Studio

Place a named Empty at every NPC position: `DD_Anchor_NPC_Tidewright`, etc. Set Z-rotation to the facing direction.

Export `out/npc_anchors.json` with each anchor in **Roblox coordinates**, applying the axis conversion:

```
roblox_x =  blender_x
roblox_y =  blender_z
roblox_z = -blender_y
```

Studio then spawns characters by name without anyone eyeballing positions. Empties do not survive FBX cleanly — the JSON is the real deliverable.

### Dockside kiosk

A single-vendor shack at **(205, −38)**, top of the beach ramp, 18 studs square. Houses the **Shipwright**. Tarred plank walls, a corrugated tin lean-to, oar rack, a rowboat on trestles.

Separate from Merchant Row on purpose: it's the last thing you pass before diving and the first thing you see coming back.

### The Deckhand

The **tutorial guide NPC stands at the head of the north dock** — first NPC a new player meets, positioned on the walk to the water. Fisch puts its guide by the docks for exactly this reason. Give the spot a coil of rope, a crate to sit on, and a lantern so it reads as somebody's post.

### Two more NPC sites

- **Innkeeper**: a small inn frontage on the W plaza rim (Market quarter) — bay window, hanging sign, bench outside. This is the set-spawn NPC.
- **Curator and Harbourmaster**: inside the centre shop, north and east arches. Cluster related services — Fisch puts the Appraiser directly beside the Merchant's shop, and that adjacency is why players find both.

### Temporary stalls (the other tier)

Four to six demountable stalls in the open plaza: four posts, a striped `cloth_red` / `cloth_blue` awning, a trestle table, crates underneath. **These have no NPCs.** They're the market's background noise and they make Merchant Row read as the permanent, important one by contrast.

---

# REFERENCE-DERIVED RULES

Drawn from medieval market-town planning and from what shipping Roblox ocean games actually do. Each one changes geometry — none is decoration.

### 1. Enclose the square

An open plaza with nothing surrounding it does not create the feeling. Squares work because built mass on every side reflects sound and framing back at you, with the tower visible above the roofline.

My original spec left the plaza rim bare. Fix it: **back at least `ENCLOSURE_COVERAGE` (55%) of the plaza's outer rim with built mass** — Merchant Row, the inn frontage, warehouse gables, a boat shed, a net loft. Heights 18–30 studs, well under the shop's 48 so the spire always wins the skyline.

Leave the eight lane openings clear. The gaps are what make the openings read as gateways.

### 2. Terrace the town above the water

Moosewood puts its village up a slope from the docks with the lighthouse highest at the back. My flat Y=0 island wastes that.

Raise the **west half of the island by 8 studs** across 3 terrace steps. Now the town looks down on its own harbour, spawn has a commanding first view, and **every dive is a descent** before the player even touches water. That last part is thematically free and worth a lot.

### 3. Organic paths, not radial spokes

Medieval towns had irregular, organic street layouts following topography, not classical grids. My eight perfectly radial paths are a grid in polar clothing.

Keep the endpoints exact. **Bow each path's midpoint 8–14 studs off the straight line**, alternating direction, and let them kink where they meet a terrace step. Costs nothing, removes the last of the blueprint feel.

### 4. Name the lanes after trades

Medieval street names are the fossil record of the market: Bread Street, Fish Lane, Butcher Row. Sellers clustered by trade and the names outlived them.

Put a small carved lane sign at the mouth of each of the eight paths: **Netmender's Walk, Salt Lane, Tar Row, Chandler's Cut, Cooper's Way, Gutting Lane, Ballast Row, The Descent** (the east one, to the ocean). Six studs tall, iron bracket, carved icon plus the name. Players will use these names in chat. That is what makes a hub feel like a place.

### 5. Market cross

Put a **market cross on an octagonal plinth** at the plaza's west opening where spawn arrives. Genuine medieval civic furniture, strong silhouette, three steps to sit on, and it becomes the natural "meet me at the cross" landmark. 1,200 tris.

### 6. Harbour works, done properly

Real medieval harbour walls: large granite blocks with rubble infill, and **on the seaward side a protecting wall that is ramped at the top**, with rough-hewn coping stones.

Apply to both breakwaters: ramped seaward face, blocky landward face, coping stones at irregular intervals. Add a **timber cargo crane** on the north breakwater — harbour districts read as working ports because of cranes, warehouses, and vertical variation more than anything else.

### 7. A second water body

Moosewood has a freshwater pond next to the village, opposite the beach.

Add the **tide pool at (−196, 44)**, 28 stud radius, 5 deep, on the raised west terrace. Colour it `water_shallow` against the ocean's `water_deep` — the contrast reads immediately. It gives the west side a reason to exist, makes an obvious tutorial fishing spot, and gives the shrine and the two pines something to sit beside.

### 8. Hide something

Moosewood's Shady Bazaar is reached through a trapdoor inside the lighthouse. Hidden sublocations do enormous work in collection games.

Build a **smuggler's cellar entrance** under the south breakwater root: a barred iron door in the seawall, above the tide line, reachable by a narrow ledge. Model the door and ledge as real geometry; leave the interior for Studio. Discovery is the strongest hook a fishing game has and it costs 800 triangles to plant.

### 9. Reserve a monetization wall

Fisch displays its gamepasses in the village centre. Whatever you sell, you'll need the surface.

Put a **display wall on the shop's south arch**: three framed panels, clean quads, correct UVs, ready for SurfaceGui. Build the frame, never the content.

### 10. Give one NPC no fixed home

Fisch's Lantern Keeper appears in different spots around the lighthouse. It makes the world feel like it has its own life.

Place **five candidate anchors** for the LampTender — rim path, tide pool, breakwater head, behind the shop, under the fossil arch — and let Studio pick one per server.

---

# PHASES

Each phase: write the script → run it → screenshot → inspect → fix → commit.

### Phase 0 — Scaffold
Create the repo structure, `config.py` verbatim from above, and all four `lib/` modules. Write `validate.py` and `export_fbx.py` now, before any geometry — they define the contract everything else must satisfy. Confirm the Blender MCP bridge responds and report the Blender version.
**Deliverable:** repo tree, working `validate.py` that passes on an empty scene.
**🛑 GATE 0** — show me the tree and `config.py`.

### Phase 1 — Greybox
Primitives only. Correct dimensions, zero detail. Island disc, shop box, spire cylinder, plaza annulus, seven plot pads, gate cut, beach ramp wedge, dock planks, leaderboard slabs, spawn marker.
**Deliverable:** `renders/p1_top_ortho.png` and `renders/p1_spawn_eye.png`.
**🛑 GATE 1 — the most important gate in the build.** Spacing is nearly free to change here and expensive later. Do not add a single detail until I approve the greybox.

### Phase 2 — Terrain shell
Coastline with seeded irregularity, four quadrant meshes, rim walk, terraces, outcrops, tidepool notch, ocean floor slope.
**Check:** no two coastline segments identical; each quadrant ≤ 8,000 tris.

### Phase 3 — Shop + spire
The landmark. Everything else is scaled against it. Arched openings on all four sides, two storeys, slate roof, spire to Z=95.
**Check:** render from (600, 0, 5) looking back — spire must be clearly visible above the horizon.

### Phase 4 — Plaza, paths, leaderboard court
Radial cobblestone, step ring, eight paths (bowed per rule 3, with trade-name lane signs), west terrace lift and steps, market cross, dais, three stelae with clean quad faces, banner poles.
**🛑 GATE 2** — render the spawn sightline frame. All five required elements visible or we adjust.

### Phase 4b — Merchant Row and plaza enclosure
Merchant Row with all four bays, the inn frontage, warehouse gables, boat shed, net loft. Verify `ENCLOSURE_COVERAGE` is met and the lane openings are still clear. Place all NPC anchor Empties and emit `out/npc_anchors.json`.
**Check:** stand a camera at the plaza centre and rotate 360° — built mass should read as a room with eight doorways, spire above the roofline in every frame.

### Phase 5 — Plots
Seven pads, kerbs, marker posts, footpaths. Per-plot variation.

### Phase 6 — Ocean gate and harbour works
Beach ramp, breakwater arms with ramped seaward faces and coping stones, timber cargo crane on the north arm, lantern caps, two modular docks, the dockside kiosk, the smuggler's cellar door, buoys, wreck, kelp, coral. Tide pool on the west terrace.

### Phase 7a — Prop kit
Build every unique mesh in the prop library table, nothing placed yet. Lay them out on a grid off to the side at (1000, 0, 0) for review. Respect per-asset tri budgets.
**Deliverable:** `renders/p7a_kit_sheet.png` — orthographic contact sheet of the whole kit.
**🛑 GATE 3** — the kit is the map's entire vocabulary. Approve it before anything gets placed.

### Phase 7b — Zones, lanes, scatter
Build zone polygons, subtract traffic lanes, run the seeded Poisson-disc scatter, place by district weighting, raycast-settle everything. Linked mesh data only.
**Check:** run the fullness acceptance checks. Render each district quarter at eye level.

### Phase 7c — Hand-placed storytelling
Scatter cannot do intent. Place these by hand, in script, with explicit coordinates: the overhead rope lines, the fossil jaw arch, the trophy rack, the dive-log wall, the ex-voto shrine, the hull under repair, the two wind-bent pines, the chair facing the sea, the boots at the dock, the tide-line barnacle rings, the wheel ruts.
**Deliverable:** one eye-level render per district plus one from the dock looking back at town.

### Phase 8 — Materials, validation, export
Palette atlas, material assignment, `biolume_cyan` audit, full `validate.py` run, FBX export per collection, generate `MANIFEST.md`.

---

# NAMING

`DD_<Category>_<Name>_<Variant>`

Categories: `Terrain`, `Struct`, `Plot`, `Dock`, `Prop`, `Nature`, `Marker`, `UI`, `Lamp`, `Overhead`, `Lore`, `Sub`.

Examples: `DD_Struct_Shop_Main`, `DD_Terrain_Island_NE`, `DD_UI_LeaderboardStele_01`, `DD_Prop_Barrel_A`, `DD_Overhead_RopeLine_N02`, `DD_Lore_FossilArch`, `DD_Sub_KelpCluster_C`.

Placed instances append a district and index: `DD_Prop_Barrel_A.MarketW.017`.

Collections: `Terrain / Structures / Plaza / Plots / Docks / Props / Overhead / Nature / Underwater / Lore / Markers`.

`validate.py` enforces the naming regex. Anything unmatched is a failure.

---

# `validate.py` — required checks

Exit nonzero and print a per-object report on any failure.

| # | Check |
|---|---|
| 1 | Every mesh ≤ 20,000 triangles |
| 2 | Every mesh within its `TRI_BUDGET` category |
| 3 | Zero non-manifold edges (`bmesh` select_non_manifold) |
| 4 | Zero n-gons (no polygon with > 4 verts) |
| 5 | Zero loose verts / loose edges / interior faces |
| 6 | Source kit meshes (unplaced structural/terrain builds and the Phase 7a kit grid): scale `(1,1,1)`, rotation `(0,0,0)`. Placed/scattered instances (name ends `.District.Index`): scale must be uniform and within ±`SCATTER_SCALE_JITTER` of 1; rotation is unconstrained (that's the scatter jitter) |
| 7 | Every object's mesh data has its base at local Z ≈ 0 (±0.01) — checked in local space, so it holds for placed instances regardless of world rotation |
| 8 | No object dimension > 2048 |
| 9 | Every object name matches the naming regex |
| 10 | Every object assigned to exactly one collection |
| 11 | `biolume_cyan` appears only on objects in the interactable allowlist |
| 12 | Anti-repetition — no two instances of the same mesh within 40 studs share rotation within 5° |
| 13 | All materials use linear-converted colours |
| 14 | Total scene triangle count reported (target: under 400k for the whole hub) |
| 15 | **Zero props inside any traffic lane + `LANE_CLEARANCE`** |
| 16 | **Zero floating props** — every prop's lowest vertex within 0.3 studs of the terrain below it |
| 17 | **Linked data enforced** — no mesh datablock has exactly one user if it appears in the prop library |
| 18 | Plaza empty floor area ≥ `PLAZA_MIN_EMPTY` |
| 19 | Overhead-layer objects present at ≥ `OVERHEAD_MIN_SITES` distinct locations |
| 20 | All three layers (ground / mid / overhead) represented in each district quarter |
| 21 | `specimen_glow` used only on `DD_Lore_*` objects; `biolume_cyan` only on the interactable allowlist |
| 22 | All `DD_Nature_*` instances carry the wind lean |
| 23 | **Every entry in `NPC_ANCHORS` has a matching Empty**, and `out/npc_anchors.json` round-trips to the same positions |
| 24 | Plaza rim enclosure ≥ `ENCLOSURE_COVERAGE`, with all eight lane openings unobstructed |
| 25 | No enclosure building exceeds `ENCLOSURE_H_MAX`, and none occludes the spire from any plaza point |
| 26 | Every GUI surface (stelae, chalk boards, notice board, gamepass wall) is a **single planar quad with non-overlapping UVs** |
| 27 | No path is perfectly straight — every one bows ≥ 8 studs at its midpoint |

---

# DEFINITION OF DONE

- [ ] `validate.py` exits 0
- [ ] Spawn sightline frame contains shop+spire, leaderboards, 2+ plot markers, open ocean
- [ ] Spire visible from (600, 0, 5)
- [ ] All 7 plots reachable from plaza in ≤ 12 s walking (≈190 studs at walkspeed 16)
- [ ] Coastline has no repeated segment
- [ ] `biolume_cyan` on interactables only
- [ ] Every prop readable as a silhouette at 200 studs
- [ ] All fullness acceptance checks pass
- [ ] Each district quarter identifiable from one unlabelled eye-level render
- [ ] The fossil jaw arch frames the beach ramp from the plaza approach
- [ ] `out/npc_anchors.json` written, all 10 anchors present, Roblox-space coordinates verified
- [ ] From plaza centre, a 360° turn reads as an enclosed square with eight doorways
- [ ] Merchant Row bay 4 reads as vacant-but-used without the cart parked
- [ ] Every dive begins with a descent — the west terrace steps down to the water
- [ ] FBX files in `out/`, each importing into Studio without scale or orientation correction
- [ ] `MANIFEST.md` lists every object with stud position, rotation, collection, tri count, and collision-fidelity flag
- [ ] Every phase committed

---

# KNOWN FAILURE MODES

Read these before you start. Each has cost people hours.

- **`bpy.ops` in MCP context** — silently operates on the wrong object or no-ops entirely because context/selection isn't what you assume. Use `bpy.data` and `bmesh`.
- **sRGB assigned as linear** — everything comes out pale and chalky. Convert.
- **Bevel modifier not applied before export** — the FBX ships unbeveled and the whole style collapses. Apply modifiers in the export script, not the build script, so the source stays editable.
- **Boolean cuts producing n-gons and non-manifold edges** — the gate opening and the shop arches are the risk spots. Run a cleanup pass (limited dissolve → triangulate → recalc normals outward) after every boolean, and re-check manifold.
- **Unapplied scale after mirroring or arraying** — mirrors flip normals. Recalculate outward.
- **Building the whole map as one mesh** — instantly blows the 20k cap and makes it unusable in Studio. Modular from the start.
- **Perfect symmetry** — the failure mode that ships. If the top-down render looks like the blueprint, you haven't done Phase 2 properly.
- **Copied mesh data instead of linked** — 450 unique datablocks, a Studio import that crawls, and 450 separate mesh uploads. Check user counts before export.
- **Uniform scatter density** — evenly-sprinkled props read as noise, not as a lived-in town. Density must vary sharply between lane, edge, and district core.
- **Dressing in the walking lanes** — the fastest way to make a beautiful map feel bad to play. Lane subtraction happens before scatter, not after.
- **Props floating or half-sunk** — always raycast to the actual terrain surface. Never assume Z=0; the terrain has jitter and terraces.
- **Cyan leaking into scenery** — the moment a decorative prop glows cyan, the interactable colour language is dead and players stop trusting it.

---

# ASK ME ABOUT

Stop and ask rather than guessing: shop interior layout, how many plot marker sign variants, whether the wreck should be enterable, banner heraldry, whether plots need visible ownership state, anything where a wrong assumption costs a rebuild.
