"""One-page project sheet PDF with a fixed template: cover image, facts strip,
description, challenges, our contribution, value added, services and highlights."""

from io import BytesIO

from django.utils import timezone

from core.models import CompanyProfile


def _rl(hexcolor):
    from reportlab.lib import colors

    return colors.HexColor(hexcolor)


def sheet_story(project, styles, width, company=None, page_break=False):
    """Flowables for one sheet (reused by the proposal export)."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

    company = company or CompanyProfile.get_solo()
    primary, accent = _rl(company.primary_color), _rl(company.accent_color)
    st = styles
    story = []
    if page_break:
        story.append(PageBreak())
    # header band: logo + "Project sheet"
    left = []
    if company.logo:
        try:
            left.append(Image(company.logo.path, width=3.6 * cm, height=1.4 * cm, kind="proportional"))
        except Exception:
            pass
    head = Table([[left or Paragraph(f"<b>{company.name}</b>", st["co"]), Paragraph(f"<b>PROJECT SHEET</b><br/>{project.get_kind_display()}", st["right"])]], colWidths=[width * 0.55, width * 0.45])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.5, accent), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [head, Spacer(1, 8)]
    cover = project.cover
    if cover:
        try:
            story.append(Image(cover.image.path, width=width, height=width * 0.42, kind="proportional"))
            story.append(Spacer(1, 6))
        except Exception:
            pass
    story.append(Paragraph((project.display_client or "").upper(), st["kicker"]))
    story.append(Paragraph(project.name, st["h1"]))
    facts = []
    for k, v in (("Location", project.location), ("Our role", project.role), ("Completed", project.year_completed), ("Construction value", f"${project.construction_value:,.0f}" if project.construction_value else ""), ("Duration", f"{project.duration_months} months" if project.duration_months else ""), ("Key dimensions", project.key_dimensions)):
        if v:
            facts.append([Paragraph(f"<font size=6.5 color='#666666'>{k.upper()}</font><br/><b>{v}</b>", st["body"])])
    if facts:
        cols = min(len(facts), 4)
        rows = [facts[i : i + cols] for i in range(0, len(facts), cols)]
        rows = [[c[0] for c in r] + [""] * (cols - len(r)) for r in rows]
        ft = Table(rows, colWidths=[width / cols] * cols)
        ft.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f4f4")), ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [ft, Spacer(1, 6)]
    blocks = [("Project", project.description), ("Challenges", project.challenges), ("Our contribution", project.contribution), ("Value added", project.value_added)]
    two_col = [b for b in blocks if b[1]]
    cells = []
    for title, text in two_col:
        cells.append([Paragraph(title, st["h2"]), Paragraph(text.replace("\n", "<br/>"), st["body"])])
    if cells:
        # two columns of blocks
        left_col = [c for i, c in enumerate(cells) if i % 2 == 0]
        right_col = [c for i, c in enumerate(cells) if i % 2 == 1]

        def col(items):
            out = []
            for h, p in items:
                out += [h, p, Spacer(1, 5)]
            return out

        t = Table([[col(left_col), col(right_col)]], colWidths=[width * 0.5 - 4, width * 0.5 - 4])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
        story.append(t)
    services = list(project.services.all())
    hl = project.highlight_list
    bottom = []
    if services:
        bottom.append([Paragraph("Services provided", st["h2"]), Paragraph("<br/>".join(f"• {s.name}" for s in services), st["small"])])
    if hl:
        bottom.append([Paragraph("Highlights", st["h2"]), Paragraph("<br/>".join(f"• {h}" for h in hl), st["small"])])
    if bottom:
        bt = Table([[[*b] for b in bottom]], colWidths=[width / len(bottom)] * len(bottom))
        bt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
        story.append(bt)
    if project.reference_contact:
        story.append(Paragraph(f"Reference: {project.reference_contact}", st["small"]))
    tags = ", ".join(t.name for t in project.tags)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"{company.name} · {company.tagline}{' · ' + tags if tags else ''}", st["foot"]))
    return story


def sheet_styles(company=None):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    company = company or CompanyProfile.get_solo()
    primary, accent = _rl(company.primary_color), _rl(company.accent_color)
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=8.8, leading=11.5)
    return {
        "body": body,
        "small": ParagraphStyle("small", parent=body, fontSize=8, leading=10.5),
        "co": ParagraphStyle("co", parent=body, fontSize=10, textColor=primary),
        "right": ParagraphStyle("right", parent=body, alignment=TA_RIGHT, fontSize=8, textColor=colors.HexColor("#555555")),
        "kicker": ParagraphStyle("kicker", parent=body, fontSize=7.5, textColor=accent, spaceAfter=1),
        "h1": ParagraphStyle("h1", parent=ss["Title"], fontSize=17, leading=20, textColor=primary, alignment=0, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=ss["Heading3"], fontSize=9.5, leading=12, textColor=primary, spaceBefore=4, spaceAfter=2),
        "foot": ParagraphStyle("foot", parent=body, fontSize=7, textColor=colors.HexColor("#777777")),
    }


def build_sheet_pdf(project) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=f"Project sheet — {project.name}", author=CompanyProfile.get_solo().name)
    width = A4[0] - 3.2 * cm
    doc.build(sheet_story(project, sheet_styles(), width))
    return buf.getvalue()
