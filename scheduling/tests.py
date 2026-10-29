from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proposals.models import Proposal
from scheduling.gantt import build_gantt, create_default_tasks
from scheduling.models import Task


class GanttTests(TestCase):
    def setUp(self):
        self.p = Proposal.objects.create(title="P", service_type="design")

    def test_build_gantt_geometry(self):
        self.assertIsNone(build_gantt([]))
        a = Task.objects.create(proposal=self.p, name="A", start=date(2026, 1, 5), end=date(2026, 1, 16))
        b = Task.objects.create(proposal=self.p, name="B", start=date(2026, 1, 19), end=date(2026, 1, 19), is_milestone=True, predecessor=a)
        g = build_gantt([a, b], today=date(2026, 1, 10))
        self.assertEqual(len(g["rows"]), 2)
        self.assertEqual(len(g["deps"]), 1)
        self.assertIsNotNone(g["today_x"])
        self.assertLess(g["rows"][0]["x"], g["rows"][1]["x"])
        self.assertTrue(g["rows"][1]["is_milestone"])

    def test_default_schedule_and_shift(self):
        created = create_default_tasks(self.p, date(2026, 3, 2))
        self.assertGreater(len(created), 5)
        self.assertTrue(any(t.is_milestone for t in created))
        first = created[0]
        first.shift(7)
        self.assertEqual(first.start, date(2026, 3, 9))


class ScheduleViewTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("u", "u@x.com", "p"))
        self.p = Proposal.objects.create(title="P")

    def test_add_edit_cascade_delete(self):
        r = self.client.post(reverse("task_add", args=[self.p.pk]), {"name": "Design", "phase": "detailed", "start": "2026-02-02", "end": "2026-02-27"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        a = self.p.tasks.get()
        r = self.client.post(reverse("task_add", args=[self.p.pk]), {"name": "Submit", "phase": "detailed", "start": "2026-03-02", "is_milestone": "on", "predecessor": a.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        b = self.p.tasks.get(name="Submit")
        self.assertEqual(b.end, b.start)
        self.client.post(reverse("task_shift", args=[a.pk]), {"days": 7, "cascade": 1}, HTTP_HX_REQUEST="true")
        b.refresh_from_db()
        self.assertEqual(b.start, date(2026, 3, 9))
        r = self.client.post(reverse("task_add", args=[self.p.pk]), {"name": "Bad", "phase": "other", "start": "2026-03-10", "end": "2026-03-01"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 422)
        self.client.post(reverse("task_delete", args=[a.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(self.p.tasks.count(), 1)

    def test_defaults_endpoint_and_programme(self):
        r = self.client.post(reverse("schedule_defaults", args=[self.p.pk]), {"start": "2026-05-04"})
        self.assertEqual(r.status_code, 302)
        self.assertGreater(self.p.tasks.count(), 0)
        self.assertContains(self.client.get(reverse("programme")), self.p.number)
