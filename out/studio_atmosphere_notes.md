# Studio atmosphere notes

Documentation only. Nothing in this repo builds fog, haze, or atmosphere
geometry, and no build script sets these values -- see CLAUDE.md's explicit
scope exclusion. Roblox's real-time `Lighting.FogColor`/`FogStart`/`FogEnd`
and `Atmosphere` render every frame against the live camera and the actual
lit scene; anything faked into a static mesh here would look wrong underneath
them the moment real lighting is switched on. This is a starting point for
whoever sets `Lighting`/`Atmosphere` in Studio, derived from the two
`PALETTE` water tones already in `src/config.py` (`water_deep` / `water_mid`)
so the fog reads as a continuation of the water rather than a mismatched
add-on.

## Source colours

| Key | Hex | RGB (0-255) |
|---|---|---|
| `water_deep` | `#081E2C` | `8, 30, 44` |
| `water_mid` | `#1A4F63` | `26, 79, 99` |

These are the same sRGB hex values `src/config.py` stores in `PALETTE` --
`Color3.fromRGB()` expects sRGB 0-255 the same way, so no linear conversion
is needed here (that conversion in `lib/palette.py` is specific to feeding
Blender's Principled BSDF, which wants linear light).

## Suggested `Lighting` fog

```lua
Lighting.FogColor = Color3.fromRGB(26, 79, 99)   -- water_mid
Lighting.FogStart = 150
Lighting.FogEnd   = 1400
```

- `FogColor` = `water_mid` directly: a fog that reads as "more of the same
  water," not a generic grey haze. If it reads too dark against the sky once
  real lighting is in, a lightened variant is `Color3.fromRGB(60, 105, 122)`
  (`water_mid` blended 15% toward white) -- try that before reaching for an
  unrelated colour.
- `FogStart = 150` keeps the plaza, the gate mouth and the near dock
  dressing crisp; haze only starts past the breakwater tips (`BREAKWATER_REACH
  = 90` from the rim).
- `FogEnd = 1400` is deliberately generous. CLAUDE.md's Definition of Done
  requires the spire visible from `(600, 0, 5)` (`SPIRE_PEAK_Z = 95`) --
  `renders/p8_sea600.png` confirms this in the unfogged Workbench render,
  but fog is the one thing that can undo it in Studio
  without touching a single mesh. Verify the spire is still legible from 600
  studs out with fog live before shipping; raise `FogEnd` rather than
  lowering `FogStart` if it washes out, since `FogStart` is what protects the
  near dressing.

## Suggested `Atmosphere`

```lua
local atmosphere = Instance.new("Atmosphere")
atmosphere.Density = 0.3
atmosphere.Offset  = 0.3
atmosphere.Color   = Color3.fromRGB(26, 79, 99)   -- water_mid, the near tint
atmosphere.Decay   = Color3.fromRGB(8, 30, 44)    -- water_deep, the far/high decay tone
atmosphere.Glare   = 0.1
atmosphere.Haze    = 2.0
atmosphere.Parent  = Lighting
```

- `Color` (nearby tint) uses `water_mid`, `Decay` (the colour distance/altitude
  fades toward) uses `water_deep` -- the same near/far pairing as the fog
  above, so the two systems agree with each other instead of fighting.
- `Glare = 0.1` is deliberately low: MOOD DIRECTIVE (CLAUDE.md) rations warm
  light and light generally (`LIT_LANTERN_SITES` is five sites, everything
  else unlit glass) -- a glary atmosphere would fight that restraint.
- `Density`/`Offset`/`Haze` are reasonable starting points, not measured
  against anything in this repo (there is no in-Studio render to check them
  against yet). Tune them in Studio against the actual sky/lighting setup
  before treating these as final.

## Why this is a note and not a script

Every other deliverable in this repo is built or exported by a script that
can be re-run (`src/p*.py`, `src/export_fbx.py`). Fog and atmosphere are
excluded from that on purpose: they are Studio `Lighting`/`Atmosphere`
properties, not Blender geometry, and this repo has no Studio-side build
step to set them programmatically. Whoever wires up `Lighting` in Studio
should treat the values above as a first pass, not a fixed spec.
