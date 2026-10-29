from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import CompanyProfile
from proposals.models import ProposalTemplate, Service, StaffRole


class SeedAndCoreTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command("seed", verbosity=0)
        n = (Service.objects.count(), StaffRole.objects.count(), ProposalTemplate.objects.count())
        self.assertGreater(n[0], 10)
        self.assertEqual(ProposalTemplate.objects.filter(is_default=True).count(), 1)
        call_command("seed", verbosity=0)
        self.assertEqual(n, (Service.objects.count(), StaffRole.objects.count(), ProposalTemplate.objects.count()))

    def test_demo_seed_renders_dashboard_and_metrics(self):
        call_command("seed", "--demo", verbosity=0)
        self.client.login(username="admin", password="admin")
        for name in ("dashboard", "metrics", "programme", "proposal_board"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_login_required(self):
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_company_profile_singleton_and_settings_form(self):
        CompanyProfile.get_solo()
        CompanyProfile.get_solo()
        self.assertEqual(CompanyProfile.objects.count(), 1)
        user = get_user_model().objects.create_user("u", password="p")
        self.client.force_login(user)
        r = self.client.post(
            reverse("company_settings"),
            {"name": "Deep Rock", "tagline": "", "primary_color": "#112233", "accent_color": "#445566",
             "proposal_prefix": "DR", "proposal_footer": "", "project_number_pattern": r"^\d{2}-\d{3}$",
             "project_number_example": "26-001", "project_number_help": "", "require_project_number_when_won": "on"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyProfile.get_solo().name, "Deep Rock")
        self.assertContains(self.client.get(reverse("dashboard")), "Deep Rock")


    def test_currency_management(self):
        user = get_user_model().objects.create_user("u2", password="p")
        self.client.force_login(user)
        r = self.client.post(reverse("currency_add"), {"code": "eur", "name": "Euro", "symbol": "€", "rate_to_base": "1.5", "is_active": "on"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "EUR")
        from core.models import Currency

        eur = Currency.objects.get(code="EUR")
        self.client.post(reverse("currency_make_default", args=[eur.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(CompanyProfile.get_solo().default_currency, eur)
        self.assertEqual(eur.format(1234.5), "€1,235")
        self.assertEqual(eur.format(-20, 2), "-€20.00")
