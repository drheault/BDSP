from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import CompanyProfile
from crm.models import Client, Contact
from proposals.models import Proposal, ProposalStaffing, ProposalTemplate, StaffRole, TemplateSection


class ProposalModelTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(name="Metro")
        self.contact = Contact.objects.create(client=self.client_obj, name="Dana")
        self.role = StaffRole.objects.create(title="Engineer", default_rate=Decimal("150"))

    def test_numbering_increments_per_year(self):
        p1 = Proposal.objects.create(title="A")
        p2 = Proposal.objects.create(title="B")
        self.assertTrue(p1.number.endswith("-001"))
        self.assertTrue(p2.number.endswith("-002"))
        self.assertTrue(p1.number.startswith(CompanyProfile.get_solo().proposal_prefix + "-"))

    def test_fee_totals(self):
        p = Proposal.objects.create(title="A", expenses=Decimal("1000"), markup_percent=Decimal("10"), probability=50)
        ProposalStaffing.objects.create(proposal=p, role=self.role, hours=Decimal("10"))
        line = p.staffing.first()
        self.assertEqual(line.rate, Decimal("150"))  # default rate copied
        self.assertEqual(p.labour_total, Decimal("1500"))
        self.assertEqual(p.expenses_total, Decimal("1100"))
        self.assertEqual(p.fee_total, Decimal("2600"))
        self.assertEqual(p.weighted_value, Decimal("1300"))
        p.manual_value = Decimal("5000")
        self.assertEqual(p.fee_total, Decimal("5000"))

    def test_placeholders_and_template_apply(self):
        t = ProposalTemplate.objects.create(name="T")
        TemplateSection.objects.create(template=t, order=0, title="Intro", body="Dear {{contact_name}} of {{client_name}}, re {{project_name}} {{unknown}}")
        p = Proposal.objects.create(title="Tunnel", client=self.client_obj, contact=self.contact)
        p.apply_template(t)
        self.assertEqual(p.sections.count(), 1)
        self.assertEqual(p.sections.first().rendered_body, "Dear Dana of Metro, re Tunnel {{unknown}}")

    def test_status_sets_dates(self):
        p = Proposal.objects.create(title="A", status="submitted")
        self.assertIsNotNone(p.submitted_at)
        p.status = "won"
        p.save()
        self.assertIsNotNone(p.decided_at)


class ProposalViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.cl = Client.objects.create(name="Metro")
        self.t = ProposalTemplate.objects.create(name="T", is_default=True)
        TemplateSection.objects.create(template=self.t, order=0, title="Intro", body="Hi {{client_name}}")
        self.role = StaffRole.objects.create(title="Engineer", default_rate=100)

    def test_create_from_template_and_pages(self):
        r = self.client.post(reverse("proposal_create"), {"title": "New", "client": self.cl.pk, "service_type": "design", "template": self.t.pk})
        self.assertEqual(r.status_code, 302)
        p = Proposal.objects.get(title="New")
        self.assertEqual(p.sections.count(), 1)
        for name in ("proposal_detail", "proposal_sections", "proposal_fee", "proposal_schedule", "proposal_preview"):
            self.assertEqual(self.client.get(reverse(name, args=[p.pk])).status_code, 200, name)
        self.assertContains(self.client.get(reverse("proposal_preview", args=[p.pk])), "Hi Metro")

    def test_htmx_section_and_staffing_flow(self):
        p = Proposal.objects.create(title="P")
        r = self.client.post(reverse("section_add", args=[p.pk]), {"title": "Scope"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        s = p.sections.get()
        r = self.client.post(reverse("section_edit", args=[s.pk]), {"title": "Scope", "body": "Body text"})
        self.assertContains(r, "Body text")
        r = self.client.post(reverse("staffing_add", args=[p.pk]), {"role": self.role.pk, "task": "QA", "hours": "5"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "QA")
        self.assertEqual(p.fee_total, Decimal("500"))
        r = self.client.post(reverse("staffing_delete", args=[p.staffing.get().pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(p.staffing.count(), 0)

    def test_status_change_and_board(self):
        p = Proposal.objects.create(title="P")
        r = self.client.post(reverse("proposal_status", args=[p.pk]), {"status": "won", "render": "row"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "won")
        self.assertContains(self.client.get(reverse("proposal_board")), "P")

    def test_library_role_delete_deactivates_when_used(self):
        p = Proposal.objects.create(title="P")
        ProposalStaffing.objects.create(proposal=p, role=self.role, hours=1)
        self.client.post(reverse("role_delete", args=[self.role.pk]), HTTP_HX_REQUEST="true")
        self.role.refresh_from_db()
        self.assertFalse(self.role.is_active)
