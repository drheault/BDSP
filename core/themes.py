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
        "dark": {"navy": "#7fb3dc", "navy-700": "#9cc5e8", "navy-100": "#1d2f3f", "accent": "#f0a062", "accent-100": "#3d2a18", "ink": "#e8edf2", "ink-2": "#bcc6d0", "ink-3": "#8795a3", "line": "#273340", "line-2": "#36455a", "bg": "#0f161d", "card": "#172029", "sidebar-bg": "#0a1118", "sidebar-ink": "#d8e4ee", "sidebar-muted": "#8ea2b4", "sidebar-active": "rgba(255,255,255,.12)"},
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
        "dark": {"navy": "#8db4f0", "navy-700": "#a9c6f4", "navy-100": "#1f2a3d", "accent": "#3fc7c1", "accent-100": "#14403e", "ink": "#eaeef3", "ink-2": "#c0c8d2", "ink-3": "#8b96a3", "line": "#2a323c", "line-2": "#3a4450", "bg": "#121619", "card": "#1a2026", "sidebar-bg": "#1a2026", "sidebar-ink": "#dfe5ec", "sidebar-muted": "#8b96a3", "sidebar-active": "#263244"},
    },
    "slate": {
        "name": "Engineering slate (Dr. Sauer)",
        "description": "Anthracite and slate with the Dr. Sauer gold accent. Dark by default, light on request. Technical typeface, tighter density.",
        "vars": {
            "font": "'IBM Plex Sans', Inter, 'Segoe UI', system-ui, sans-serif",
            "font-size": "16px", "radius": "6px",
            "navy": "#2b3440", "navy-700": "#1c232c", "navy-100": "#e6e9ed", "accent": "#b8962e", "accent-100": "#f3ead0",
            "ink": "#1a1f26", "ink-2": "#3f4852", "ink-3": "#66707b", "line": "#dfe3e8", "line-2": "#c6ccd4",
            "bg": "#eef0f3", "card": "#ffffff",
            "sidebar-bg": "#1c232c", "sidebar-ink": "#e4e8ec", "sidebar-muted": "#98a2ad", "sidebar-active": "rgba(184,150,46,.22)",
        },
        "dark": {
            "navy": "#c9a84c", "navy-700": "#e0bf63", "navy-100": "#3a3320", "accent": "#c9a84c", "accent-100": "#3a3320",
            "ink": "#eceff2", "ink-2": "#c3c9d1", "ink-3": "#8e97a2", "line": "#2d343d", "line-2": "#3d4651",
            "bg": "#14181d", "card": "#1c222a",
            "sidebar-bg": "#0f1317", "sidebar-ink": "#e4e8ec", "sidebar-muted": "#8e97a2", "sidebar-active": "rgba(201,168,76,.22)",
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
        "dark": {"navy": "#9ac4f5", "navy-700": "#b6d4f8", "navy-100": "#1c3250", "accent": "#ff9d4d", "accent-100": "#4a2a10", "ink": "#ffffff", "ink-2": "#dcdcdc", "ink-3": "#b3b3b3", "line": "#333333", "line-2": "#4d4d4d", "bg": "#0d0d0d", "card": "#1a1a1a", "sidebar-bg": "#001f3f", "sidebar-ink": "#ffffff", "sidebar-muted": "#c7d6e6", "sidebar-active": "rgba(255,255,255,.22)"},
    },
}
DEFAULT_PRESET = "slate"
VAR_KEYS = list(PRESETS["classic"]["vars"].keys())
