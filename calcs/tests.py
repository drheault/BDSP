from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from calcs.engines import REGISTRY
from calcs.models import CalcRun, Tool
from calcs.views import ensure_builtins


class EngineTests(TestCase):
    def test_all_engines_run_with_defaults(self):
        for key, eng in REGISTRY.items():
            res = eng.run({i.name: i.default for i in eng.inputs})
            self.assertTrue(res["results"], key)
            self.assertTrue(res["checks"], key)

    def test_face_stability_numbers(self):
        eng = REGISTRY["face_stability"]
        res = eng.run({"D": 6, "C": 12, "gamma": 20, "sigma_s": 0, "cu": 50, "c": 0, "phi": 30, "hw": 0, "sigma_T": 100, "fos": 1.5})
        n = dict((r[0], r[1]) for r in res["results"])
        self.assertEqual(n["Undrained stability number N"], "4.00")  # (0 + 20*15 - 100)/50
        self.assertAlmostEqual(float(n["Drained effective support p_f (collapse)"]), 20 * 6 * (1 / (9 * 0.57735) - 0.05), places=0)

    def test_beam_simply_supported_udl(self):
        res = REGISTRY["beam"].run({"support": 0, "L": 8, "w": 10, "P": 0, "a": 4, "E": 200, "I": 10000})
        mmax = float(dict((r[0], r[1]) for r in res["results"])["Max |M|"].split()[0])
        self.assertAlmostEqual(mmax, 80.0, places=1)  # wL²/8


class ToolViewTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_superuser("u", "u@x.com", "p")
        self.client.force_login(self.u)

    def test_list_run_save_rate_upload(self):
        r = self.client.get(reverse("tool_list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Tool.objects.filter(kind="builtin").count(), len(REGISTRY))
        eng = REGISTRY["rc_section"]
        data = {i.name: i.default for i in eng.inputs}
        data["save_title"] = "Lining section check"
        r = self.client.post(reverse("tool_detail", args=["rc_section"]), data)
        self.assertContains(r, "M_Rd")
        self.assertEqual(CalcRun.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("run_detail", args=[CalcRun.objects.get().pk])).status_code, 200)
        from django.contrib.contenttypes.models import ContentType

        t = Tool.objects.get(key="rc_section")
        r = self.client.post(reverse("rate", args=[ContentType.objects.get_for_model(t).pk, t.pk]), {"stars": 4, "review": "Handy", "next": "/calcs/"})
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("tool_upload"), {"name": "Waler check", "category": "Temporary works", "summary": "Spreadsheet", "description": "", "url": "https://example.com/sheet", "version": "1", "tags": "Temporary works, Drawing"})
        self.assertEqual(r.status_code, 302)
        up = Tool.objects.get(name="Waler check")
        self.assertEqual(up.kind, "link")
        self.assertEqual({t.name for t in up.tags}, {"Temporary works", "Drawing"})
