from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import CompanyProfile, Currency
from crm.models import Client, Contact
from proposals.models import Employee, FeeItem, FeeLine, Proposal, ProposalTemplate, StaffRole, TemplateSection
from proposals.suggestions import suggest_for_item


def _currencies():
    cad = Currency.objects.create(code="CAD", name="Canadian dollar", symbol="CA$", rate_to_base=1)
    usd = Currency.objects.create(code="USD", name="US dollar", symbol="US$", rate_to_base=Decimal("1.40"))
    c = CompanyProfile.get_solo()
    c.default_currency = cad
    c.save()
    return cad, usd


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

    def test_project_number_validation(self):
        p = Proposal(title="A", project_number="bad")
        with self.assertRaises(Exception):
            p.full_clean()
        p.project_number = "26-001"
        p.full_clean()
        p.status = "won"
        p.project_number = None
        with self.assertRaises(Exception):
            p.full_clean()

    def test_suggestions_from_won_projects(self):
        won = Proposal.objects.create(title="Old", status="won", project_number="25-001")
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
        self.user = get_user_model().objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.cl = Client.objects.create(name="Metro")
        self.t = ProposalTemplate.objects.create(name="T", is_default=True)
        TemplateSection.objects.create(template=self.t, order=0, title="Intro", body="Hi {{client_name}}")
        self.role = StaffRole.objects.create(title="Engineer", default_rate=100)
        self.emp = Employee.objects.create(name="Ann Lee", role=self.role, rate=120)

    def test_create_from_template_and_pages(self):
        r = self.client.post(reverse("proposal_create"), {"title": "New", "client": self.cl.pk, "service_type": "design", "template": self.t.pk})
        self.assertEqual(r.status_code, 302)
        p = Proposal.objects.get(title="New")
        self.assertEqual(p.sections.count(), 1)
        for name in ("proposal_detail", "proposal_sections", "proposal_fee", "proposal_schedule", "proposal_preview", "proposal_actuals"):
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

    def test_status_change_requires_project_number_for_won(self):
        p = Proposal.objects.create(title="P")
        r = self.client.post(reverse("proposal_detail", args=[p.pk]), {"title": "P", "service_type": "design", "status": "won", "probability": 50, "project_number": "nope", "contingency_percent": 0})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "must match the company format")
        r = self.client.post(reverse("proposal_detail", args=[p.pk]), {"title": "P", "service_type": "design", "status": "won", "probability": 50, "project_number": "26-007", "contingency_percent": 0})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.project_status, "active")

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
