"""Generators for the landing-page visuals: a structured finite-element mesh
around the SEM profile, contour results on that mesh, and the profile geometry.
Everything is computed here so the templates stay small. No text in the art."""

import math
from functools import lru_cache

# Three-centred profile (cm): crown R560 @ (0,-40); walls R760 @ (±200,-40); invert R1500 through knees (±480,300).
CROWN_C, CROWN_R = (0.0, -40.0), 560.0
WALL_R = 760.0
KNEE_Y = 300.0


def profile_point(t: float):
    """Point on the excavation boundary for t in [0,1): clockwise from the left knee, over the crown, to the right knee, then along the invert."""
    # arc lengths
    wall_ang = math.asin((KNEE_Y - CROWN_C[1]) / WALL_R)  # ~0.46 rad
    L_wall = WALL_R * wall_ang
    L_crown = math.pi * CROWN_R
    inv_half = math.asin(480 / 1500.0)
    L_inv = 2 * 1500 * inv_half
    total = 2 * L_wall + L_crown + L_inv
    s = (t % 1.0) * total
    if s < L_wall:  # left wall going up: centre (+200,-40), angle from pi-wall_ang → pi
        a = math.pi - wall_ang + (s / L_wall) * wall_ang
        return 200 + WALL_R * math.cos(a), -40 + WALL_R * math.sin(a)
    s -= L_wall
    if s < L_crown:
        a = math.pi + (s / L_crown) * math.pi
        return CROWN_R * math.cos(a), -40 + CROWN_R * math.sin(a)
    s -= L_crown
    if s < L_wall:  # right wall going down: centre (-200,-40), angle 0 → wall_ang
        a = (s / L_wall) * wall_ang
        return -200 + WALL_R * math.cos(a), -40 + WALL_R * math.sin(a)
    s -= L_wall
    # invert from right knee to left knee: centre (0, 300-1421)
    cy = KNEE_Y - math.sqrt(1500**2 - 480**2)
    a0 = math.atan2(KNEE_Y - cy, 480)
    a = a0 + (s / L_inv) * (math.pi - 2 * a0)
    return 1500 * math.cos(a), cy + 1500 * math.sin(a)


def _color(v: float) -> str:
    """0..1 → muted blue → gold contour ramp (subtle, dark-friendly)."""
    stops = [(0.0, (26, 48, 80)), (0.35, (36, 92, 120)), (0.6, (86, 130, 110)), (0.8, (170, 150, 70)), (1.0, (227, 167, 37))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= v <= t1:
            f = (v - t0) / (t1 - t0) if t1 > t0 else 0
            r, g, b = (round(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#e3a725"


@lru_cache(maxsize=4)
def mesh(rings: int = 14, segments: int = 72, growth: float = 1.16):
    """Structured mesh: rings of nodes offset outward from the profile; quads split into triangles.
    Returns dict with triangles [(points, value)], boundary polyline, and nodes count."""
    nodes = []
    for r in range(rings + 1):
        ring = []
        for sgm in range(segments):
            t = sgm / segments
            x, y = profile_point(t)
            # outward normal ≈ direction from a soft centre (0, 60)
            dx, dy = x - 0.0, y - 60.0
            d = math.hypot(dx, dy) or 1.0
            off = (growth**r - 1) * 180.0  # cm
            ring.append((x + dx / d * off, y + dy / d * off))
        nodes.append(ring)
    tris = []
    for r in range(rings):
        for sgm in range(segments):
            a, b = nodes[r][sgm], nodes[r][(sgm + 1) % segments]
            c, d = nodes[r + 1][(sgm + 1) % segments], nodes[r + 1][sgm]
            # "result": radial decay of displacement, a little stronger at the crown
            depth = r / rings
            ang = sgm / segments
            crown = 0.5 * (1 + math.cos((ang - 0.5) * 2 * math.pi))  # 1 at crown (t≈0.5), 0 at invert
            v = (1 - depth) ** 1.6 * (0.55 + 0.45 * crown)
            for pts in ((a, b, c), (a, c, d)):
                cx = sum(p[0] for p in pts) / 3
                cy = sum(p[1] for p in pts) / 3
                if -760 <= cx <= 760 and -800 <= cy <= 540:
                    tris.append({"points": " ".join(f"{x:.0f},{y:.0f}" for x, y in pts), "fill": _color(max(0.0, min(1.0, v)))})
    boundary = " ".join(f"{x:.0f},{y:.0f}" for x, y in nodes[0])
    return {"triangles": tris, "boundary": boundary, "nodes": (rings + 1) * segments}


def contour_bands(levels: int = 8):
    """Smooth contour polylines (iso-displacement) around the profile for the results frame."""
    out = []
    for i in range(1, levels + 1):
        off = (1.16 ** (i * 1.6) - 1) * 180.0
        pts = []
        for sgm in range(96):
            t = sgm / 96
            x, y = profile_point(t)
            dx, dy = x, y - 60.0
            d = math.hypot(dx, dy) or 1.0
            crown = 0.5 * (1 + math.cos((t - 0.5) * 2 * math.pi))
            o = off * (0.75 + 0.35 * crown)
            pts.append(f"{x + dx / d * o:.0f},{y + dy / d * o:.0f}")
        out.append({"points": " ".join(pts), "color": _color(1 - i / (levels + 1))})
    return out
