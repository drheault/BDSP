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
        self.assertContains(self.client.get(reverse("dashboard")), "Sign in")  # public landing page
        r = self.client.get(reverse("proposal_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_company_profile_singleton_and_settings_form(self):
        CompanyProfile.get_solo()
        CompanyProfile.get_solo()
        self.assertEqual(CompanyProfile.objects.count(), 1)
        user = get_user_model().objects.create_superuser("u", "u@x.com", "p")
        self.client.force_login(user)
        r = self.client.post(
            reverse("company_settings"),
            {"name": "Deep Rock", "tagline": "", "primary_color": "#112233", "accent_color": "#445566",
             "proposal_prefix": "DR", "proposal_footer": "", "number_digits": 3, "sequence_start": 601,
             "bd_number_format": "B-{region}{seq}", "phase_number_format": "{seq}{phase}", "require_project_number_when_won": "on",
             "smb_path_template": "", "notes_server": "", "notes_database": "", "landing_visual": "analysis_loop"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CompanyProfile.get_solo().name, "Deep Rock")
        self.assertContains(self.client.get(reverse("dashboard")), "Deep Rock")


    def test_roles_users_and_capabilities(self):
        from core.models import AccessRole, user_capabilities

        admin = get_user_model().objects.create_superuser("adm", "a@x.com", "p")
        self.client.force_login(admin)
        r = self.client.post(reverse("role_create"), {"name": "Estimators", "rank": 35, "description": "", "capabilities": ["view_proposals", "edit_proposals"]})
        self.assertEqual(r.status_code, 302)
        role = AccessRole.objects.get(name="Estimators")
        r = self.client.post(reverse("user_create"), {"username": "sam", "first_name": "Sam", "last_name": "Q", "email": "", "password": "secret123", "is_active": "on", "roles": [role.pk]})
        self.assertEqual(r.status_code, 302)
        sam = get_user_model().objects.get(username="sam")
        self.assertTrue(sam.check_password("secret123"))
        self.assertEqual(user_capabilities(sam), {"view_proposals", "edit_proposals"})
        self.assertEqual(self.client.get(reverse("roles")).status_code, 200)
        self.assertEqual(self.client.get(reverse("users")).status_code, 200)
        self.client.force_login(sam)
        self.assertEqual(self.client.get(reverse("roles")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("dashboard")), "Company settings")

    def test_currency_management(self):
        user = get_user_model().objects.create_superuser("u2", "u2@x.com", "p")
        self.client.force_login(user)
        r = self.client.post(reverse("currency_add"), {"code": "eur", "name": "Euro", "symbol": "€", "rate_to_base": "1.5", "is_active": "on"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "EUR")
        from core.models import Currency

        eur = Currency.objects.get(code="EUR")
        self.client.post(reverse("currency_make_default", args=[eur.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(CompanyProfile.get_solo().default_currency, eur)
        self.assertEqual(eur.format(1234.5), "€1,235")
        self.assertEqual(eur.format(-20, 2), "-€20.00")


    def test_dashboard_widgets_scoping_and_customise(self):
        from community.models import Profile
        from core.models import AccessRole, Office
        from proposals.models import Proposal

        tor = Office.objects.create(code="DSP-Toronto", name="Toronto")
        lon = Office.objects.create(code="DSP-London", name="London")
        U = get_user_model()
        partner = U.objects.create_user("pt", password="p")
        AccessRole.objects.create(name="Partners", capabilities=["view_proposals", "view_all_offices", "view_actuals"]).users.add(partner)
        local = U.objects.create_user("lc", password="p")
        AccessRole.objects.create(name="Associates", capabilities=["view_proposals"]).users.add(local)
        Profile.objects.create(user=local, office=tor)
        Proposal.objects.create(title="Toronto job", office=tor)
        Proposal.objects.create(title="London job", office=lon)
        self.client.force_login(partner)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "London job")
        self.assertContains(r, "Offices")
        self.client.force_login(local)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Toronto job")
        self.assertNotContains(r, "London job")
        self.assertNotContains(r, 'id="w-offices"')
        r = self.client.post(reverse("dashboard_customize"), {"widget": ["weather", "top_tools"], "order": "top_tools,weather"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Profile.objects.get(user=local).dashboard, ["top_tools", "weather"])
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, 'id="w-top_tools"')
        self.assertNotContains(r, 'id="w-pipeline"')
        self.client.post(reverse("dashboard_customize"), {"reset": "1"})
        self.assertEqual(Profile.objects.get(user=local).dashboard, [])


    def test_landing_visual_options_render(self):
        for v in ("analysis_loop", "shotcrete", "advance", "drawing_photo"):
            r = self.client.get(reverse("dashboard") + f"?visual={v}")
            self.assertEqual(r.status_code, 200, v)
        self.assertContains(self.client.get(reverse("dashboard") + "?visual=analysis_loop"), "fe-mesh")
