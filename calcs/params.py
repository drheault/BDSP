"""Shared project parameters.

Tools declare which canonical parameter each input maps to (`Input.param`),
so tunnel geometry, ground and materials are entered once per project and
flow into every tool. Values live on the proposal (`ProjectParams`), and a
user's last inputs per tool are kept (`ToolState`) so nothing is retyped."""

PARAMS = [
    # key, label, unit, group
    ("tunnel_diameter", "Tunnel diameter / span", "m", "Geometry"),
    ("tunnel_height", "Tunnel height", "m", "Geometry"),
    ("cover", "Cover to crown", "m", "Geometry"),
    ("depth_axis", "Depth to axis", "m", "Geometry"),
    ("lining_thickness", "Lining thickness", "mm", "Lining"),
    ("fck", "Concrete / shotcrete fck", "MPa", "Lining"),
    ("fyk", "Steel fyk", "MPa", "Lining"),
    ("fR1k", "Residual strength fR1k", "MPa", "Lining"),
    ("fR3k", "Residual strength fR3k", "MPa", "Lining"),
    ("gamma", "Unit weight γ", "kN/m³", "Ground"),
    ("cu", "Undrained shear strength cu", "kPa", "Ground"),
    ("c", "Effective cohesion c′", "kPa", "Ground"),
    ("phi", "Friction angle φ′", "°", "Ground"),
    ("water_head", "Water head above axis", "m", "Ground"),
    ("K_trough", "Trough width parameter K", "", "Ground"),
    ("volume_loss", "Volume loss", "%", "Construction"),
    ("surcharge", "Surface surcharge", "kPa", "Loads"),
    ("face_pressure", "Face support pressure", "kPa", "Construction"),
    ("beam_span", "Beam / waler span", "m", "Structural"),
    ("section_width", "Section width b", "mm", "Structural"),
    ("section_depth", "Section depth h", "mm", "Structural"),
]
PARAM_KEYS = {p[0] for p in PARAMS}
GROUPS = []
for _, _, _, g in PARAMS:
    if g not in GROUPS:
        GROUPS.append(g)


def grouped(values=None):
    values = values or {}
    return [(g, [(k, l, u, values.get(k)) for k, l, u, gg in PARAMS if gg == g]) for g in GROUPS]
