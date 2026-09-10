"""Phase 7a -- Prop kit. GATE 3.

Every unique mesh in the CLAUDE.md prop library: 39 asset types, 91 variants,
nothing placed. They are laid out on a review grid at (1000, 0, 0), well clear
of the hub, because these are SOURCE meshes -- Phase 7b makes ~450 placed
instances from them with linked mesh data, and the kit objects stay where they
are as the datablock owners.

This is the map's entire vocabulary, which is why it gates. Two rules drive
every shape here:

  SILHOUETTE FIRST. Each prop has to be identifiable as a black shape at 200
  studs, so the polygon budget goes into the outline -- a barrel's taper, a
  gull's head, the hook of a crab pot -- and never into surface detail that
  vanishes at distance.

  BREAK REPETITION. Variants differ in proportion and arrangement, not just
  scale. Anything seeded uses lib.parts.seeded() off SCATTER_SEED so the kit
  rebuilds identically, and the five shore rocks are genuinely five rocks.

MOOD DIRECTIVE. Lanterns in the kit are unlit by construction: their glass
goes to the glass slot and none of them is in LIT_LANTERN_SITES, so Phase 8
paints them dark. Cloth comes in a blue default and a warm variant rather than
one warm default -- Phase 7b asks lib.mood.WarmBudget which it may place, so
the ration is enforced where the decision actually happens. Specimen jars use
the glow slot, never biolume_cyan, keeping the interactable colour language
intact.

Budgets are per asset, from the library table, now in config.PROP_TRI_BUDGET.
The per-category TRI_BUDGET caps DD_Prop at 150, which the table contradicts
for every set piece; validate.py prefers the per-asset figure.

Idempotent: purges DD_*_*_<variant> kit objects by the prefixes it owns.
"""
import math
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import bmesh
import bpy
import mathutils

import config
from lib import mesh as dd_mesh
from lib import mood as dd_mood
from lib import palette as dd_palette
from lib import parts as P
from lib import scene as dd_scene

KIT_ORIGIN = (1000.0, 0.0, 0.0)
GRID_COLS = 10
# 13 was too tight: the 18-stud rope-line spans overlapped their neighbours on
# the contact sheet, which is the one artefact this phase exists to be judged on.
GRID_SPACING = 19.0

TIMBER = 0.9


# ---------------------------------------------------------------- containers

def barrel(bm, v, rng):
    """0 upright, 1 on its side, 2 open and empty."""
    if v == 2:
        P.tube(bm, (0, 0, 1.7), 1.6, 1.25, 3.4, segments=8)
        for hz in (0.7, 2.7):
            P.cylinder(bm, (0, 0, hz), 1.72, 0.22, segments=8)
        return
    if v == 1:
        P.cylinder(bm, (0, 0, 1.6), 1.6, 3.4, segments=8, r_top=1.6, pitch=math.pi / 2)
        for off in (-1.0, 1.0):
            P.cylinder(bm, (off, 0, 1.6), 1.72, 0.22, segments=8, pitch=math.pi / 2)
        return
    P.cylinder(bm, (0, 0, 1.75), 1.45, 3.5, segments=8)
    P.cylinder(bm, (0, 0, 1.75), 1.68, 1.4, segments=8)
    for hz in (0.5, 3.0):
        P.cylinder(bm, (0, 0, hz), 1.6, 0.24, segments=8)


def crate(bm, v, rng):
    """3 is the broken one, with a sprung slat and its contents spilled."""
    s = (3.0, 3.0, 2.6) if v != 2 else (3.6, 2.4, 2.2)
    P.box(bm, (0, 0, s[2] / 2), s)
    for dz in (0.3, s[2] - 0.3):
        P.box(bm, (0, 0, dz), (s[0] + 0.16, s[1] + 0.16, 0.3))
    if v == 1:
        P.box(bm, (0, 0, s[2] + 0.9), (2.4, 2.4, 1.6))
    if v == 3:
        P.box(bm, (s[0] / 2 + 0.4, 0.4, 1.9), (0.3, 2.6, 0.9), yaw=0.35)
        for k in range(3):
            P.sphere(bm, (2.6 + k * 1.1, -0.5 - k * 0.5, 0.35), 0.42,
                     segments=6, rings=3, jitter=0.25, rng=rng)


def timber_stack(bm, v, rng):
    rows = 2 if v == 0 else 3
    for r in range(rows):
        n = 3 if r % 2 == 0 else 2
        for i in range(n):
            off = (i - (n - 1) / 2.0) * 1.5
            P.cylinder(bm, (off, 0, 0.75 + r * 1.35), 0.7, 6.0, segments=6,
                       pitch=math.pi / 2)


def salt_vat(bm, v, rng):
    if v == 0:
        P.tube(bm, (0, 0, 1.5), 1.9, 1.5, 3.0, segments=8)
        P.cylinder(bm, (0, 0, 2.7), 2.0, 0.3, segments=8)
    else:
        P.tube(bm, (0, 0, 1.1), 2.6, 2.2, 2.2, segments=8)
        P.cylinder(bm, (0, 0, 2.0), 2.7, 0.3, segments=8)


# -------------------------------------------------------------------- ropes

def rope_coil(bm, v, rng):
    if v == 0:
        n = 8
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            r = 1.5
            P.strut(bm, (r * math.cos(a0), r * math.sin(a0), 0.2),
                    (r * math.cos(a1), r * math.sin(a1), 0.2), 0.45)
    else:
        # A closed hanging loop, not a half-arc. The half-arc version was a
        # single vertical stroke in the silhouette sheet -- unreadable as a
        # black shape, which is the one thing every prop here has to pass.
        n = 8
        rw, rh = 1.15, 1.75
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            P.strut(bm, (0, rw * math.cos(a0), 2.4 + rh * math.sin(a0)),
                    (0, rw * math.cos(a1), 2.4 + rh * math.sin(a1)), 0.48)


def rope_line(bm, v, rng):
    """Modular overhead span. The highest-value, lowest-cost thing in the kit:
    a line with hangers transforms a whole plaza quarter for ~200 tris."""
    span, sag = 18.0, 1.6 + 0.5 * v
    top = 13.0
    n = 5
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((-span / 2 + span * t, 0.0, top - sag * math.sin(math.pi * t)))
    for i in range(n):
        P.strut(bm, pts[i], pts[i + 1], 0.22)
    # Lanterns hang LEVEL with each other, on hangers of differing length,
    # rather than each dangling a fixed drop below a sagging line. That is how
    # a real festoon is rigged, and it puts every lantern body in one flat Z
    # band so mark_glass can find them -- without it the glass is scattered
    # through the mesh at per-hanger heights, and these lanterns ended up
    # painted as pale rope canvas, reading as LIT when the whole point of the
    # mood directive is that they are not.
    hangers = (2, 3, 4)[v]
    lantern_top = top - sag - 1.9
    for k in range(hangers):
        t = (k + 1) / (hangers + 1)
        i = min(int(t * n), n - 1)
        x, _y, z = pts[i]
        P.strut(bm, (x, 0, z), (x, 0, lantern_top), 0.16)
        if v == 0:
            P.box(bm, (x, 0, lantern_top - 0.8), (1.3, 1.3, 1.6))
        else:
            P.cylinder(bm, (x, 0, lantern_top - 0.8), 0.55, 1.6, segments=6, r_top=0.0)


def net(bm, v, rng):
    """Draped: 0 on a wall, 1 over a rack, 2 piled on the ground."""
    if v == 2:
        for k in range(4):
            P.sphere(bm, (rng.uniform(-1, 1), rng.uniform(-1, 1), 0.35 + k * 0.16),
                     1.3 - k * 0.18, segments=6, rings=3, jitter=0.3, rng=rng, squash=0.35)
        return
    w, h = 5.0, 4.5
    sag = 0.9 if v == 1 else 0.3
    for i in range(4):
        x = -w / 2 + w * i / 3
        P.strut(bm, (x, 0, h), (x, sag, 0.2), 0.13)
    for j in range(4):
        z = h * (1 - j / 3.0) + 0.2
        d = sag * (j / 3.0)
        P.strut(bm, (-w / 2, d, z), (w / 2, d, z), 0.13)


# ------------------------------------------------------------------ fishing

def drying_rack(bm, v, rng):
    """0 empty, 1 half, 2 full -- the N quarter's signature."""
    w, h = 6.0, 5.5
    for sx in (-1, 1):
        P.box(bm, (sx * w / 2, 0, h / 2), (0.5, 0.5, h))
        P.box(bm, (sx * w / 2, 0, h - 0.4), (0.5, 2.4, 0.4))
    for dy in (-0.9, 0.9):
        P.strut(bm, (-w / 2, dy, h - 0.6), (w / 2, dy, h - 0.6), 0.28)
    count = (0, 3, 6)[v]
    for k in range(count):
        x = -w / 2 + 0.9 + k * (w - 1.8) / max(count - 1, 1)
        dy = -0.9 if k % 2 == 0 else 0.9
        P.cylinder(bm, (x, dy, h - 1.9), 0.42, 2.2, segments=5, r_top=0.1)


def hanging_fish(bm, v, rng):
    ln = 2.2 if v == 0 else 1.6
    P.cylinder(bm, (0, 0, -ln / 2), 0.42, ln, segments=5, r_top=0.12, pitch=0.0)
    P.pyramid(bm, (0, 0, -ln - 0.3), 0.8, 0.7)


def gutting_table(bm, v, rng):
    P.box(bm, (0, 0, 3.0), (6.0, 2.6, 0.5))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box(bm, (sx * 2.6, sy * 1.0, 1.5), (0.4, 0.4, 3.0))
    for k in range(4):    # scars worn into the top
        P.box(bm, (-2.0 + k * 1.3, rng.uniform(-0.6, 0.6), 3.26),
              (0.14, 1.6, 0.06), yaw=rng.uniform(-0.3, 0.3))


def crab_pot(bm, v, rng):
    if v == 1:      # collapsed
        P.sphere(bm, (0, 0, 0.5), 1.5, segments=6, rings=3, squash=0.3,
                 jitter=0.25, rng=rng)
        P.strut(bm, (-1.4, -0.6, 0.3), (1.2, 0.9, 0.9), 0.14)
        return
    P.sphere(bm, (0, 0, 0.9), 1.6, segments=6, rings=3, squash=0.62)
    for k in range(4):
        a = math.pi * k / 4
        P.strut(bm, (1.6 * math.cos(a), 1.6 * math.sin(a), 0.1),
                (-1.6 * math.cos(a), -1.6 * math.sin(a), 0.1), 0.13)


# ---------------------------------------------------------------- furniture

def bollard(bm, v, rng):
    P.cylinder(bm, (0, 0, 1.3), 0.85, 2.6, segments=8)
    P.cylinder(bm, (0, 0, 2.75), 1.05, 0.5, segments=8)
    if v == 1:      # rope wound in a figure eight, not a coil set beside it
        # two wraps, not three: the third put this 6 tris over the 130 budget
        for k in range(2):
            P.strut(bm, (-1.0, -0.5, 0.8 + k * 0.5), (1.0, 0.5, 1.0 + k * 0.5), 0.2)
            P.strut(bm, (-1.0, 0.5, 1.0 + k * 0.5), (1.0, -0.5, 0.8 + k * 0.5), 0.2)


def sawhorse(bm, v, rng):
    ln = 4.0 if v == 0 else 3.0
    P.box(bm, (0, 0, 2.4), (ln, 0.5, 0.5))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.strut(bm, (sx * ln * 0.35, 0, 2.3), (sx * ln * 0.45, sy * 1.1, 0.0), 0.35)


def market_stall(bm, v, rng):
    """Awning: 0 blue (the default), 1 warm, 2 striped. Phase 7b asks
    WarmBudget before placing 1 or 2, so the ration binds at placement."""
    w, d, h = 6.0, 4.0, 6.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box(bm, (sx * w / 2, sy * d / 2, h / 2), (0.4, 0.4, h))
    P.box(bm, (0, 0, 3.0), (w - 0.6, d - 0.8, 0.4))          # trestle table
    P.box(bm, (0, -d / 2 + 0.6, 1.0), (2.2, 1.6, 2.0))        # crates beneath
    if v == 2:
        for k in range(4):
            P.box(bm, (-w / 2 + 0.9 + k * 1.6, 0, h + 0.3), (1.5, d + 1.0, 0.35))
    else:
        P.box(bm, (0, 0, h + 0.3), (w + 0.8, d + 1.0, 0.35))


def awning(bm, v, rng):
    w = 5.0 if v == 0 else 3.6
    P.box(bm, (0, 0, 6.0), (w, 3.0, 0.3))
    for sx in (-1, 1):
        P.strut(bm, (sx * w / 2, 1.4, 6.0), (sx * w / 2, 1.4, 0.0), 0.3)


def well(bm, v, rng):
    P.tube(bm, (0, 0, 1.6), 2.6, 2.0, 3.2, segments=8)
    for sx in (-1, 1):
        P.box(bm, (sx * 2.2, 0, 5.0), (0.45, 0.45, 6.6))
    P.pyramid(bm, (0, 0, 8.9), 6.4, 2.2)
    P.cylinder(bm, (0, 0, 7.8), 0.28, 4.6, segments=6, pitch=math.pi / 2)
    P.strut(bm, (0, 0, 7.6), (0, 0, 4.4), 0.14)
    P.tube(bm, (0, 0, 3.9), 0.85, 0.65, 1.2, segments=6)


def notice_board(bm, v, rng):
    for sx in (-1, 1):
        P.box(bm, (sx * 2.2, 0, 2.6), (0.45, 0.45, 5.2))
    P.box(bm, (0, 0, 5.2), (5.2, 0.4, 3.6))
    P.box(bm, (0, 0, 7.3), (5.6, 0.6, 0.6))


def tally_board(bm, v, rng):
    P.box(bm, (0, 0, 3.4), (4.4, 0.35, 3.0))
    for sx in (-1, 1):
        P.box(bm, (sx * 1.9, 0, 1.6), (0.4, 0.4, 3.2))
    if v == 1:
        P.box(bm, (0, 0, 5.1), (4.8, 0.5, 0.5))


# --------------------------------------------------------------------- boats

def rowboat(bm, v, rng):
    """Upturned on the shore -- keel up, the classic repair-yard silhouette."""
    for i in range(5):
        t = i / 4.0
        w = 3.2 * math.sin(math.pi * (0.18 + 0.64 * t))
        P.box(bm, (-5.0 + t * 10.0, 0, 1.1), (2.2, w, 1.6))
    P.box(bm, (0, 0, 2.1), (10.4, 0.6, 0.5))


def hull_repair(bm, v, rng):
    """The S district centrepiece: a hull up on trestles, ribs exposed."""
    for i in range(6):
        t = i / 5.0
        w = 4.2 * math.sin(math.pi * (0.14 + 0.72 * t))
        P.box(bm, (-7.0 + t * 14.0, 0, 4.4), (2.6, w, 3.0))
    for k in range(5):
        x = -5.0 + k * 2.5
        P.box(bm, (x, 0, 6.6), (0.4, 4.6, 1.6))
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.strut(bm, (sx * 4.5, 0, 2.9), (sx * 5.2, sy * 2.2, 0.0), 0.5)
        P.box(bm, (sx * 4.8, 0, 3.0), (0.6, 5.0, 0.5))


def buoy(bm, v, rng):
    r = (1.5, 1.2, 1.8)[v]
    P.cylinder(bm, (0, 0, 1.2), r, 2.4, segments=8, r_top=r * 0.7)
    P.cylinder(bm, (0, 0, 2.9), r * 0.65, 1.0, segments=6)
    if v == 2:
        P.cylinder(bm, (0, 0, 4.6), 0.22, 2.4, segments=5, r_top=0.0)
    else:
        P.cylinder(bm, (0, 0, 4.0), 0.22, 1.4, segments=5)


def anchor(bm, v, rng):
    P.box(bm, (0, 0, 3.0), (0.7, 0.7, 6.0))
    P.box(bm, (0, 0, 5.6), (3.2, 0.6, 0.6))
    for sx in (-1, 1):
        P.strut(bm, (0, 0, 1.0), (sx * 2.4, 0, 2.4), 0.6)
        P.pyramid(bm, (sx * 2.7, 0, 2.7), 1.5, 1.2)
    if v == 1:
        for k in range(5):
            P.strut(bm, (0.4 + k * 1.3, 0.2 * k, 5.7 - k * 0.9),
                    (1.6 + k * 1.3, 0.3 * k, 5.2 - k * 0.9), 0.34)


# ---------------------------------------------------------------------- lore

def trophy_rack(bm, v, rng):
    P.box(bm, (0, 0, 4.0), (7.0, 0.5, 8.0))
    for sx in (-1, 1):
        P.box(bm, (sx * 3.6, 0, 4.0), (0.6, 0.9, 8.4))
    shapes = 5
    for k in range(shapes):
        x = -2.4 + k * 1.2
        z = 6.2 if k % 2 == 0 else 4.4
        if k in (1, 4):      # conspicuously empty mounts, name plate only
            P.box(bm, (x, 0.4, z - 1.0), (1.0, 0.2, 0.35))
            continue
        P.cylinder(bm, (x, 0.5, z), 0.55, 1.9, segments=5, r_top=0.12, pitch=0.5)
        P.box(bm, (x, 0.4, z - 1.4), (1.0, 0.2, 0.35))


def jar_shelf(bm, v, rng):
    n = 3 if v == 0 else 4
    P.box(bm, (0, 0, 3.2), (n * 1.6 + 0.8, 1.4, 0.35))
    P.box(bm, (0, 0, 1.6), (n * 1.6 + 0.8, 1.4, 0.3))
    for k in range(n):
        x = -(n - 1) * 0.8 + k * 1.6
        P.cylinder(bm, (x, 0, 4.0), 0.55, 1.3, segments=6)
        P.cylinder(bm, (x, 0, 2.3), 0.5, 1.1, segments=6)


def shrine(bm, v, rng):
    """Ex-voto niche for divers who did not surface."""
    P.box(bm, (0, 0, 3.2), (4.4, 1.6, 6.4))
    P.box(bm, (0, -0.5, 3.0), (2.8, 0.8, 4.0))
    P.pyramid(bm, (0, 0, 7.2), 5.0, 1.6)
    for k in range(4):
        x = -1.1 + k * 0.75
        P.strut(bm, (x, -1.0, 4.6), (x + rng.uniform(-0.2, 0.2), -1.1, 3.1), 0.12)
        P.box(bm, (x, -1.05, 2.8), (0.5, 0.2, 0.6))
    P.box(bm, (0, -1.0, 1.2), (3.0, 1.0, 0.5))


def fossil_arch(bm, v, rng):
    """The threshold every dive passes through, so it gets the detail its
    2200-tri budget allows rather than the 248 a coarse version cost: 12
    segments a side for a jaw that actually curves, 8 teeth each, and a
    buried root block so it reads as risen out of the sand rather than set
    on top of it."""
    # 30 wide. The arch straddles the gate lane so players walk through it every
    # dive, which means ALL of its low geometry has to clear the 16-stud
    # corridor plus its 2-stud buffer. At span 24 the legs cleared but the
    # lowest teeth -- offset inward and pointing further in -- reached about
    # 9.8 studs and clipped the walk. Measuring the teeth rather than the legs
    # is the point: the widest part of the silhouette was never the constraint.
    span, height = 30.0, 15.0
    for sy in (-1, 1):
        prev = None
        n = 12
        for i in range(n + 1):
            t = i / n
            ang = math.pi * 0.5 * t
            x = sy * (span / 2) * math.cos(ang)
            z = height * math.sin(ang)
            cur = (x, sy * 1.3 * (1 - t * 0.55), z)
            if prev:
                P.strut(bm, prev, cur, 1.9 - 1.0 * t)
            prev = cur
        # root block, half-buried
        P.sphere(bm, (sy * span / 2, sy * 1.1, 0.9), 2.3, segments=6, rings=3,
                 jitter=0.25, rng=rng, squash=0.7)
        for k in range(8):
            t = 0.10 + k * 0.105
            ang = math.pi * 0.5 * t
            x = sy * (span / 2) * math.cos(ang)
            z = height * math.sin(ang)
            P.cylinder(bm, (x - sy * 1.0, sy * 0.7, z), 0.46 - 0.02 * k, 2.1,
                       segments=4, r_top=0.0, pitch=sy * math.pi / 2)


# ------------------------------------------------------------------- lights

def lantern_post(bm, v, rng):
    """0 tall plaza, 1 short quay. Glass band is marked by the caller."""
    h = 11.0 if v == 0 else 7.0
    P.cylinder(bm, (0, 0, h / 2), 0.35, h, segments=6)
    P.box(bm, (0, 0.7, h - 0.3), (0.3, 1.8, 0.3))
    P.box(bm, (0, 1.4, h - 1.0), (1.9, 1.9, 0.3))        # plate  (below glass)
    P.box(bm, (0, 1.4, h - 2.3), (1.5, 1.5, 2.2))        # GLASS
    P.pyramid(bm, (0, 1.4, h - 3.8), 2.1, 1.0)           # roof


def hanging_lantern(bm, v, rng):
    P.strut(bm, (0, 0, 4.0), (0, 0, 3.2), 0.16)
    P.box(bm, (0, 0, 3.0), (1.8, 1.8, 0.3))              # plate
    P.box(bm, (0, 0, 1.8), (1.4, 1.4, 2.1))              # GLASS
    P.pyramid(bm, (0, 0, 0.4), 2.0, 0.9)


def banner_pole(bm, v, rng):
    h = 12.0 + v * 1.5
    P.cylinder(bm, (0, 0, h / 2), 0.32, h, segments=6)
    P.cylinder(bm, (0, 0, h + 0.4), 0.5, 0.8, segments=6, r_top=0.0)
    if v == 2:      # swallow-tail pennant
        P.box(bm, (0, 1.4, h - 2.6), (0.16, 2.4, 3.0))
        P.box(bm, (0, 2.9, h - 1.9), (0.16, 1.0, 1.2))
    else:
        P.box(bm, (0, 1.3, h - 2.4), (0.16, 2.2, 3.4))


# ------------------------------------------------------------------- nature

def kelp(bm, v, rng):
    """Height-graded: taller with depth, which is how the underwater near-field
    reads as getting deeper as you swim out."""
    h = 5.0 + v * 3.0
    for k in range(2 + (v % 2)):
        P.blade(bm, (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0.0),
                h * rng.uniform(0.75, 1.1), 1.1, bend=1.6 + 0.5 * v,
                segments=2, yaw=rng.uniform(0, 6.28))


def sea_grass(bm, v, rng):
    for k in range(2):
        P.blade(bm, (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0.0),
                1.6 + 0.4 * v, 0.5, bend=0.5, segments=2, yaw=rng.uniform(0, 6.28))


def heather(bm, v, rng):
    P.sphere(bm, (0, 0, 0.5), 1.1 + 0.2 * v, segments=6, rings=3, squash=0.45,
             jitter=0.3, rng=rng)
    P.sphere(bm, (rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0.75), 0.6,
             segments=6, rings=3, squash=0.5, jitter=0.3, rng=rng)


def coral(bm, v, rng):
    n = 2 + v % 3
    for k in range(n):
        P.sphere(bm, (rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0),
                      0.6 + rng.uniform(0, 0.8)),
                 0.75 + rng.uniform(0, 0.5), segments=6, rings=3,
                 jitter=0.35, rng=rng, squash=0.9)


def ballast(bm, v, rng):
    for k in range(3 + v):
        P.sphere(bm, (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2),
                      0.4 + rng.uniform(0, 0.5)),
                 0.6 + rng.uniform(0, 0.25), segments=6, rings=3,
                 jitter=0.3, rng=rng, squash=0.7)


def rock(bm, v, rng):
    P.sphere(bm, (0, 0, 0.9 + v * 0.25), 1.3 + v * 0.35, segments=6, rings=3,
             jitter=0.4, rng=rng, squash=0.72)


def pine(bm, v, rng):
    """Wind-shaped, west rim only. Built UPRIGHT: the lean comes from the
    placement rotation, the same treatment every other DD_Nature_ instance
    gets. Baking it into the mesh as well would double it, and it would stop
    tracking WIND_LEAN_DEG if that value ever changed. The asymmetry -- one
    taller, foliage massed off-centre -- stays in the geometry, which is what
    makes the two pines read as a pair rather than a mirror."""
    h = 14.0 if v == 0 else 10.0
    segs = 3
    drift = 0.45 if v == 0 else 0.8
    for i in range(segs):
        P.cylinder(bm, (i * drift, 0, h * (i / segs + 0.5 / segs)),
                   0.75 - 0.18 * i, h / segs, segments=6, r_top=0.6 - 0.18 * i)
    for k in range(3):
        z = h * (0.55 + k * 0.16)
        P.sphere(bm, (drift * 2.0 + k * 0.55, rng.uniform(-0.4, 0.4), z),
                 3.0 - k * 0.7, segments=6, rings=3, squash=0.5,
                 jitter=0.25, rng=rng)


def gull(bm, v, rng):
    P.sphere(bm, (0, 0, 0.8), 0.75, segments=6, rings=3, squash=0.8)
    P.sphere(bm, (0.6, 0, 1.35), 0.38, segments=6, rings=3)
    P.pyramid(bm, (1.15, 0, 1.3), 0.32, 0.5, yaw=0.0)
    P.pyramid(bm, (-0.9, 0, 0.85), 0.6, 0.9, yaw=0.4)
    if v == 1:      # gripping a rope line, legs tucked
        P.box(bm, (0, 0, 0.15), (0.5, 0.7, 0.3))


# ------------------------------------------------------------- story props

def tool(bm, v, rng):
    """Tar bucket, brush, mallet, adze."""
    if v == 0:
        P.tube(bm, (0, 0, 0.8), 0.85, 0.65, 1.6, segments=6)
        P.strut(bm, (-0.85, 0, 1.5), (0.85, 0, 1.5), 0.12)
    elif v == 1:
        P.cylinder(bm, (0, 0, 1.4), 0.16, 2.8, segments=5)
        P.box(bm, (0, 0, 0.25), (0.6, 0.5, 0.5))
    elif v == 2:
        P.cylinder(bm, (0, 0, 1.1), 0.16, 2.2, segments=5)
        P.cylinder(bm, (0, 0, 2.35), 0.42, 1.1, segments=6, pitch=math.pi / 2)
    else:
        P.cylinder(bm, (0, 0, 1.2), 0.16, 2.4, segments=5)
        P.box(bm, (0, 0.35, 2.4), (0.25, 1.0, 0.7), yaw=0.0)


def story(bm, v, rng):
    """Boots at the dock head, a mug, the chair facing the sea, a bucket."""
    if v == 0:
        for sy in (-1, 1):
            P.box(bm, (0, sy * 0.45, 0.4), (1.4, 0.6, 0.8))
            P.box(bm, (-0.5, sy * 0.45, 0.95), (0.5, 0.55, 0.5))
    elif v == 1:
        P.tube(bm, (0, 0, 0.45), 0.42, 0.3, 0.9, segments=6)
        P.strut(bm, (0.42, 0, 0.6), (0.75, 0, 0.35), 0.1)
    elif v == 2:
        P.box(bm, (0, 0, 1.5), (1.8, 1.8, 0.25))
        for sx in (-1, 1):
            for sy in (-1, 1):
                P.box(bm, (sx * 0.7, sy * 0.7, 0.75), (0.22, 0.22, 1.5))
        P.box(bm, (-0.8, 0, 2.4), (0.25, 1.8, 1.8))
    else:
        P.tube(bm, (0, 0, 0.7), 0.7, 0.52, 1.4, segments=6)


# --------------------------------------------------------------------- kit

# (category, asset key, variants, builder, glass band or None)
KIT = [
    ("Prop", "Barrel", 3, barrel, None),
    # "rope" marks the festoon lanterns' Z band -- see rope_line()
    ("Prop", "Crate", 4, crate, None),
    ("Prop", "RopeCoil", 2, rope_coil, None),
    ("Overhead", "RopeLine", 3, rope_line, "rope"),
    ("Prop", "DryingRack", 3, drying_rack, None),
    ("Prop", "HangingFish", 2, hanging_fish, None),
    ("Prop", "Net", 3, net, None),
    ("Lamp", "LanternPost", 2, lantern_post, "post"),
    ("Overhead", "HangingLantern", 1, hanging_lantern, "hang"),
    ("Prop", "Bollard", 2, bollard, None),
    ("Prop", "MarketStall", 3, market_stall, None),
    ("UI", "NoticeBoard", 1, notice_board, None),
    ("Prop", "Well", 1, well, None),
    ("Prop", "TimberStack", 2, timber_stack, None),
    ("Prop", "Sawhorse", 2, sawhorse, None),
    ("Prop", "HullRepair", 1, hull_repair, None),
    ("Prop", "Rowboat", 1, rowboat, None),
    ("Prop", "Tool", 4, tool, None),
    ("Prop", "GuttingTable", 1, gutting_table, None),
    ("Prop", "SaltVat", 2, salt_vat, None),
    ("UI", "TallyBoard", 2, tally_board, None),
    ("Lore", "TrophyRack", 1, trophy_rack, None),
    ("Lore", "JarShelf", 2, jar_shelf, None),
    ("Lore", "Shrine", 1, shrine, None),
    ("Lore", "FossilArch", 1, fossil_arch, None),
    ("Lamp", "BannerPole", 3, banner_pole, None),
    ("Prop", "Awning", 2, awning, None),
    ("Sub", "CrabPot", 2, crab_pot, None),
    ("Sub", "Buoy", 3, buoy, None),
    ("Sub", "Anchor", 2, anchor, None),
    ("Sub", "Kelp", 4, kelp, None),
    ("Sub", "Coral", 4, coral, None),
    ("Sub", "Ballast", 2, ballast, None),
    ("Nature", "SeaGrass", 3, sea_grass, None),
    ("Nature", "Heather", 3, heather, None),
    ("Nature", "Pine", 2, pine, None),
    ("Prop", "Rock", 5, rock, None),
    ("Prop", "Story", 4, story, None),
    ("Nature", "Gull", 2, gull, None),
]

# whole-object cloth that Phase 7b may only place within the warm ration
WARM_VARIANTS = {("MarketStall", 1), ("MarketStall", 2), ("Awning", 1),
                 ("BannerPole", 1), ("BannerPole", 2)}

OWNED_PREFIXES = ["DD_Prop_", "DD_Nature_", "DD_Sub_", "DD_Lore_",
                  "DD_Overhead_", "DD_Lamp_LanternPost", "DD_Lamp_BannerPole",
                  "DD_UI_NoticeBoard", "DD_UI_TallyBoard"]

COLLECTION_FOR = {"Prop": "Props", "Nature": "Nature", "Sub": "Underwater",
                  "Lore": "Lore", "Overhead": "Overhead", "Lamp": "Props",
                  "UI": "Props"}


def purge():
    # Phase 6's wreck shares the DD_Sub_ prefix but is a unique placed set
    # piece with no kit entry, so it survives. Its buoys do not: this kit owns
    # DD_Sub_Buoy_A/B/C now, and any left over from an older p6 run get cleared
    # here rather than colliding into DD_Sub_Buoy_A.001.
    keep = ("DD_Sub_WreckHull", "DD_Sub_WreckMast")
    doomed = [o for o in bpy.data.objects
              if any(o.name.startswith(p) for p in OWNED_PREFIXES)
              and o.name not in keep]
    meshes = {o.data for o in doomed if o.type == "MESH" and o.data}
    for o in doomed:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in meshes:
        if m.users == 0:
            bpy.data.meshes.remove(m)


def build():
    dd_scene.ensure_collections()
    purge()
    made = []
    index = 0
    for cat, key, variants, fn, glass in KIT:
        for v in range(variants):
            rng = P.seeded(key, v)
            bm = bmesh.new()
            fn(bm, v, rng)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.normal_update()
            name = f"DD_{cat}_{key}_{chr(ord('A') + v)}"
            obj = dd_mesh.bm_to_object(name, bm)

            col = index % GRID_COLS
            row = index // GRID_COLS
            obj.location = (KIT_ORIGIN[0] + (col - (GRID_COLS - 1) / 2.0) * GRID_SPACING,
                            KIT_ORIGIN[1] - row * GRID_SPACING,
                            KIT_ORIGIN[2])
            dd_mesh.shade_flat(obj)
            dd_scene.set_origin_to_base(obj)
            dd_scene.link_to_collection(obj, COLLECTION_FOR[cat])

            if glass == "post":
                h = 11.0 if v == 0 else 7.0
                dd_mood.mark_glass(obj, h - 3.5, h - 1.3)
            elif glass == "hang":
                dd_mood.mark_glass(obj, 0.85, 2.9)
            elif glass == "rope":
                # the festoon lanterns all hang level, so they occupy one band
                # at the bottom of the mesh; the line and hangers sit above it
                dd_mood.mark_glass(obj, -0.01, 1.72)
            if (key, v) in WARM_VARIANTS:
                dd_mood.mark_all(obj, dd_mood.WARM_SLOT)
            if key == "JarShelf":
                dd_mood.mark_all(obj, dd_mood.GLOW_SLOT)
            if key in ("NoticeBoard", "TallyBoard"):
                _uv_front_quad(obj)
            made.append(obj)
            index += 1
    return made


def _uv_front_quad(obj):
    """Give the largest -Y-facing quad a clean 0-1 UV for a Studio SurfaceGui."""
    best, best_area = None, 0.0
    for i, poly in enumerate(obj.data.polygons):
        if len(poly.vertices) != 4:
            continue
        if poly.normal.y < -0.7 and poly.area > best_area:
            best, best_area = i, poly.area
    if best is not None:
        dd_mesh.set_quad_face_uv(obj, face_index=best)


def report():
    rows = []
    over = []
    for cat, key, variants, _fn, _g in KIT:
        for v in range(variants):
            name = f"DD_{cat}_{key}_{chr(ord('A') + v)}"
            o = bpy.data.objects.get(name)
            if not o:
                over.append(f"{name}: MISSING")
                continue
            tris = dd_mesh.triangle_count(o)
            budget = config.PROP_TRI_BUDGET.get(key)
            if budget and tris > budget:
                over.append(f"{name}: {tris} > {budget}")
            rows.append((name, tris, budget))
    total = sum(r[1] for r in rows)
    print(f"kit: {len(rows)} meshes, {total} tris total, "
          f"largest {max(rows, key=lambda r: r[1])[0]} at {max(r[1] for r in rows)}")
    print("over budget:", over or "none")
    return rows


def capture_renders():
    renders_dir = os.path.join(REPO_ROOT, "renders")
    os.makedirs(renders_dir, exist_ok=True)
    dd_palette.apply_debug_colors([o for o in bpy.data.objects if o.name.startswith("DD_")])

    rows = (len(rows_needed()) + GRID_COLS - 1) // GRID_COLS
    cx = KIT_ORIGIN[0]
    cy = KIT_ORIGIN[1] - (rows - 1) * GRID_SPACING / 2.0
    # Frame the grid's real footprint. The sheet is wider than it is tall once
    # the oblique view foreshortens the rows, so ortho_scale keys off the
    # column span and the render is 8:5 rather than square -- sizing off
    # max(cols, rows) left the kit sitting in the middle third of the image.
    extent = GRID_COLS * GRID_SPACING + 1.5 * GRID_SPACING

    cam_data = bpy.data.cameras.get("KitCam") or bpy.data.cameras.new("KitCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = extent
    cam = bpy.data.objects.get("KitCam")
    if cam is None:
        cam = bpy.data.objects.new("KitCam", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    cam.data = cam_data
    cam.location = (cx, cy - extent * 0.50, extent * 0.50)
    direction = mathutils.Vector((cx, cy, 3.0)) - mathutils.Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p7a_kit_sheet.png"),
                            resolution=(2400, 1500))

    # silhouette check: the same grid flat-lit, to judge black-shape readability
    dd_scene.render_to_file(cam, os.path.join(renders_dir, "p7a_kit_silhouette.png"),
                            resolution=(2400, 1500), color_type="SINGLE")


def rows_needed():
    return [v for _c, _k, n, _f, _g in KIT for v in range(n)]


if __name__ == "__main__":
    build()
    report()
    capture_renders()
