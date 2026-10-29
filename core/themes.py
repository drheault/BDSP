"""Built-in appearance presets. Each preset is a dict of CSS custom properties
(without the leading `--`) plus a few layout switches. Stored themes are the
same shape, so a preset can be copied, edited, exported and re-imported."""

PRESETS = {
    "classic": {
        "name": "Classic navy",
        "description": "Dark navy sidebar, orange accent. Confident and traditional.",
        "vars": {
            "font": "Inter, 'Segoe UI', system-ui, -apple-system, Roboto, 'Helvetica Neue', Arial, sans-serif",
            "font-size": "16px", "radius": "10px",
            "navy": "#0f3d5e", "navy-700": "#0b2e47", "navy-100": "#e3edf5", "accent": "#e07a1f", "accent-100": "#fbe9d8",
            "ink": "#16212b", "ink-2": "#44535f", "ink-3": "#5f6f7c", "line": "#e2e8ee", "line-2": "#cdd6de",
            "bg": "#f4f6f8", "card": "#ffffff",
            "sidebar-bg": "#0f3d5e", "sidebar-ink": "#d8e4ee", "sidebar-muted": "#a9bfd0", "sidebar-active": "rgba(255,255,255,.14)",
        },
    },
    "airy": {
        "name": "Light & airy",
        "description": "White sidebar, soft blue accent, generous spacing. Calm and modern.",
        "vars": {
            "font": "Inter, 'Segoe UI', system-ui, -apple-system, Roboto, 'Helvetica Neue', Arial, sans-serif",
            "font-size": "16px", "radius": "14px",
            "navy": "#2457a6", "navy-700": "#1b437f", "navy-100": "#e6eefb", "accent": "#0ea5a0", "accent-100": "#d9f3f1",
            "ink": "#1b2430", "ink-2": "#4a5563", "ink-3": "#6b7785", "line": "#e6eaf0", "line-2": "#d2d9e2",
            "bg": "#f7f8fa", "card": "#ffffff",
            "sidebar-bg": "#ffffff", "sidebar-ink": "#2b3642", "sidebar-muted": "#7b8794", "sidebar-active": "#e6eefb",
        },
    },
    "slate": {
        "name": "Engineering slate",
        "description": "Charcoal sidebar, teal accent, tighter density for power users.",
        "vars": {
            "font": "'IBM Plex Sans', Inter, 'Segoe UI', system-ui, sans-serif",
            "font-size": "15px", "radius": "6px",
            "navy": "#2d3e50", "navy-700": "#1f2d3b", "navy-100": "#e4e9ee", "accent": "#0f9d8a", "accent-100": "#d6f2ed",
            "ink": "#1a2129", "ink-2": "#3f4b57", "ink-3": "#66737f", "line": "#e1e6ea", "line-2": "#c9d1d8",
            "bg": "#eef1f4", "card": "#ffffff",
            "sidebar-bg": "#1f2d3b", "sidebar-ink": "#d6dde4", "sidebar-muted": "#93a0ad", "sidebar-active": "rgba(255,255,255,.12)",
        },
    },
    "large": {
        "name": "Large & high contrast",
        "description": "Bigger text, stronger contrast, simple shapes. Easiest on the eyes.",
        "vars": {
            "font": "'Atkinson Hyperlegible', Inter, 'Segoe UI', system-ui, Arial, sans-serif",
            "font-size": "18px", "radius": "8px",
            "navy": "#003a70", "navy-700": "#002850", "navy-100": "#e0ebf7", "accent": "#c25400", "accent-100": "#fde4d3",
            "ink": "#000000", "ink-2": "#2a2a2a", "ink-3": "#4d4d4d", "line": "#d9d9d9", "line-2": "#b8b8b8",
            "bg": "#f2f2f2", "card": "#ffffff",
            "sidebar-bg": "#003a70", "sidebar-ink": "#ffffff", "sidebar-muted": "#c7d6e6", "sidebar-active": "rgba(255,255,255,.2)",
        },
    },
}
DEFAULT_PRESET = "classic"
VAR_KEYS = list(PRESETS["classic"]["vars"].keys())
