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


class SpecTests(TestCase):
    def test_safe_eval_blocks_unsafe_and_runs_example(self):
        from calcs.spec import EXAMPLE_SPEC, SpecError, safe_eval, validate_spec

        self.assertEqual(safe_eval("w*L**2/8", {"w": 10, "L": 8}), 80)
        for bad in ("__import__('os')", "open('x')", "(1).__class__", "L.real", "lambda: 1"):
            with self.assertRaises((SpecError, SyntaxError)):
                safe_eval(bad, {"L": 1})
        self.assertTrue(validate_spec(EXAMPLE_SPEC))
        with self.assertRaises(SpecError):
            validate_spec({"inputs": [{"name": "x"}], "formulas": [{"name": "y", "expr": "zz+1"}]})


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


    def test_live_run_state_params_and_spec_builder(self):
        import json

        from calcs.models import ProjectParams, Tool, ToolState
        from calcs.spec import EXAMPLE_SPEC
        from core.models import Currency
        from proposals.models import Proposal

        Currency.objects.create(code="CAD", name="Canadian dollar", symbol="CA$")
        ensure_builtins()
        p = Proposal.objects.create(title="P")
        # project parameters feed the face-stability tool
        r = self.client.post(reverse("project_params", args=[p.pk]), {"tunnel_diameter": "8.5", "cover": "20", "cu": "80"})
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse("tool_detail", args=["face_stability"]) + f"?proposal={p.pk}")
        self.assertContains(r, 'value="8.5"')
        self.assertContains(r, "Results")  # live-rendered on open
        # live recalculation endpoint + autosaved state
        eng = REGISTRY["face_stability"]
        data = {i.name: i.default for i in eng.inputs}
        data["D"] = 9
        r = self.client.post(reverse("tool_live", args=["face_stability"]), data, HTTP_HX_REQUEST="true")
        self.assertContains(r, "Undrained stability number")
        self.assertEqual(ToolState.objects.get(tool__key="face_stability", user=self.u).inputs["D"], 9)
        # save inputs back to the project
        data["proposal"] = p.pk
        data["save_params"] = "1"
        self.client.post(reverse("tool_detail", args=["face_stability"]), data)
        self.assertEqual(ProjectParams.objects.get(proposal=p).values["tunnel_diameter"], 9)
        # no-code tool
        r = self.client.post(reverse("spec_builder"), {"name": "Waler", "category": "Temporary works", "summary": "s", "description": "", "version": "1", "tags": "", "spec_text": json.dumps(EXAMPLE_SPEC)})
        self.assertEqual(r.status_code, 302)
        t = Tool.objects.get(name="Waler")
        self.assertEqual(t.kind, "spec")
        r = self.client.post(reverse("tool_live", args=[t.key]), {"L": 8, "w": 10}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "80.0")
        self.assertContains(r, "Bending moment")
        r = self.client.post(reverse("spec_builder"), {"name": "Bad", "category": "x", "summary": "s", "description": "", "version": "1", "tags": "", "spec_text": json.dumps({"inputs": [{"name": "a"}], "formulas": [{"name": "b", "expr": "__import__('os')"}]})})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Tool.objects.filter(name="Bad").exists())
