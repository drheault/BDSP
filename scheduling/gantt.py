"""Compute geometry for a server-rendered SVG Gantt chart.

`build_gantt(items)` accepts any iterable of objects exposing
``pk, name, start, end, color, is_milestone, percent_complete, predecessor_id``
and returns a dict the template turns into SVG. Keeping the maths here keeps
the template dumb and testable.
"""

from datetime import date, timedelta
from types import SimpleNamespace

from django.utils import timezone

ROW_H = 30
HEADER_H = 44
LABEL_W = 210
PAD_RIGHT = 24
MIN_DAY_PX = 2.5
MAX_DAY_PX = 28
TARGET_W = 900


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_gantt(items, today=None):
    items = list(items)
    if not items:
        return None
    today = today or timezone.localdate()

    start = _monday(min(t.start for t in items))
    end = max(t.end for t in items)
    end = _monday(end) + timedelta(days=13)  # pad ~2 weeks after the last bar
    total_days = (end - start).days + 1
    day_px = max(MIN_DAY_PX, min(MAX_DAY_PX, TARGET_W / total_days))

    def x_of(d: date) -> float:
        return LABEL_W + (d - start).days * day_px

    chart_w = total_days * day_px
    width = LABEL_W + chart_w + PAD_RIGHT
    height = HEADER_H + ROW_H * len(items) + 12

    # Month bands + week ticks
    months, weeks = [], []
    cursor = start
    while cursor <= end:
        nxt = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
        band_end = min(nxt - timedelta(days=1), end)
        months.append(
            {
                "x": x_of(cursor),
                "w": ((band_end - cursor).days + 1) * day_px,
                "label": cursor.strftime("%b %Y") if ((band_end - cursor).days + 1) * day_px > 48 else cursor.strftime("%b"),
            }
        )
        cursor = nxt
    wk = start
    while wk <= end:
        weeks.append({"x": x_of(wk), "label": wk.strftime("%d") if day_px >= 6 else ""})
        wk += timedelta(days=7)

    rows, pos = [], {}
    for i, t in enumerate(items):
        y = HEADER_H + i * ROW_H
        x = x_of(t.start)
        w = max(day_px, ((t.end - t.start).days + 1) * day_px)
        pct = max(0, min(100, int(getattr(t, "percent_complete", 0) or 0)))
        rows.append(
            {
                "task": t,
                "y": y,
                "cy": y + ROW_H / 2,
                "x": x,
                "w": w,
                "progress_w": w * pct / 100,
                "color": getattr(t, "color", "#0f3d5e"),
                "is_milestone": bool(getattr(t, "is_milestone", False)),
                "label": f"{t.start:%d %b} – {t.end:%d %b}" if not getattr(t, "is_milestone", False) else f"{t.start:%d %b %Y}",
                "zebra": i % 2 == 1,
            }
        )
        pos[t.pk] = (x, x + w, y + ROW_H / 2)

    deps = []
    for t in items:
        pred = getattr(t, "predecessor_id", None)
        if pred and pred in pos and t.pk in pos:
            x1, x2, y1 = pos[pred][1], pos[t.pk][0], pos[pred][2]
            y2 = pos[t.pk][2]
            mid = x1 + 8
            deps.append({"d": f"M{x1},{y1} L{mid},{y1} L{mid},{y2} L{x2},{y2}"})

    today_x = x_of(today) if start <= today <= end else None
    return {
        "width": width,
        "height": height,
        "label_w": LABEL_W,
        "header_h": HEADER_H,
        "row_h": ROW_H,
        "months": months,
        "weeks": weeks,
        "rows": rows,
        "deps": deps,
        "today_x": today_x,
        "start": start,
        "end": end,
        "day_px": day_px,
    }


def summary_item(proposal, tasks):
    """Collapse a proposal's tasks into one bar for the programme overview."""
    tasks = list(tasks)
    if not tasks:
        return None
    pct = round(sum(t.percent_complete for t in tasks) / len(tasks))
    return SimpleNamespace(
        pk=proposal.pk,
        name=f"{proposal.number} · {proposal.title}",
        start=min(t.start for t in tasks),
        end=max(t.end for t in tasks),
        color="#0f3d5e" if proposal.service_type == "design" else "#e07a1f",
        is_milestone=False,
        percent_complete=pct,
        predecessor_id=None,
        proposal=proposal,
    )


# ---------------------------------------------------------------------------
# Default schedules by service type
# ---------------------------------------------------------------------------
DEFAULT_SCHEDULES = {
    "design": [
        ("Notice to proceed", "planning", 0, 0, True),
        ("Data review & site reconnaissance", "planning", 0, 21, False),
        ("Geotechnical interpretation & GBR input", "planning", 14, 42, False),
        ("Preliminary design (30%)", "prelim", 21, 77, False),
        ("30% submittal", "prelim", 77, 77, True),
        ("Detailed design (60%)", "detailed", 84, 154, False),
        ("60% submittal", "detailed", 154, 154, True),
        ("Final design (90%)", "detailed", 161, 217, False),
        ("90% submittal", "detailed", 217, 217, True),
        ("Issued for construction", "detailed", 224, 245, False),
        ("IFC package", "procurement", 245, 245, True),
    ],
    "construction": [
        ("Contract award", "procurement", 0, 0, True),
        ("Pre-construction & submittal register", "construction", 0, 28, False),
        ("Shop drawing & submittal review", "construction", 28, 210, False),
        ("RFI response & design clarifications", "construction", 28, 240, False),
        ("Site engineering support & inspections", "construction", 56, 240, False),
        ("Instrumentation & monitoring review", "construction", 56, 240, False),
        ("Substantial completion", "closeout", 240, 240, True),
        ("Record drawings & close-out", "closeout", 240, 285, False),
    ],
}
DEFAULT_SCHEDULES["both"] = DEFAULT_SCHEDULES["design"] + [
    (name, phase, s + 260, e + 260, ms) for name, phase, s, e, ms in DEFAULT_SCHEDULES["construction"][1:]
]
DEFAULT_SCHEDULES["other"] = [
    ("Kick-off", "planning", 0, 0, True),
    ("Data collection", "planning", 0, 21, False),
    ("Analysis & options study", "planning", 21, 63, False),
    ("Draft report", "planning", 63, 84, False),
    ("Final report", "planning", 91, 105, False),
    ("Final deliverable", "closeout", 105, 105, True),
]


def create_default_tasks(proposal, start: date):
    from .models import Task

    rows = DEFAULT_SCHEDULES.get(proposal.service_type, DEFAULT_SCHEDULES["design"])
    created = []
    for i, (name, phase, s, e, ms) in enumerate(rows):
        created.append(
            Task.objects.create(
                proposal=proposal,
                name=name,
                phase=phase,
                start=start + timedelta(days=s),
                end=start + timedelta(days=e),
                is_milestone=ms,
                order=proposal.tasks.count() + i,
            )
        )
    return created
