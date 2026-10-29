"""Built-in engineering calculators.

Each engine declares its inputs (name, label, unit, default, help) and a
`run(values) -> dict` returning `results` (label/value/unit rows), `checks`
(pass/fail statements), optional `chart` (SVG string) and `notes` (method and
references). They are deliberately transparent: every formula is shown so a
reviewer can check it. They are design aids, not a substitute for a checked
calculation package.
"""

import math
from dataclasses import dataclass, field


@dataclass
class Input:
    name: str
    label: str
    unit: str = ""
    default: float = 0.0
    help: str = ""
    choices: list = field(default_factory=list)
    step: float = 0.1


def _svg_chart(series, xlabel, ylabel, width=640, height=360, points=None, xlim=None, ylim=None, title=""):
    """Tiny SVG line-chart helper: series = [(label, [(x,y),...], color)], points = [(x,y,label,color)]."""
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 50
    xs = [x for _, pts, _ in series for x, _ in pts] + [p[0] for p in (points or [])]
    ys = [y for _, pts, _ in series for _, y in pts] + [p[1] for p in (points or [])]
    if not xs:
        return ""
    x0, x1 = xlim or (min(xs), max(xs))
    y0, y1 = ylim or (min(0, min(ys)), max(ys))
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1
    W, H = width - pad_l - pad_r, height - pad_t - pad_b

    def sx(x):
        return pad_l + (x - x0) / (x1 - x0) * W

    def sy(y):
        return pad_t + H - (y - y0) / (y1 - y0) * H

    out = [f'<svg class="calc-chart" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">']
    if title:
        out.append(f'<text x="{pad_l}" y="18" class="ct">{title}</text>')
    # grid
    for i in range(6):
        gx = x0 + (x1 - x0) * i / 5
        gy = y0 + (y1 - y0) * i / 5
        out.append(f'<line x1="{sx(gx):.1f}" y1="{pad_t}" x2="{sx(gx):.1f}" y2="{pad_t+H}" class="cg"/><text x="{sx(gx):.1f}" y="{pad_t+H+16}" class="cl" text-anchor="middle">{gx:.3g}</text>')
        out.append(f'<line x1="{pad_l}" y1="{sy(gy):.1f}" x2="{pad_l+W}" y2="{sy(gy):.1f}" class="cg"/><text x="{pad_l-6}" y="{sy(gy)+4:.1f}" class="cl" text-anchor="end">{gy:.3g}</text>')
    out.append(f'<rect x="{pad_l}" y="{pad_t}" width="{W}" height="{H}" class="cf"/>')
    for label, pts, color in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"/>')
    for x, y, label, color in points or []:
        out.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="5" fill="{color}"/><text x="{sx(x)+8:.1f}" y="{sy(y)-8:.1f}" class="cl">{label}</text>')
    lx = pad_l
    for label, _, color in series:
        out.append(f'<rect x="{lx}" y="{height-14}" width="14" height="4" fill="{color}"/><text x="{lx+18}" y="{height-9}" class="cl">{label}</text>')
        lx += 18 + 7 * len(label) + 20
    out.append(f'<text x="{pad_l + W/2:.1f}" y="{height-28}" class="cl" text-anchor="middle">{xlabel}</text>')
    out.append(f'<text transform="translate(14 {pad_t + H/2:.1f}) rotate(-90)" class="cl" text-anchor="middle">{ylabel}</text></svg>')
    return "".join(out)


# ---------------------------------------------------------------------------
class FaceStability:
    key = "face_stability"
    name = "Tunnel face stability"
    category = "Tunnel design"
    summary = "Undrained stability ratio (Broms & Bennermark) and drained minimum support pressure (Vermeer, Ruse & Marcher)."
    description = (
        "Undrained (clays): stability number N = (σs + γ·(C + D/2) − σT) / cu. Face is stable for N below ~6 (Broms & Bennermark 1967); "
        "many designers limit N to 4–5 for serviceability and to control volume loss.\n\n"
        "Drained (sands, gravels): minimum effective face support pressure from the Vermeer, Ruse & Marcher (2002) fit to finite-element "
        "collapse results: p_f = −c′/tanφ′ + γ′·D·(1/(9·tanφ′) − 0.05), valid for φ′ ≥ 20° and C/D ≥ 1. Water pressure at the axis is added "
        "separately for a closed-face TBM. A factor of safety is applied on the support pressure.\n\n"
        "Philosophy: the face is the most sensitive element of a soft-ground drive. Use these closed-form checks for screening and "
        "sensitivity; confirm critical faces with limit-equilibrium wedge models (Anagnostou & Kovári) or 3D FE, and tie the chosen "
        "pressure window to the monitoring trigger levels."
    )
    inputs = [
        Input("D", "Tunnel diameter D", "m", 6.5), Input("C", "Cover to crown C", "m", 15),
        Input("gamma", "Unit weight γ (bulk)", "kN/m³", 19), Input("sigma_s", "Surface surcharge σs", "kPa", 20),
        Input("cu", "Undrained shear strength cu (clay)", "kPa", 60), Input("c", "Effective cohesion c′ (drained)", "kPa", 2),
        Input("phi", "Effective friction angle φ′", "°", 32), Input("hw", "Water head above axis (0 if dry)", "m", 8),
        Input("sigma_T", "Applied face support pressure σT (total, at axis)", "kPa", 150), Input("fos", "Required factor of safety on support", "", 1.5, step=0.05),
    ]

    def run(self, v):
        D, C, g, ss, cu, c, phi, hw, sT, fos = (v[k] for k in ("D", "C", "gamma", "sigma_s", "cu", "c", "phi", "hw", "sigma_T", "fos"))
        z_axis = C + D / 2
        N = (ss + g * z_axis - sT) / cu if cu > 0 else float("inf")
        sT_req_undrained = ss + g * z_axis - 4.0 * cu  # for N = 4 target
        tan = math.tan(math.radians(phi)) if phi > 0 else 1e-9
        g_eff = g - 9.81 if hw > 0 else g
        pf = -c / tan + g_eff * D * (1 / (9 * tan) - 0.05)
        pf = max(pf, 0)
        u = 9.81 * hw
        p_total_req = pf * fos + u
        phi_ok = phi >= 20 and C / D >= 1
        results = [
            ("Depth to axis", f"{z_axis:.2f}", "m"), ("Total vertical stress at axis", f"{ss + g * z_axis:.1f}", "kPa"),
            ("Undrained stability number N", f"{N:.2f}", "—"), ("Support for N = 4 (undrained)", f"{max(sT_req_undrained, 0):.0f}", "kPa"),
            ("Drained effective support p_f (collapse)", f"{pf:.1f}", "kPa"), ("Water pressure at axis u", f"{u:.1f}", "kPa"),
            (f"Drained total support required (FoS {fos:g})", f"{p_total_req:.0f}", "kPa"),
        ]
        checks = [
            ("Undrained: N ≤ 4 (comfortable)", N <= 4), ("Undrained: N ≤ 6 (stable)", N <= 6),
            ("Drained: σT ≥ FoS·p_f + u", sT >= p_total_req), ("Vermeer fit valid (φ′ ≥ 20°, C/D ≥ 1)", phi_ok),
        ]
        pts = [(x, (ss + g * z_axis - x) / cu if cu > 0 else 0) for x in range(0, int(ss + g * z_axis) + 1, max(1, int((ss + g * z_axis) / 40)))]
        chart = _svg_chart([("N vs support pressure", pts, "#0f3d5e")], "Face support σT (kPa)", "Stability number N", points=[(sT, N, "current", "#e07a1f")], ylim=(0, max(8, N + 1)), title="Undrained stability")
        return {"results": results, "checks": checks, "chart": chart}


class SettlementDamage:
    key = "settlement_damage"
    name = "Tunnel settlement & building damage"
    category = "Ground movements"
    summary = "Peck/O'Reilly & New Gaussian trough, volume loss, and Burland limiting tensile strain damage category for a building."
    description = (
        "Greenfield settlement S(y) = Smax·exp(−y²/2i²), i = K·z0, Smax = Vl·π·D²/4 / (i·√(2π)). Horizontal displacement from the "
        "O'Reilly & New assumption of vectors pointing to the axis: u(y) = y·S(y)/z0.\n\n"
        "Building damage follows the Burland & Wroth / Burland (1995) deep-beam approach: the building span over the trough is "
        "divided at the inflection point into hogging and sagging zones; deflection ratio Δ/L and average horizontal strain εh give "
        "the limiting tensile strain ε_lim (bending and diagonal shear modes, E/G = 2.6, neutral axis at the bottom for hogging). "
        "Categories: 0–0.05 % negligible, 0.05–0.075 % very slight, 0.075–0.15 % slight, 0.15–0.3 % moderate, >0.3 % severe.\n\n"
        "Philosophy: Stage 1 screening on greenfield; Stage 2 with building stiffness ignored (this tool); Stage 3 soil–structure "
        "interaction only where Stage 2 flags moderate or worse. Volume loss is the design variable you control through face "
        "pressure, grouting and advance rate — tie it to the Face stability tool and to monitoring triggers."
    )
    inputs = [
        Input("D", "Tunnel diameter D", "m", 6.5), Input("z0", "Depth to axis z0", "m", 18), Input("Vl", "Volume loss Vl", "%", 1.0, step=0.05),
        Input("K", "Trough width parameter K", "", 0.5, help="0.5 clays, 0.25–0.35 sands", step=0.05),
        Input("y1", "Building near edge offset from axis y1", "m", 4), Input("y2", "Building far edge offset y2", "m", 24),
        Input("H", "Building height (to eaves)", "m", 9), Input("EG", "E/G ratio", "", 2.6, step=0.1),
    ]

    def run(self, v):
        D, z0, Vl, K, y1, y2, H, EG = (v[k] for k in ("D", "z0", "Vl", "K", "y1", "y2", "H", "EG"))
        i = K * z0
        Smax = (Vl / 100) * math.pi * D**2 / 4 / (i * math.sqrt(2 * math.pi))

        def S(y):
            return Smax * math.exp(-(y**2) / (2 * i**2))

        def u(y):
            return y * S(y) / z0

        y1, y2 = sorted((abs(y1), abs(y2)))
        L = max(y2 - y1, 0.1)
        # split at inflection point i if inside the building
        segments = []
        if y1 < i < y2:
            segments = [("sagging", y1, i), ("hogging", i, y2)]
        elif y2 <= i:
            segments = [("sagging", y1, y2)]
        else:
            segments = [("hogging", y1, y2)]
        rows, worst = [], (0, "negligible")
        cats = [(0.05, "negligible"), (0.075, "very slight"), (0.15, "slight"), (0.3, "moderate"), (9e9, "severe to very severe")]
        for mode, a, b in segments:
            Ls = max(b - a, 0.1)
            Sa, Sb, Sm = S(a), S(b), S((a + b) / 2)
            chord = (Sa + Sb) / 2
            delta = abs(Sm - chord)
            DR = delta / Ls
            eh = (u(b) - u(a)) / Ls  # tensile positive away from axis
            eh = max(eh, 0)
            t = H  # neutral axis at bottom for hogging (t = H), mid for sagging (t = H/2) → use Burland: hogging t=H, sagging t=H/2
            if mode == "sagging":
                t = H / 2
            LH = Ls / H
            # Burland & Wroth: Δ/L = ε_b (L/(12 t) + 3 I E/(2 t L H G))... use closed form with I = H^3/12 per unit thickness
            I = H**3 / 12
            eb_coef = (Ls / (12 * t) + 3 * I * EG / (2 * t * Ls * H))
            ed_coef = (1 + H * Ls**2 / (18 * I * EG))
            eb = DR / eb_coef
            ed = DR / ed_coef
            # combine with horizontal strain (Burland 1995)
            eb_tot = eb + eh
            ed_tot = eh * (1 - 0.3) / 2 + math.sqrt((eh * (1 + 0.3) / 2) ** 2 + ed**2)
            elim = max(eb_tot, ed_tot) * 100  # percent
            cat = next(name for lim, name in cats if elim < lim)
            rows.append((mode, a, b, DR * 100, eh * 100, elim, cat))
            if elim > worst[0]:
                worst = (elim, cat)
        results = [("Trough width i", f"{i:.2f}", "m"), ("Max settlement Smax", f"{Smax*1000:.1f}", "mm"), ("Settlement at y1 / y2", f"{S(y1)*1000:.1f} / {S(y2)*1000:.1f}", "mm")]
        for mode, a, b, DR, eh, elim, cat in rows:
            results += [(f"{mode.title()} zone {a:.1f}–{b:.1f} m: Δ/L", f"{DR:.3f}", "%"), (f"{mode.title()} zone: εh", f"{eh:.3f}", "%"), (f"{mode.title()} zone: ε_lim → category", f"{elim:.3f} % → {cat}", "")]
        checks = [("Damage category ≤ slight (ε_lim < 0.15 %)", worst[0] < 0.15), ("Smax ≤ 25 mm", Smax <= 0.025)]
        pts = [(y, -S(y) * 1000) for y in [x * 0.5 for x in range(0, int(3 * i / 0.5) + 2)]]
        chart = _svg_chart([("Settlement (mm)", pts, "#0f3d5e")], "Offset from tunnel axis y (m)", "Settlement (mm, downward negative)", points=[(y1, -S(y1) * 1000, "y1", "#e07a1f"), (y2, -S(y2) * 1000, "y2", "#e07a1f")], title="Greenfield trough")
        return {"results": results, "checks": checks, "chart": chart, "headline": f"Worst zone: {worst[1]} ({worst[0]:.3f} %)"}


class BeamAnalysis:
    key = "beam"
    name = "Beam analysis"
    category = "Structural"
    summary = "Moments, shears and deflections for simply supported, cantilever and fixed-fixed beams under UDL and a point load."
    description = "Closed-form elastic beam formulas (Roark). Combined loading is superposed. Deflection uses E·I. Use for lining segments, walers, struts and temporary works screening."
    inputs = [
        Input("support", "Support condition", "", 0, choices=[(0, "Simply supported"), (1, "Cantilever (fixed at left)"), (2, "Fixed both ends")]),
        Input("L", "Span L", "m", 6), Input("w", "Uniform load w", "kN/m", 25), Input("P", "Point load P", "kN", 50), Input("a", "Point load position from left a", "m", 3),
        Input("E", "Elastic modulus E", "GPa", 30), Input("I", "Second moment of area I", "cm⁴", 50000),
    ]

    def run(self, v):
        sup, L, w, P, a, E, I = int(v["support"]), v["L"], v["w"], v["P"], v["a"], v["E"] * 1e6, v["I"] * 1e-8  # kN/m², m⁴
        a = min(max(a, 0), L)
        b = L - a
        n = 60
        xs = [L * k / n for k in range(n + 1)]
        M, V, d = [], [], []
        for x in xs:
            if sup == 0:
                m = w * x * (L - x) / 2 + (P * b * x / L if x <= a else P * a * (L - x) / L)
                s = w * (L / 2 - x) + (P * b / L if x < a else -P * a / L)
                dw = w * x * (L**3 - 2 * L * x**2 + x**3) / (24 * E * I)
                dp = (P * b * x * (L**2 - b**2 - x**2) / (6 * L * E * I)) if x <= a else (P * a * (L - x) * (2 * L * x - x**2 - a**2) / (6 * L * E * I))
                dd = dw + dp
            elif sup == 1:
                m = -(w * (L - x) ** 2 / 2) - (P * (a - x) if x <= a else 0)
                s = w * (L - x) + (P if x < a else 0)
                dw = w * x**2 * (6 * L**2 - 4 * L * x + x**2) / (24 * E * I)
                dp = (P * x**2 * (3 * a - x) / (6 * E * I)) if x <= a else (P * a**2 * (3 * x - a) / (6 * E * I))
                dd = dw + dp
            else:
                m = w * (6 * L * x - L**2 - 6 * x**2) / 12
                if x <= a:
                    m += P * b**2 * (a * L - x * (L + 2 * a)) / L**3 * -1 + P * b**2 * a / L**2 - P * b**2 * (L + 2 * a) * x / L**3 * 0  # simplified below
                # fixed-fixed point load exact:
                Ma = -P * a * b**2 / L**2
                Mb = -P * a**2 * b / L**2
                Ra = P * b**2 * (3 * a + b) / L**3
                mp = Ma + Ra * x - (P * (x - a) if x > a else 0)
                m = w * (6 * L * x - L**2 - 6 * x**2) / 12 + mp
                s = w * (L / 2 - x) + Ra - (P if x > a else 0)
                dw = w * x**2 * (L - x) ** 2 / (24 * E * I)
                dp = (P * b**2 * x**2 * (3 * a * L - 3 * a * x - b * x) / (6 * E * I * L**3)) if x <= a else (P * a**2 * (L - x) ** 2 * (3 * b * L - 3 * b * (L - x) - a * (L - x)) / (6 * E * I * L**3))
                dd = dw + dp
            M.append((x, m))
            V.append((x, s))
            d.append((x, dd * 1000))
        Mmax = max(M, key=lambda p: abs(p[1]))
        Vmax = max(V, key=lambda p: abs(p[1]))
        dmax = max(d, key=lambda p: abs(p[1]))
        results = [("Max |M|", f"{Mmax[1]:.1f} at x = {Mmax[0]:.2f} m", "kNm"), ("Max |V|", f"{Vmax[1]:.1f} at x = {Vmax[0]:.2f} m", "kN"), ("Max deflection", f"{dmax[1]:.2f} at x = {dmax[0]:.2f} m", "mm"), ("Span / deflection", f"{(L*1000/abs(dmax[1])) if dmax[1] else float('inf'):.0f}", "")]
        checks = [("Deflection ≤ L/250", abs(dmax[1]) <= L * 1000 / 250), ("Deflection ≤ L/360", abs(dmax[1]) <= L * 1000 / 360)]
        chart = _svg_chart([("Moment (kNm)", M, "#0f3d5e"), ("Shear (kN)", V, "#e07a1f")], "x (m)", "kNm / kN", title="Bending moment & shear")
        chart2 = _svg_chart([("Deflection (mm)", d, "#3a9d6a")], "x (m)", "mm", title="Deflection")
        return {"results": results, "checks": checks, "chart": chart + chart2}


class RCSection:
    key = "rc_section"
    name = "Reinforced concrete section"
    category = "Structural"
    summary = "Singly reinforced rectangular section: moment capacity, required steel for a target moment, ductility and minimum steel checks."
    description = (
        "Rectangular stress block to Eurocode 2 (λ = 0.8, η = 1.0 for fck ≤ 50 MPa), fcd = αcc·fck/γc with αcc = 0.85, γc = 1.5, fyd = fyk/1.15. "
        "Capacity: x = As·fyd / (λ·η·fcd·b); M_Rd = As·fyd·(d − λx/2). Required steel for M_Ed from K = M_Ed/(b·d²·fck) and z = d·(0.5 + √(0.25 − K/1.134)) ≤ 0.95d. "
        "Ductility limit x/d ≤ 0.45; minimum steel 0.26·fctm/fyk·b·d ≥ 0.0013·b·d. Swap the partial factors for CSA A23.3 or ACI 318 if the project requires."
    )
    inputs = [
        Input("b", "Width b", "mm", 1000, step=1), Input("h", "Depth h", "mm", 400, step=1), Input("cover", "Cover to bar centre", "mm", 50, step=1),
        Input("fck", "Concrete fck", "MPa", 35, step=1), Input("fyk", "Steel fyk", "MPa", 500, step=1),
        Input("As", "Tension steel As (provided)", "mm²", 1570, step=1), Input("MEd", "Design moment M_Ed", "kNm", 180, step=1),
    ]

    def run(self, v):
        b, h, cov, fck, fyk, As, MEd = (v[k] for k in ("b", "h", "cover", "fck", "fyk", "As", "MEd"))
        d = h - cov
        fcd, fyd = 0.85 * fck / 1.5, fyk / 1.15
        lam, eta = 0.8, 1.0
        x = As * fyd / (lam * eta * fcd * b)
        MRd = As * fyd * (d - lam * x / 2) / 1e6
        K = MEd * 1e6 / (b * d**2 * fck)
        z = min(d * (0.5 + math.sqrt(max(0.25 - K / 1.134, 0))), 0.95 * d)
        As_req = MEd * 1e6 / (fyd * z)
        fctm = 0.3 * fck ** (2 / 3) if fck <= 50 else 2.12 * math.log(1 + (fck + 8) / 10)
        As_min = max(0.26 * fctm / fyk * b * d, 0.0013 * b * d)
        results = [("Effective depth d", f"{d:.0f}", "mm"), ("fcd / fyd", f"{fcd:.1f} / {fyd:.0f}", "MPa"), ("Neutral axis x (provided As)", f"{x:.1f} (x/d = {x/d:.3f})", "mm"),
                   ("Moment capacity M_Rd", f"{MRd:.1f}", "kNm"), ("Utilisation M_Ed / M_Rd", f"{MEd/MRd if MRd else float('inf'):.2f}", ""),
                   ("K = M_Ed/(b d² fck)", f"{K:.3f}", ""), ("Lever arm z", f"{z:.0f}", "mm"), ("Required As for M_Ed", f"{As_req:.0f}", "mm²"), ("Minimum As", f"{As_min:.0f}", "mm²")]
        checks = [("M_Rd ≥ M_Ed", MRd >= MEd), ("Ductility x/d ≤ 0.45", x / d <= 0.45), ("K ≤ 0.167 (no compression steel)", K <= 0.167), ("As ≥ As,min", As >= As_min), ("As ≥ As,req", As >= As_req)]
        return {"results": results, "checks": checks, "headline": f"M_Rd = {MRd:.0f} kNm vs M_Ed = {MEd:.0f} kNm"}


class CapacityCurve:
    key = "capacity_curve"
    name = "Capacity limit curves (M–N interaction)"
    category = "Structural"
    summary = "Axial force–moment interaction envelope for a rectangular lining section (plain or symmetrically reinforced) with the applied load points."
    description = (
        "Strain-compatibility interaction diagram: for neutral-axis depths from the fully compressed section to pure bending, the concrete "
        "block (λ = 0.8, fcd = 0.85·fck/1.5, εcu = 0.0035) and steel layers (bilinear, fyd = fyk/1.15, Es = 200 GPa) are integrated for N and M. "
        "For plain concrete (As = 0) the curve collapses to the familiar parabola used for SEM shotcrete linings; the point (N, M) from the "
        "bedded-beam or FE model must fall inside. Enter up to three load combinations.\n\n"
        "Philosophy: in a lining the thrust is the friend of the section — compare load points against the envelope rather than against a "
        "bare bending capacity, and check both the early-age (low fck) and long-term curves."
    )
    inputs = [
        Input("b", "Width b", "mm", 1000, step=1), Input("h", "Thickness h", "mm", 300, step=1), Input("fck", "Concrete fck", "MPa", 30, step=1),
        Input("As", "Steel per face As (0 for plain)", "mm²/face", 0, step=1), Input("cover", "Cover to bar centre", "mm", 50, step=1), Input("fyk", "Steel fyk", "MPa", 500, step=1),
        Input("N1", "Load point 1: N", "kN", 1200, step=1), Input("M1", "Load point 1: M", "kNm", 60, step=1),
        Input("N2", "Load point 2: N", "kN", 600, step=1), Input("M2", "Load point 2: M", "kNm", 90, step=1),
        Input("N3", "Load point 3: N", "kN", 0, step=1), Input("M3", "Load point 3: M", "kNm", 0, step=1),
    ]

    def run(self, v):
        b, h, fck, As, cov, fyk = (v[k] for k in ("b", "h", "fck", "As", "cover", "fyk"))
        fcd, fyd, Es, ecu = 0.85 * fck / 1.5, fyk / 1.15, 200000, 0.0035
        lam = 0.8
        pts = []
        layers = [(cov, As), (h - cov, As)] if As > 0 else []
        for k in range(0, 121):
            x = h * 3 * (120 - k) / 120 + 1e-6  # from deep compression (x = 3h) to tiny
            a = min(lam * x, h)
            Nc = fcd * b * a / 1000
            Mc = Nc * (h / 2 - a / 2) / 1000
            N, M = Nc, Mc
            for yi, Asi in layers:
                eps = ecu * (x - yi) / x
                fs = max(-fyd, min(fyd, Es * eps))
                Fs = fs * Asi / 1000
                N += Fs
                M += Fs * (h / 2 - yi) / 1000
            pts.append((N, M))
        # pure tension end for reinforced
        if As > 0:
            pts.append((-2 * As * fyd / 1000, 0))
        curve = [(n, abs(m)) for n, m in pts]
        loads = [(v[f"N{i}"], v[f"M{i}"], f"LC{i}", "#e07a1f") for i in (1, 2, 3) if v[f"N{i}"] or v[f"M{i}"]]

        def inside(N, M):
            # capacity moment at this N by linear interpolation along the curve (sorted by N)
            srt = sorted(curve)
            if N < srt[0][0] or N > srt[-1][0]:
                return False, 0
            for (n1, m1), (n2, m2) in zip(srt, srt[1:]):
                if n1 <= N <= n2:
                    mc = m1 + (m2 - m1) * (N - n1) / (n2 - n1) if n2 != n1 else m1
                    return abs(M) <= mc, mc
            return False, 0

        checks, results = [], [("Pure compression N_max", f"{max(n for n, _ in curve):.0f}", "kN"), ("Max moment on envelope", f"{max(m for _, m in curve):.1f}", "kNm")]
        for N, M, lab, _ in loads:
            ok, mc = inside(N, M)
            results.append((f"{lab}: capacity M at N = {N:.0f} kN", f"{mc:.1f}", "kNm"))
            checks.append((f"{lab} (N = {N:.0f}, M = {M:.0f}) inside envelope", ok))
        chart = _svg_chart([("Capacity envelope", sorted(curve), "#0f3d5e")], "Axial force N (kN, compression +)", "Moment M (kNm)", points=loads, title="M–N interaction")
        return {"results": results, "checks": checks, "chart": chart}


class FRSDesign:
    key = "frs"
    name = "Fibre-reinforced shotcrete lining"
    category = "Tunnel design"
    summary = "Residual strength classification (fib Model Code 2010), post-crack moment capacity of a shotcrete section, and the design philosophy for fibre-only linings."
    description = (
        "From beam-test residual strengths fR1k and fR3k (EN 14651): class = fR1k ‘letter’ with fR3k/fR1k ratio (a: 0.5–0.7, b: 0.7–0.9, c: 0.9–1.1, d: 1.1–1.3, e: ≥1.3). "
        "Structural fibre use requires fR1k/fLk > 0.4 and fR3k/fR1k > 0.5. Ultimate residual tensile strength (rigid-plastic model) f_Ftu = fR3k/3; design f_Ftud = f_Ftu/γF (γF = 1.5). "
        "Rigid-plastic post-crack moment per metre: M_Rd ≈ f_Ftud · b · h² / 2 … applying the Model Code stress block gives M_Rd = f_Ftud·b·h²/2 for a fully cracked section "
        "(conservative, no axial force). With thrust N the capacity increases; use the Capacity curve tool with an equivalent tensile strength.\n\n"
        "Philosophy: fibres replace mesh for crack control and residual capacity in SEM linings, cross-passages and shafts; they do not replace bars where "
        "flexure dominates at low thrust (portals, openings, large spans). Specify by performance (fR1k, fR3k, energy from round-panel tests EN 14488-5) rather than "
        "by dosage, and verify on site with early-age panels."
    )
    inputs = [
        Input("fLk", "Limit of proportionality fLk", "MPa", 4.5, step=0.1), Input("fR1k", "Residual strength fR1k (CMOD 0.5 mm)", "MPa", 2.5, step=0.1), Input("fR3k", "Residual strength fR3k (CMOD 2.5 mm)", "MPa", 2.0, step=0.1),
        Input("h", "Lining thickness h", "mm", 250, step=5), Input("b", "Width considered b", "mm", 1000, step=1), Input("gammaF", "Partial factor γF", "", 1.5, step=0.05),
        Input("MEd", "Design moment M_Ed (per metre)", "kNm/m", 25, step=1), Input("energy", "Round panel energy at 40 mm (EN 14488-5)", "J", 800, step=10),
    ]

    def run(self, v):
        fLk, fR1k, fR3k, h, b, gF, MEd, energy = (v[k] for k in ("fLk", "fR1k", "fR3k", "h", "b", "gammaF", "MEd", "energy"))
        ratio = fR3k / fR1k if fR1k else 0
        letter = "a" if ratio < 0.7 else "b" if ratio < 0.9 else "c" if ratio < 1.1 else "d" if ratio < 1.3 else "e"
        f_Ftu = fR3k / 3
        f_Ftud = f_Ftu / gF
        MRd = f_Ftud * b * h**2 / 2 / 1e6
        results = [("fR3k / fR1k", f"{ratio:.2f}", ""), ("Model Code class", f"{fR1k:g}{letter}", ""), ("fR1k / fLk", f"{fR1k/fLk if fLk else 0:.2f}", ""), ("f_Ftu = fR3k/3", f"{f_Ftu:.2f}", "MPa"), ("f_Ftud", f"{f_Ftud:.2f}", "MPa"), ("Post-crack M_Rd (no thrust)", f"{MRd:.1f}", "kNm/m"), ("Utilisation", f"{MEd/MRd if MRd else float('inf'):.2f}", "")]
        checks = [("Structural use: fR1k/fLk > 0.4", fR1k / fLk > 0.4 if fLk else False), ("Structural use: fR3k/fR1k > 0.5", ratio > 0.5), ("M_Rd ≥ M_Ed", MRd >= MEd), ("Panel energy ≥ 700 J (typical temporary lining)", energy >= 700), ("Panel energy ≥ 1000 J (permanent / squeezing)", energy >= 1000)]
        return {"results": results, "checks": checks, "headline": f"Class {fR1k:g}{letter} · M_Rd = {MRd:.1f} kNm/m"}


REGISTRY = {e.key: e() for e in (FaceStability, SettlementDamage, BeamAnalysis, RCSection, CapacityCurve, FRSDesign)}
