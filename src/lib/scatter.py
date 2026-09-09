"""Seeded randomized placement: Poisson-disc sampling within zone polygons,
rotation/scale jitter, and linked-instance placement.

All randomness must flow through a random.Random(config.SCATTER_SEED)
instance so results are reproducible run-to-run (idempotency rule).
"""
import math
import random

import bpy


def make_rng(seed):
    return random.Random(seed)


def point_in_polygon(x, y, poly):
    """Ray-casting point-in-polygon test. `poly` is a list of (x, y)."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_intersect = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def polygon_bounds(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def poisson_disc_sample(poly, min_spacing, target_count, rng, exclude_polys=None, max_attempts=30):
    """Bridson-style Poisson-disc sampling constrained to `poly`, minus any
    polygons in `exclude_polys` (traffic lanes + LANE_CLEARANCE). Returns up
    to `target_count` (x, y) points, each >= min_spacing apart."""
    exclude_polys = exclude_polys or []
    min_x, min_y, max_x, max_y = polygon_bounds(poly)
    cell = min_spacing / math.sqrt(2)

    def valid(pt):
        x, y = pt
        if not point_in_polygon(x, y, poly):
            return False
        return not any(point_in_polygon(x, y, ex) for ex in exclude_polys)

    grid = {}

    def grid_key(pt):
        return (int(pt[0] // cell), int(pt[1] // cell))

    def fits(pt):
        gx, gy = grid_key(pt)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                for other in grid.get((gx + dx, gy + dy), []):
                    if math.dist(pt, other) < min_spacing:
                        return False
        return True

    points = []
    active = []
    for _ in range(60):
        seed_pt = (rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))
        if valid(seed_pt):
            points.append(seed_pt)
            active.append(seed_pt)
            grid.setdefault(grid_key(seed_pt), []).append(seed_pt)
            break

    while active and len(points) < target_count:
        idx = rng.randrange(len(active))
        base = active[idx]
        placed = False
        for _ in range(max_attempts):
            ang = rng.uniform(0.0, 2.0 * math.pi)
            rad = rng.uniform(min_spacing, 2.0 * min_spacing)
            cand = (base[0] + rad * math.cos(ang), base[1] + rad * math.sin(ang))
            if valid(cand) and fits(cand):
                points.append(cand)
                active.append(cand)
                grid.setdefault(grid_key(cand), []).append(cand)
                placed = True
                if len(points) >= target_count:
                    break
        if not placed:
            active.pop(idx)

    return points


def jitter_yaw_scale(rng, rot_jitter_deg, scale_jitter_frac, base_yaw_deg=0.0):
    """Seeded (yaw_radians, uniform_scale) jitter per prop instance."""
    yaw = math.radians(base_yaw_deg + rng.uniform(-rot_jitter_deg, rot_jitter_deg))
    scale = 1.0 + rng.uniform(-scale_jitter_frac, scale_jitter_frac)
    return yaw, scale


def new_linked_instance(name, source_obj, location, yaw=0.0, scale=1.0, collection=None):
    """Place an object that shares source_obj's mesh datablock -- never
    copies it. This is the ~45-meshes-to-~450-instances contract; validate.py
    checks (#17) that every prop-library mesh has more than one user."""
    obj = bpy.data.objects.new(name, source_obj.data)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, yaw)
    obj.scale = (scale, scale, scale)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj
