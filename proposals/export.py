"""Word (.docx) and PDF export of a proposal.

Structure: main body (cover, description, your sections, fee summary, closing
words, signature, validity note) followed by attachments in order: fee
breakdown, schedule, terms & validity, project sheets / files / calculations
(as arranged on the Attachments tab), and the capabilities statement.
"""

from io import BytesIO

from django.utils import timezone

from core.models import CompanyProfile
from scheduling.gantt import build_gantt


def _hex(color: str):
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _rl(hexcolor):
    from reportlab.lib import colors

    return colors.HexColor(hexcolor)


def _fee_rows(proposal):
    rows = []
    for item in proposal.items.prefetch_related("lines__employee", "lines__role"):
        rows.append(("item", item))
        for line in item.lines.all():
            rows.append(("line", line))
    return rows


def _fee_summary_rows(proposal):
    rows = [(f"{it.code} {it.name}".strip(), proposal.money(it.total)) for it in proposal.items.all()]
    rows.append(("Labour", proposal.money(proposal.labour_total)))
    if proposal.expense_total:
        rows.append(("Expenses & other", proposal.money(proposal.expense_total)))
    if proposal.contingency_percent:
        rows.append((f"Contingency ({proposal.contingency_percent:g}%)", proposal.money(proposal.contingency_amount)))
    rows.append((f"Total fee ({proposal.cur.code})", proposal.money(proposal.fee_total)))
    return rows


def _custom_fields(proposal):
    from core.models import CustomField

    out = []
    for cf in CustomField.objects.filter(form_key="proposal", is_active=True, show_in_export=True):
        val = (proposal.extra or {}).get(cf.key)
        if val not in (None, "", False):
            out.append((cf.label, "Yes" if val is True else str(val)))
    return out


# ----------------------------------------------------------------------------
# Gantt drawing (shared)
# ----------------------------------------------------------------------------
def gantt_drawing(tasks, scale: float = 1.0, max_width=None):
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String

    g = build_gantt(tasks, max_width=max_width)
    if not g:
        return None
    d = Drawing(g["width"] * scale, g["height"] * scale)
    d.scale(scale, scale)
    H = g["height"]

    def y(v):
        return H - v

    for m in g["months"]:
        d.add(Rect(m["x"], y(22), m["w"], 22, fillColor=_rl("#f3f6f9"), strokeColor=_rl("#e2e8ee"), strokeWidth=0.5))
        d.add(String(m["x"] + 4, y(15), m["label"], fontSize=7, fillColor=_rl("#44535f")))
    for w in g["weeks"]:
        if g["day_px"] >= 2:
            d.add(Line(w["x"], y(22), w["x"], 0, strokeColor=_rl("#e2e8ee"), strokeWidth=0.5))
    for r in g["rows"]:
        d.add(Line(0, y(r["y"] + g["row_h"]), g["width"], y(r["y"] + g["row_h"]), strokeColor=_rl("#e2e8ee"), strokeWidth=0.5))
        d.add(String(8, y(r["cy"] + 3), r["task"].name[:34], fontSize=7.5, fontName="Helvetica-Bold" if r["is_milestone"] else "Helvetica", fillColor=_rl("#16212b")))
        if r["is_milestone"]:
            cx, cy = r["x"], y(r["cy"])
            d.add(Polygon([cx, cy + 6, cx + 6, cy, cx, cy - 6, cx - 6, cy], fillColor=_rl(r["color"]), strokeColor=None))
            d.add(String(cx + 9, cy - 2.5, r["label"], fontSize=6.5, fillColor=_rl("#74838f")))
        else:
            d.add(Rect(r["x"], y(r["y"] + g["row_h"] - 7), r["w"], g["row_h"] - 14, fillColor=_rl(r["color"]), strokeColor=None, rx=3, ry=3))
            if r["w"] > 92:
                d.add(String(r["x"] + 5, y(r["cy"] + 3), r["label"], fontSize=6.5, fillColor=_rl("#ffffff")))
    if g["today_x"]:
        d.add(Line(g["today_x"], y(22), g["today_x"], 0, strokeColor=_rl("#e07a1f"), strokeWidth=1, strokeDashArray=[3, 2]))
    return d


def render_gantt_png(tasks) -> bytes | None:
    d = gantt_drawing(tasks, scale=2, max_width=640)
    if d is None:
        return None
    try:
        from reportlab.graphics import renderPM

        return renderPM.drawToString(d, fmt="PNG")
    except Exception:
        return None


# ----------------------------------------------------------------------------
# DOCX
# ----------------------------------------------------------------------------
def build_docx(proposal) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.shared import Cm, Pt, RGBColor

    company = CompanyProfile.get_solo()
    primary = RGBColor(*_hex(company.primary_color))
    accent = RGBColor(*_hex(company.accent_color))
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2)
        s.top_margin = s.bottom_margin = Cm(2)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    def heading(text, level=1):
        h = doc.add_heading(text, level=level)
        for r in h.runs:
            r.font.color.rgb = primary
        return h

    def page_break():
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- cover ----
    if company.logo:
        try:
            doc.add_picture(company.logo.path, height=Cm(2.2))
        except Exception:
            pass
    p = doc.add_paragraph()
    r = p.add_run(company.name)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(14), primary
    for m in (company.tagline, company.address, company.phone, company.email, company.website):
        if m:
            doc.add_paragraph(m).paragraph_format.space_after = Pt(0)
    doc.add_paragraph()
    k = doc.add_paragraph()
    kr = k.add_run(f"PROPOSAL {proposal.number} · {proposal.get_service_type_display().upper()}")
    kr.bold, kr.font.size, kr.font.color.rgb = True, Pt(9), accent
    heading(proposal.title, 0)
    t = doc.add_table(rows=0, cols=2)
    t.style = "Light List"
    pairs = [("Prepared for", f"{proposal.client or '—'}" + (f"\n{proposal.contact.name}" + (f", {proposal.contact.title}" if proposal.contact.title else "") if proposal.contact else "")), ("Date", timezone.localdate().strftime("%d %B %Y"))]
    if proposal.project_number:
        pairs.append(("Project number", proposal.project_number))
    if proposal.location:
        pairs.append(("Location", proposal.location))
    if proposal.owner:
        pairs.append(("Prepared by", proposal.owner.get_full_name() or proposal.owner.username))
    pairs.append(("Currency", proposal.cur.code))
    pairs += _custom_fields(proposal)
    for a, b in pairs:
        row = t.add_row().cells
        row[0].text, row[1].text = a, b
        row[0].paragraphs[0].runs[0].bold = True

    # ---- main body ----
    n = 0
    if proposal.summary:
        n += 1
        heading(f"{n}. Project description", 1)
        for para in proposal.rendered_summary.split("\n"):
            doc.add_paragraph(para)
    for s in proposal.sections.all():
        n += 1
        heading(f"{n}. {s.title}", 1)
        for para in (s.rendered_body or "").split("\n"):
            doc.add_paragraph(para)
    n += 1
    heading(f"{n}. Fee summary", 1)
    ft = doc.add_table(rows=0, cols=2)
    ft.style = "Light Grid"
    for a, b in _fee_summary_rows(proposal):
        c = ft.add_row().cells
        c[0].text, c[1].text = a, b
        c[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    last = ft.rows[-1].cells
    for cell in last:
        for p_ in cell.paragraphs:
            for r_ in p_.runs:
                r_.bold = True
    if proposal.include_fee_breakdown and proposal.items.exists():
        doc.add_paragraph("The detailed fee breakdown is provided in Attachment A.").runs[0].italic = True
    if proposal.validity_line:
        doc.add_paragraph(f"This proposal is valid for {proposal.validity_line.rstrip('.')}.")
    n += 1
    heading(f"{n}. Closing", 1)
    doc.add_paragraph(proposal.render_text(proposal.closing_words))
    doc.add_paragraph()
    name, title = proposal.signature
    doc.add_paragraph("Yours sincerely,")
    doc.add_paragraph()
    sig = doc.add_paragraph()
    sr = sig.add_run(name)
    sr.bold = True
    doc.add_paragraph(f"{title}, {company.name}")

    # ---- attachments ----
    letter = ord("A")
    rows = _fee_rows(proposal)
    if proposal.include_fee_breakdown and rows:
        page_break()
        heading(f"Attachment {chr(letter)} — Fee breakdown ({proposal.cur.code})", 1)
        letter += 1
        bt = doc.add_table(rows=1, cols=5)
        bt.style = "Light Grid"
        for i, hdr in enumerate(("Item / line", "Who / description", "Hours / qty", "Rate", "Amount")):
            bt.rows[0].cells[i].text = hdr
        for kind, obj in rows:
            c = bt.add_row().cells
            if kind == "item":
                c[0].text = f"{obj.code} {obj.name}".strip()
                c[4].text = proposal.money(obj.total)
                for cell in c:
                    for p_ in cell.paragraphs:
                        for r_ in p_.runs:
                            r_.bold = True
            else:
                c[0].text = "    " + obj.get_kind_display()
                c[1].text = obj.label if obj.kind == "labour" else obj.description
                c[2].text = f"{obj.hours:g}" if obj.kind == "labour" else f"{obj.quantity:g}"
                c[3].text = proposal.money(obj.unit_cost, 2)
                c[4].text = proposal.money(obj.amount)
            for i in (2, 3, 4):
                c[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for label, amt in _fee_summary_rows(proposal)[-4:]:
            c = bt.add_row().cells
            c[0].text, c[4].text = label, amt
            c[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tasks = list(proposal.tasks.all())
    if proposal.include_schedule and tasks:
        page_break()
        heading(f"Attachment {chr(letter)} — Schedule", 1)
        letter += 1
        png = render_gantt_png(tasks)
        if png:
            doc.add_picture(BytesIO(png), width=Cm(16.5))
        tt = doc.add_table(rows=1, cols=4)
        tt.style = "Light Grid"
        for i, hdr in enumerate(("Task", "Start", "End", "Phase")):
            tt.rows[0].cells[i].text = hdr
        for task in tasks:
            c = tt.add_row().cells
            c[0].text, c[1].text, c[2].text, c[3].text = ("◆ " if task.is_milestone else "") + task.name, task.start.strftime("%d %b %Y"), "" if task.is_milestone else task.end.strftime("%d %b %Y"), task.get_phase_display()
    if proposal.include_terms and company.proposal_terms:
        page_break()
        heading(f"Attachment {chr(letter)} — Terms & validity", 1)
        letter += 1
        for line in company.proposal_terms.splitlines():
            if line.strip():
                doc.add_paragraph(line.strip())
    for att in proposal.attachments.select_related("project", "calc_run"):
        page_break()
        heading(f"Attachment {chr(letter)} — {att.display_title}", 1)
        letter += 1
        if att.project_id:
            pr = att.project
            doc.add_paragraph(f"{pr.display_client} · {pr.location} · {pr.get_kind_display()}{' · ' + str(pr.year_completed) if pr.year_completed else ''}").runs[0].italic = True
            if pr.cover:
                try:
                    doc.add_picture(pr.cover.image.path, width=Cm(16))
                except Exception:
                    pass
            for h, text in (("Project", pr.description), ("Challenges", pr.challenges), ("Our contribution", pr.contribution), ("Value added", pr.value_added)):
                if text:
                    heading(h, 2)
                    doc.add_paragraph(text)
            if pr.services.exists():
                heading("Services provided", 2)
                for s in pr.services.all():
                    doc.add_paragraph(s.name, style="List Bullet")
            for h in pr.highlight_list:
                doc.add_paragraph(h, style="List Bullet")
        elif att.calc_run_id:
            run = att.calc_run
            doc.add_paragraph(f"{run.tool.name} · {run.created_at:%d %b %Y}").runs[0].italic = True
            if run.outputs.get("headline"):
                doc.add_paragraph(run.outputs["headline"]).runs[0].bold = True
            ct = doc.add_table(rows=0, cols=2)
            ct.style = "Light Grid"
            for k, v in run.inputs.items():
                c = ct.add_row().cells
                c[0].text, c[1].text = k, f"{v:g}" if isinstance(v, (int, float)) else str(v)
            for row in run.outputs.get("results", []):
                c = ct.add_row().cells
                c[0].text, c[1].text = row[0], f"{row[1]} {row[2]}".strip()
        else:
            doc.add_paragraph(f"See attached file: {att.file.name.rsplit('/', 1)[-1] if att.file else att.title}")
    if proposal.include_capabilities:
        page_break()
        heading(f"Attachment {chr(letter)} — Capabilities", 1)
        doc.add_paragraph(company.capabilities_statement)
        from .models import Service

        cur_cat = None
        for sv in Service.objects.filter(is_active=True):
            if sv.category != cur_cat:
                cur_cat = sv.category
                heading(sv.get_category_display(), 2)
            doc.add_paragraph(sv.name, style="List Bullet")
    doc.add_paragraph()
    f = doc.add_paragraph(company.proposal_footer)
    f.runs[0].font.size = Pt(8)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------------------
# PDF (ReportLab + pypdf for merging attached PDFs)
# ----------------------------------------------------------------------------
def build_pdf(proposal) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from projects.export import sheet_story, sheet_styles

    company = CompanyProfile.get_solo()
    primary, accent = _rl(company.primary_color), _rl(company.accent_color)
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#555555"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, leading=24, textColor=primary, alignment=0, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, textColor=primary, spaceBefore=12, spaceAfter=4)
    kicker = ParagraphStyle("kicker", parent=body, fontSize=8, textColor=accent, spaceAfter=2)
    right = ParagraphStyle("right", parent=small, alignment=TA_RIGHT)
    width = A4[0] - 4 * cm

    def esc(t):
        return (t or "").replace("&", "&amp;").replace("<", "&lt;")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=f"{proposal.number} {proposal.title}", author=company.name)
    story = []
    left = []
    if company.logo:
        try:
            left.append(Image(company.logo.path, width=4.5 * cm, height=1.8 * cm, kind="proportional"))
        except Exception:
            pass
    left.append(Paragraph(f"<b>{esc(company.name)}</b>", ParagraphStyle("co", parent=body, textColor=primary, fontSize=11)))
    co = "<br/>".join(esc(x) for x in (company.tagline, company.address.replace("\n", "<br/>"), company.phone, company.email, company.website) if x)
    cover = Table([[left, Paragraph(co, right)]], colWidths=[9 * cm, 8 * cm])
    cover.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 2, primary), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [cover, Spacer(1, 14), Paragraph(f"PROPOSAL {proposal.number} · {proposal.get_service_type_display().upper()}", kicker), Paragraph(esc(proposal.title), h1)]
    meta = [["Prepared for", esc(f"{proposal.client or '—'}") + (f"<br/>{esc(proposal.contact.name)}" if proposal.contact else "")], ["Date", timezone.localdate().strftime("%d %B %Y")]]
    if proposal.project_number:
        meta.append(["Project number", proposal.project_number])
    if proposal.location:
        meta.append(["Location", esc(proposal.location)])
    if proposal.owner:
        meta.append(["Prepared by", esc(proposal.owner.get_full_name() or proposal.owner.username)])
    meta.append(["Currency", proposal.cur.code])
    meta += [[esc(a), esc(b)] for a, b in _custom_fields(proposal)]
    mt = Table([[Paragraph(f"<b>{a}</b>", small), Paragraph(b, body)] for a, b in meta], colWidths=[3.5 * cm, 13.5 * cm])
    mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    story += [Spacer(1, 8), mt]

    n = 0
    if proposal.summary:
        n += 1
        story.append(Paragraph(f"{n}. Project description", h2))
        story.append(Paragraph(esc(proposal.rendered_summary).replace("\n", "<br/>"), body))
    for s in proposal.sections.all():
        n += 1
        story.append(Paragraph(f"{n}. {esc(s.title)}", h2))
        for para in (s.rendered_body or "").split("\n"):
            story.append(Paragraph(esc(para) or "&nbsp;", body))
    n += 1
    block = [Paragraph(f"{n}. Fee summary", h2)]
    srows = _fee_summary_rows(proposal)
    st = Table([[esc(a), b] for a, b in srows], colWidths=[12 * cm, 5 * cm])
    st.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e2e8ee")), ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#cdd6de")), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    block.append(st)
    if proposal.include_fee_breakdown and proposal.items.exists():
        block.append(Paragraph("<i>The detailed fee breakdown is provided in Attachment A.</i>", small))
    if proposal.validity_line:
        block.append(Paragraph(f"This proposal is valid for {esc(proposal.validity_line.rstrip('.'))}.", body))
    story.append(KeepTogether(block))
    n += 1
    name, title = proposal.signature
    story += [Paragraph(f"{n}. Closing", h2), Paragraph(esc(proposal.render_text(proposal.closing_words)), body), Spacer(1, 10), Paragraph("Yours sincerely,", body), Spacer(1, 26), Paragraph(f"<b>{esc(name)}</b>", body), Paragraph(f"{esc(title)}, {esc(company.name)}", small)]

    # ---- attachments ----
    letter = ord("A")

    def att_head(text):
        nonlocal letter
        story.append(PageBreak())
        story.append(Paragraph(f"Attachment {chr(letter)} — {esc(text)}", h2))
        letter += 1

    rows = _fee_rows(proposal)
    if proposal.include_fee_breakdown and rows:
        att_head(f"Fee breakdown ({proposal.cur.code})")
        data = [["Item / line", "Who / description", "Hours / qty", "Rate", "Amount"]]
        styles = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6f9")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#44535f")), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#cdd6de")), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e2e8ee")), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        for kind, obj in rows:
            i = len(data)
            if kind == "item":
                data.append([f"{obj.code} {obj.name}".strip(), "", "", "", proposal.money(obj.total)])
                styles += [("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"), ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fafbfc"))]
            else:
                data.append(["    " + obj.get_kind_display(), obj.label if obj.kind == "labour" else obj.description, f"{obj.hours:g}" if obj.kind == "labour" else f"{obj.quantity:g}", proposal.money(obj.unit_cost, 2), proposal.money(obj.amount)])
        tail = srows[-4:] if proposal.contingency_percent else srows[-3:]
        for label, amt in tail:
            i = len(data)
            data.append([label, "", "", "", amt])
            styles.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        ft = Table(data, colWidths=[5.2 * cm, 5.3 * cm, 2 * cm, 2.2 * cm, 2.6 * cm], repeatRows=1)
        ft.setStyle(TableStyle(styles))
        story.append(ft)
    tasks = list(proposal.tasks.all())
    if proposal.include_schedule and tasks:
        att_head("Schedule")
        drawing = gantt_drawing(tasks, max_width=17 * cm)
        if drawing is not None:
            story.append(drawing)
    if proposal.include_terms and company.proposal_terms:
        att_head("Terms & validity")
        for line in company.proposal_terms.splitlines():
            if line.strip():
                story.append(Paragraph(esc(line.strip()), body))
                story.append(Spacer(1, 4))
    sheet_st = sheet_styles(company)
    merge_pdfs = []  # (position_marker_page, bytes)
    for att in proposal.attachments.select_related("project", "calc_run"):
        if att.project_id:
            story.append(PageBreak())
            story.append(Paragraph(f"Attachment {chr(letter)} — Project sheet", kicker))
            letter += 1
            story += sheet_story(att.project, sheet_st, width, company)
        elif att.calc_run_id:
            run = att.calc_run
            att_head(f"Calculation — {run.title}")
            story.append(Paragraph(f"{esc(run.tool.name)} · {run.created_at:%d %b %Y}", small))
            if run.outputs.get("headline"):
                story.append(Paragraph(f"<b>{esc(run.outputs['headline'])}</b>", body))
            data = [["Input", "Value"]] + [[k, f"{v:g}" if isinstance(v, (int, float)) else str(v)] for k, v in run.inputs.items()] + [["Result", ""]] + [[r[0], f"{r[1]} {r[2]}".strip()] for r in run.outputs.get("results", [])]
            ct = Table(data, colWidths=[10 * cm, 7 * cm])
            ct.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8ee")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
            story.append(ct)
        else:
            att_head(att.display_title)
            if att.file and att.file.name.lower().endswith(".pdf"):
                story.append(Paragraph("<i>The attached PDF follows.</i>", small))
                try:
                    merge_pdfs.append((len(story), att.file.read()))
                except Exception:
                    pass
            elif att.file and att.file.name.lower().endswith((".png", ".jpg", ".jpeg")):
                try:
                    story.append(Image(att.file.path, width=width, height=width * 0.7, kind="proportional"))
                except Exception:
                    story.append(Paragraph(esc(att.file.name), body))
            else:
                story.append(Paragraph(f"See attached file: {esc(att.file.name.rsplit('/', 1)[-1] if att.file else att.title)}", body))
    if proposal.include_capabilities:
        att_head("Capabilities")
        story.append(Paragraph(esc(company.capabilities_statement), body))
        from .models import Service

        cur_cat = None
        for sv in Service.objects.filter(is_active=True):
            if sv.category != cur_cat:
                cur_cat = sv.category
                story.append(Paragraph(esc(sv.get_category_display()), ParagraphStyle("h3", parent=h2, fontSize=10.5, spaceBefore=8)))
            story.append(Paragraph(f"• {esc(sv.name)}", body))
    story += [Spacer(1, 18), Paragraph(esc(company.proposal_footer), small)]

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(2 * cm, 1.1 * cm, f"{company.name} · {proposal.number}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    out = buf.getvalue()
    if merge_pdfs:
        try:
            from pypdf import PdfReader, PdfWriter

            w = PdfWriter()
            for page in PdfReader(BytesIO(out)).pages:
                w.add_page(page)
            for _, data in merge_pdfs:
                for page in PdfReader(BytesIO(data)).pages:
                    w.add_page(page)
            ob = BytesIO()
            w.write(ob)
            out = ob.getvalue()
        except Exception:
            pass
    return out
