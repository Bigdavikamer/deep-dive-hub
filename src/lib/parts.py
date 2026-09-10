"""Primitives that append into an existing bmesh.

lib.mesh builds whole objects; these build PARTS of one. A prop is a handful
of closed shells merged into a single mesh, so the kit needs primitives that
add geometry to a bmesh already in progress rather than returning objects.
Phases 5, 6 and 4b each grew a private _add_box for exactly this; Phase 7a
authors 91 meshes, which is well past the point of a shared module.

Every helper writes a CLOSED shell so the merged result stays watertight, and
every one is centre-anchored -- pass the volumetric centre, not the base. One
convention throughout, because mixing base- and centre-anchored primitives is
the easiest way to end up with props that float or sink.

Nothing here uses bpy.ops (CLAUDE.md operating rule 7); bmesh.ops is fine but
these mostly emit vertices directly, which avoids a temporary mesh datablock
per call -- at several parts per prop across 91 props that adds up.
"""
import math
import random


def box(bm, center, size, yaw=0.0):
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    c, s = math.cos(yaw), math.sin(yaw)
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    corners = [(x * c - y * s, x * s + y * c) for x, y in corners]
    lo = [bm.verts.new((cx + x, cy + y, cz - hz)) for x, y in corners]
    hi = [bm.verts.new((cx + x, cy + y, cz + hz)) for x, y in corners]
    bm.verts.ensure_lookup_table()
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def cylinder(bm, center, radius, height, segments=8, yaw=0.0, r_top=None, pitch=0.0):
    """Cylinder, or a truncated cone when r_top differs. r_top=0 gives a point.
    `pitch` tilts it about local Y, which is how leaning props (kelp, the pine
    trunk, a barrel on its side) get their angle baked into vertex data rather
    than into an object transform the export contract forbids."""
    r_top = radius if r_top is None else r_top
    cx, cy, cz = center
    hz = height / 2.0
    cp, sp = math.cos(pitch), math.sin(pitch)

    def place(x, y, z):
        xr, zr = x * cp + z * sp, -x * sp + z * cp
        return (cx + xr, cy + y, cz + zr)

    bot, top = [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments + yaw
        bot.append(bm.verts.new(place(radius * math.cos(a), radius * math.sin(a), -hz)))
        if r_top > 1e-6:
            top.append(bm.verts.new(place(r_top * math.cos(a), r_top * math.sin(a), hz)))
    apex = None if r_top > 1e-6 else bm.verts.new(place(0.0, 0.0, hz))
    cap_b = bm.verts.new(place(0.0, 0.0, -hz))
    cap_t = bm.verts.new(place(0.0, 0.0, hz)) if r_top > 1e-6 else None
    bm.verts.ensure_lookup_table()

    for i in range(segments):
        j = (i + 1) % segments
        if apex is None:
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
            bm.faces.new((cap_t, top[i], top[j]))
        else:
            bm.faces.new((bot[i], bot[j], apex))
        bm.faces.new((cap_b, bot[j], bot[i]))


def tube(bm, center, r_outer, r_inner, height, segments=8):
    """Open-topped vessel: outer wall, inner wall, rim, floor. Closed solid.
    An empty barrel or a brine vat has to read as empty from above, which a
    plain cylinder cannot do and a boolean would cost n-gons."""
    cx, cy, cz = center
    hz = height / 2.0
    floor_z = cz - hz + height * 0.15
    # One ring of inner-floor vertices, shared by the inner wall AND the floor
    # fan. Building them twice at identical coordinates leaves the two surfaces
    # unwelded and the vessel open along its whole inner base -- every prop
    # using tube() came out non-manifold that way.
    ov, iv, rim_o, rim_i = [], [], [], []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        co, si = math.cos(a), math.sin(a)
        ov.append(bm.verts.new((cx + r_outer * co, cy + r_outer * si, cz - hz)))
        rim_o.append(bm.verts.new((cx + r_outer * co, cy + r_outer * si, cz + hz)))
        rim_i.append(bm.verts.new((cx + r_inner * co, cy + r_inner * si, cz + hz)))
        iv.append(bm.verts.new((cx + r_inner * co, cy + r_inner * si, floor_z)))
    base_c = bm.verts.new((cx, cy, cz - hz))
    floor_c = bm.verts.new((cx, cy, floor_z))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((ov[i], ov[j], rim_o[j], rim_o[i]))        # outer wall
        bm.faces.new((rim_o[i], rim_o[j], rim_i[j], rim_i[i]))  # rim
        bm.faces.new((rim_i[i], rim_i[j], iv[j], iv[i]))        # inner wall
        bm.faces.new((floor_c, iv[i], iv[j]))                   # floor
        bm.faces.new((base_c, ov[j], ov[i]))                    # underside


def pyramid(bm, center, base_w, height, yaw=0.0):
    cx, cy, cz = center
    h = base_w / 2.0
    c, s = math.cos(yaw), math.sin(yaw)
    corners = [(-h, -h), (h, -h), (h, h), (-h, h)]
    corners = [(x * c - y * s, x * s + y * c) for x, y in corners]
    lo = [bm.verts.new((cx + x, cy + y, cz - height / 2.0)) for x, y in corners]
    apex = bm.verts.new((cx, cy, cz + height / 2.0))
    bm.verts.ensure_lookup_table()
    bm.faces.new(lo[::-1])
    for i in range(4):
        bm.faces.new((lo[i], lo[(i + 1) % 4], apex))


def sphere(bm, center, radius, segments=8, rings=4, jitter=0.0, rng=None, squash=1.0):
    """Low-poly sphere with optional seeded per-vertex jitter -- the basis for
    every rock, coral head and foliage mass in the kit. Jitter is what stops
    five shore rocks reading as five copies of one ball."""
    cx, cy, cz = center
    rows = []
    for r in range(1, rings):
        phi = math.pi * r / rings
        ring = []
        for i in range(segments):
            th = 2.0 * math.pi * i / segments
            rad = radius * (1.0 + (rng.uniform(-jitter, jitter) if rng and jitter else 0.0))
            ring.append(bm.verts.new((
                cx + rad * math.sin(phi) * math.cos(th),
                cy + rad * math.sin(phi) * math.sin(th),
                cz + rad * math.cos(phi) * squash,
            )))
        rows.append(ring)
    top = bm.verts.new((cx, cy, cz + radius * squash))
    bot = bm.verts.new((cx, cy, cz - radius * squash))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((top, rows[0][i], rows[0][j]))
        bm.faces.new((bot, rows[-1][j], rows[-1][i]))
    for r in range(len(rows) - 1):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((rows[r][i], rows[r][j], rows[r + 1][j], rows[r + 1][i]))


def strut(bm, p0, p1, thickness):
    """Square-section beam between two 3D points -- rails, rope spans, chain
    runs, net strips, anything that connects two places."""
    import mathutils

    a, b = mathutils.Vector(p0), mathutils.Vector(p1)
    d = b - a
    if d.length < 1e-6:
        return
    up = mathutils.Vector((0.0, 0.0, 1.0))
    if abs(d.normalized().dot(up)) > 0.99:
        up = mathutils.Vector((1.0, 0.0, 0.0))
    side = d.cross(up).normalized() * (thickness / 2.0)
    vert = d.cross(side).normalized() * (thickness / 2.0)
    ring_a = [a + side + vert, a - side + vert, a - side - vert, a + side - vert]
    ring_b = [p + d for p in ring_a]
    va = [bm.verts.new(tuple(p)) for p in ring_a]
    vb = [bm.verts.new(tuple(p)) for p in ring_b]
    bm.verts.ensure_lookup_table()
    bm.faces.new(va[::-1])
    bm.faces.new(vb)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((va[i], va[j], vb[j], vb[i]))


def blade(bm, base, height, width, bend, segments=3, yaw=0.0, thickness=0.16):
    """Tapering, curving frond -- kelp, sea grass. Curves along +X after `yaw`,
    tapering to a tip, so a cluster of them reads as growth rather than spikes."""
    c, s = math.cos(yaw), math.sin(yaw)
    bx, by, bz = base
    prev = None
    for i in range(segments + 1):
        t = i / segments
        w = width * (1.0 - 0.75 * t) / 2.0
        off = bend * t * t
        x, y = bx + (off * c - 0.0 * s), by + (off * s)
        z = bz + height * t
        cur = (x, y, z, w)
        if prev is not None:
            px, py, pz, pw = prev
            lo = [bm.verts.new((px - pw * s, py + pw * c, pz)),
                  bm.verts.new((px + pw * s, py - pw * c, pz)),
                  bm.verts.new((px + pw * s + thickness * c, py - pw * c + thickness * s, pz)),
                  bm.verts.new((px - pw * s + thickness * c, py + pw * c + thickness * s, pz))]
            hi = [bm.verts.new((x - w * s, y + w * c, z)),
                  bm.verts.new((x + w * s, y - w * c, z)),
                  bm.verts.new((x + w * s + thickness * c, y - w * c + thickness * s, z)),
                  bm.verts.new((x - w * s + thickness * c, y + w * c + thickness * s, z))]
            bm.verts.ensure_lookup_table()
            bm.faces.new(lo[::-1])
            bm.faces.new(hi)
            for k in range(4):
                m = (k + 1) % 4
                bm.faces.new((lo[k], lo[m], hi[m], hi[k]))
        prev = cur


def seeded(*key):
    """Deterministic RNG for a kit asset, so re-running the build is identical."""
    import config
    return random.Random(hash((config.SCATTER_SEED,) + key) & 0xFFFFFFFF)
