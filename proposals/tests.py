from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import AccessRole, CAPABILITY_KEYS, CompanyProfile, Currency, Region
from crm.models import Client, Contact
from proposals.models import Employee, FeeItem, FeeLine, Proposal, ProposalTemplate, StaffRole, TemplateSection
from proposals.suggestions import suggest_for_item


def _currencies():
    cad = Currency.objects.create(code="CAD", name="Canadian dollar", symbol="CA$", rate_to_base=1)
    usd = Currency.objects.create(code="USD", name="US dollar", symbol="US$", rate_to_base=Decimal("1.40"))
    c = CompanyProfile.get_solo()
    c.default_currency = cad
    c.save()
    Region.objects.get_or_create(code="ON", defaults={"name": "Ontario"})
    return cad, usd


def _superuser_like(user):
    role, _ = AccessRole.objects.get_or_create(name="Partners", defaults={"capabilities": CAPABILITY_KEYS, "rank": 10})
    role.users.add(user)
    return user


class ProposalModelTests(TestCase):
    def setUp(self):
        self.cad, self.usd = _currencies()
        self.client_obj = Client.objects.create(name="Metro")
        self.contact = Contact.objects.create(client=self.client_obj, name="Dana")
        self.role = StaffRole.objects.create(title="Engineer", default_rate=Decimal("150"))
        self.emp = Employee.objects.create(name="Ann Lee", role=self.role, rate=Decimal("200"))

    def test_numbering_increments_per_year(self):
        p1 = Proposal.objects.create(title="A")
        p2 = Proposal.objects.create(title="B")
        self.assertTrue(p1.number.endswith("-001"))
        self.assertTrue(p2.number.endswith("-002"))
        self.assertEqual(p1.currency, self.cad)

    def test_fee_totals_and_currency_conversion(self):
        p = Proposal.objects.create(title="A", probability=50, contingency_percent=Decimal("10"), currency=self.usd)
        item = FeeItem.objects.create(proposal=p, code="1", name="Drawings")
        l1 = FeeLine.objects.create(item=item, kind="labour", employee=self.emp, hours=Decimal("10"))
        self.assertEqual(l1.role, self.role)
        self.assertEqual(l1.unit_cost, Decimal("142.86"))  # 200 CAD -> USD at 1.40
        self.assertEqual(l1.amount, Decimal("1428.60"))
        l2 = FeeLine.objects.create(item=item, kind="labour", role=self.role, hours=Decimal("4"), unit_cost=Decimal("100"))
        self.assertEqual(l2.amount, Decimal("400"))
        FeeLine.objects.create(item=item, kind="software", description="Licence", quantity=2, unit_cost=Decimal("500"), markup_percent=Decimal("10"))
        self.assertEqual(p.labour_total, Decimal("1828.60"))
        self.assertEqual(p.expense_total, Decimal("1100.00"))
        self.assertEqual(p.subtotal, Decimal("2928.60"))
        self.assertEqual(p.contingency_amount, Decimal("292.86"))
        self.assertEqual(p.fee_total, Decimal("3221.46"))
        self.assertEqual(p.fee_total_base, Decimal("4510.044"))
        self.assertEqual(p.total_hours, Decimal("14"))
        self.assertEqual(item.total, Decimal("2928.60"))
        p.manual_value = Decimal("5000")
        self.assertEqual(p.fee_total, Decimal("5000"))
        self.assertEqual(p.money(p.fee_total), "US$5,000")

    def test_placeholders_and_template_apply(self):
        t = ProposalTemplate.objects.create(name="T")
        TemplateSection.objects.create(template=t, order=0, title="Intro", body="Dear {{contact_name}} of {{client_name}}, re {{project_name}} {{unknown}}")
        p = Proposal.objects.create(title="Tunnel", client=self.client_obj, contact=self.contact)
        p.apply_template(t)
        self.assertEqual(p.sections.first().rendered_body, "Dear Dana of Metro, re Tunnel {{unknown}}")

    def test_project_numbering_and_phases(self):
        on = Region.objects.get(code="ON")
        p = Proposal.objects.create(title="A")
        self.assertIsNone(p.project_number)
        with self.assertRaises(Exception):
            Proposal(title="X", status="won").full_clean()  # needs a number before won
        p.assign_project_number(region=on)
        self.assertEqual(p.sequence, 601)
        self.assertEqual(p.project_number, "B-ON601")
        q = Proposal.objects.create(title="B", region=on)
        q.assign_project_number()
        self.assertEqual(q.project_number, "B-ON602")
        p.status = "won"
        p.save()  # won in phase B → C automatically
        self.assertEqual((p.phase, p.project_number), ("C", "601C"))
        p.advance_phase("D")
        self.assertEqual(p.project_number, "601D")
        self.assertEqual(p.phase_changes.count(), 2)
        self.assertIn("601D", p.smb_path)
        with self.assertRaises(Exception):
            Proposal(title="dup", region=on, sequence=601, phase="D").full_clean()
        c = CompanyProfile.get_solo()
        c.number_digits = 4
        c.save()
        self.assertEqual(Proposal.objects.get(pk=q.pk).compute_project_number(), "B-ON0602")

    def test_suggestions_from_won_projects(self):
        won = Proposal.objects.create(title="Old", status="won", region=Region.objects.get(code="ON"), sequence=650)
        item = FeeItem.objects.create(proposal=won, name="Segmental lining design drawings", kind="drawing")
        FeeLine.objects.create(item=item, kind="labour", employee=self.emp, hours=100)
        from timesheets.models import ActualEntry

        ActualEntry.objects.create(proposal=won, item=item, employee=self.emp, date="2026-01-05", hours=120)
        new = Proposal.objects.create(title="New")
        res = suggest_for_item("lining drawings", exclude_proposal=new)
        self.assertEqual(res["summary"]["n"], 1)
        self.assertEqual(res["matches"][0]["est_hours"], Decimal("100"))
        self.assertEqual(res["matches"][0]["act_hours"], Decimal("120"))
        self.assertAlmostEqual(res["matches"][0]["hours_ratio"], 1.2)
        self.assertEqual(res["summary"]["recommended_hours"], Decimal("120"))
        self.assertEqual(suggest_for_item("xyz unrelated", exclude_proposal=new)["matches"], [])


class ProposalViewTests(TestCase):
    def setUp(self):
        _currencies()
        self.user = _superuser_like(get_user_model().objects.create_user("u", password="p"))
        self.client.force_login(self.user)
        self.cl = Client.objects.create(name="Metro")
        self.t = ProposalTemplate.objects.create(name="T", is_default=True)
        TemplateSection.objects.create(template=self.t, order=0, title="Intro", body="Hi {{client_name}}")
        self.role = StaffRole.objects.create(title="Engineer", default_rate=100)
        self.emp = Employee.objects.create(name="Ann Lee", role=self.role, rate=120)

    def test_create_from_template_and_pages(self):
        on = Region.objects.get(code="ON")
        r = self.client.post(reverse("proposal_create"), {"title": "New", "client": self.cl.pk, "service_type": "design", "template": self.t.pk, "region": on.pk, "assign_number": "on"})
        self.assertEqual(r.status_code, 302)
        p = Proposal.objects.get(title="New")
        self.assertEqual(p.sections.count(), 1)
        self.assertEqual(p.project_number, "B-ON601")
        for name in ("proposal_detail", "proposal_sections", "proposal_fee", "proposal_schedule", "proposal_preview", "proposal_actuals", "proposal_records"):
            self.assertEqual(self.client.get(reverse(name, args=[p.pk])).status_code, 200, name)
        self.assertContains(self.client.get(reverse("proposal_preview", args=[p.pk])), "Hi Metro")

    def test_fee_item_and_line_flow(self):
        p = Proposal.objects.create(title="P")
        r = self.client.post(reverse("item_add", args=[p.pk]), {"name": "Drawings", "kind": "drawing", "code": ""}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        item = p.items.get()
        self.assertEqual(item.code, "1")
        r = self.client.post(reverse("line_add", args=[item.pk]), {"kind": "labour", "employee": self.emp.pk, "hours": "10"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(p.fee_total, Decimal("1200"))
        r = self.client.post(reverse("line_add", args=[item.pk]), {"kind": "software", "description": "Licence", "quantity": "1", "unit_cost": "300"}, HTTP_HX_REQUEST="true")
        self.assertEqual(p.fee_total, Decimal("1500"))
        r = self.client.post(reverse("line_add", args=[item.pk]), {"kind": "labour", "hours": "1"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 422)
        r = self.client.get(reverse("rate_lookup"), {"proposal": p.pk, "employee": self.emp.pk})
        self.assertEqual(r.content, b"120.00")
        r = self.client.get(reverse("fee_suggest", args=[p.pk]), {"name": "draw"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("item_duplicate", args=[item.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(p.items.count(), 2)
        self.assertEqual(p.fee_total, Decimal("3000"))
        r = self.client.post(reverse("line_delete", args=[item.lines.first().pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("item_delete", args=[item.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(p.items.count(), 1)

    def test_exports(self):
        p = Proposal.objects.create(title="P", summary="Sum")
        item = FeeItem.objects.create(proposal=p, code="1", name="Drawings")
        FeeLine.objects.create(item=item, kind="labour", employee=self.emp, hours=10)
        from scheduling.gantt import create_default_tasks

        create_default_tasks(p, __import__("datetime").date(2026, 3, 2))
        r = self.client.get(reverse("proposal_export", args=[p.pk, "docx"]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"PK"))
        r = self.client.get(reverse("proposal_export", args=[p.pk, "pdf"]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_won_requires_number_and_capability(self):
        p = Proposal.objects.create(title="P")
        r = self.client.post(reverse("proposal_detail", args=[p.pk]), {"title": "P", "service_type": "design", "status": "won", "probability": 50, "contingency_percent": 0})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Assign a project number")
        on = Region.objects.get(code="ON")
        r = self.client.post(reverse("assign_number", args=[p.pk]), {"region": on.pk})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.project_number, "B-ON601")
        r = self.client.post(reverse("proposal_status", args=[p.pk]), {"status": "won", "render": "header"}, HTTP_HX_REQUEST="true")
        p.refresh_from_db()
        self.assertEqual((p.status, p.phase, p.project_status, p.project_number), ("won", "C", "active", "601C"))
        r = self.client.post(reverse("change_phase", args=[p.pk]), {"phase": "E"})
        p.refresh_from_db()
        self.assertEqual(p.project_number, "601E")
        r = self.client.post(reverse("record_add", args=[p.pk]), {"kind": "progress", "date": "2026-05-01", "title": "Advance", "value": "3.2", "unit": "m/day"})
        self.assertContains(self.client.get(reverse("proposal_records", args=[p.pk])), "m/day")
        # an engineer without approve_won cannot decide or assign
        eng = get_user_model().objects.create_user("eng", password="p")
        role = AccessRole.objects.create(name="Engineers", capabilities=["view_proposals", "edit_proposals"])
        role.users.add(eng)
        self.client.force_login(eng)
        q = Proposal.objects.create(title="Q")
        self.assertEqual(self.client.post(reverse("assign_number", args=[q.pk]), {"region": on.pk}).status_code, 403)
        self.client.post(reverse("proposal_status", args=[q.pk]), {"status": "won"}, HTTP_HX_REQUEST="true")
        q.refresh_from_db()
        self.assertEqual(q.status, "lead")
        self.assertEqual(self.client.get(reverse("proposal_fee", args=[q.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("company_settings")).status_code, 403)

    def test_library_role_delete_deactivates_when_used(self):
        self.client.post(reverse("role_delete", args=[self.role.pk]), HTTP_HX_REQUEST="true")
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_active)

    def test_employee_crud(self):
        r = self.client.post(reverse("employee_add"), {"name": "Bob Ray", "role": self.role.pk, "rate": "90"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "Bob Ray")
        e = Employee.objects.get(name="Bob Ray")
        self.assertEqual(e.initials, "BR")
        self.client.post(reverse("employee_delete", args=[e.pk]), HTTP_HX_REQUEST="true")
        self.assertFalse(Employee.objects.filter(pk=e.pk).exists())


class AttachmentAndExportTests(TestCase):
    def setUp(self):
        _currencies()
        self.user = _superuser_like(get_user_model().objects.create_user("u", password="p"))
        self.client.force_login(self.user)
        from projects.models import PastProject
        from tags.models import Tag, TagCategory

        cat = TagCategory.objects.create(name="Method", weight=1.5)
        self.p = Proposal.objects.create(title="Twin tunnel final design", summary="EPB TBM running tunnels in glacial till", closing_words="Thank you {{client_name}}")
        self.p.set_tags(["TBM – EPB", "Running tunnel"])
        self.good = PastProject.objects.create(name="Riverside tunnels", kind="tunnel", description="EPB TBM tunnels in glacial till", is_published=True)
        self.good.set_tags(["TBM – EPB", "Running tunnel"])
        self.bad = PastProject.objects.create(name="Pump cavern", kind="cavern", description="Drill and blast cavern", is_published=True)
        self.draft = PastProject.objects.create(name="Draft sheet", kind="tunnel", is_published=False)

    def test_relevance_ordering_and_toggle(self):
        sugg = self.p.suggested_sheets(limit=0)
        self.assertEqual([s["sheet"] for s in sugg][:2], [self.good, self.bad])
        self.assertGreater(sugg[0]["score"], sugg[1]["score"])
        self.assertNotIn(self.draft, [s["sheet"] for s in sugg])
        r = self.client.post(reverse("attachment_toggle", args=[self.p.pk, self.good.pk]), HTTP_HX_REQUEST="true")
        self.assertContains(r, "checked")
        self.assertEqual(self.p.attachments.count(), 1)
        self.assertEqual(self.client.get(reverse("proposal_attachments", args=[self.p.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("project_preview", args=[self.good.pk])).status_code, 200)
        self.client.post(reverse("attachment_toggle", args=[self.p.pk, self.good.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(self.p.attachments.count(), 0)

    def test_export_with_attachments(self):
        from proposals.models import ProposalAttachment

        ProposalAttachment.objects.create(proposal=self.p, project=self.good, kind="sheet")
        pdf = self.client.get(reverse("proposal_export", args=[self.p.pk, "pdf"]))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        from pypdf import PdfReader
        from io import BytesIO

        text = "".join(pg.extract_text() for pg in PdfReader(BytesIO(pdf.content)).pages)
        self.assertIn("Fee summary", text)
        self.assertIn("Terms", text)
        self.assertIn("Riverside tunnels", text)
        self.assertIn("Capabilities", text)
        docx = self.client.get(reverse("proposal_export", args=[self.p.pk, "docx"]))
        self.assertTrue(docx.content.startswith(b"PK"))
        self.assertEqual(self.client.get(reverse("project_pdf", args=[self.good.pk])).status_code, 200)

    def test_form_builder_hides_and_adds_fields(self):
        from core.models import CustomField, FieldRule

        FieldRule.objects.create(form_key="proposal", field_name="probability", visible=False)
        CustomField.objects.create(form_key="proposal", key="procurement", label="Procurement route", type="choice", choices="DBB, DB, P3", show_in_export=True)
        r = self.client.get(reverse("proposal_detail", args=[self.p.pk]))
        self.assertNotContains(r, 'name="probability"')
        self.assertContains(r, 'name="cf_procurement"')
        r = self.client.post(reverse("proposal_detail", args=[self.p.pk]), {"title": "T", "service_type": "design", "status": "lead", "contingency_percent": 0, "cf_procurement": "P3", "closing_words": "x", "tags": "a, b"})
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.extra["procurement"], "P3")
        self.assertEqual({t.name for t in self.p.tags}, {"a", "b"})
        self.assertEqual(self.client.get(reverse("form_builder", args=["proposal"])).status_code, 200)
