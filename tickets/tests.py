from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from community.models import Profile
from core.models import AccessRole, Office
from tickets.models import Notification, Request, RequestKind


class RequestTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.it = AccessRole.objects.create(name="IT", capabilities=["manage_settings"])
        self.hr = AccessRole.objects.create(name="HR-Global", capabilities=["edit_profiles"])
        self.handler = U.objects.create_user("itguy", password="p", email="it@dr-sauer.com")
        self.it.users.add(self.handler)
        Profile.objects.create(user=self.handler, notify_email=True)
        self.hr_user = U.objects.create_user("hr", password="p", email="hr@dr-sauer.com")
        self.hr.users.add(self.hr_user)
        Profile.objects.create(user=self.hr_user)
        self.user = U.objects.create_user("eng", password="p", email="e@dr-sauer.com")
        Profile.objects.create(user=self.user)
        RequestKind.objects.create(key="access", name="Access", handled_by=self.it)
        self.profile_kind = RequestKind.objects.create(key="profile", name="Profile change", handled_by=self.hr)
        self.tor = Office.objects.create(code="DSP-Toronto", name="Toronto")

    def test_request_flow_notifies_group_and_requester(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("request_create"), {"kind": RequestKind.objects.get(key="access").pk, "title": "Need Metrics", "details": "please", "priority": "normal"})
        self.assertEqual(r.status_code, 302)
        req = Request.objects.get()
        self.assertEqual(req.number, 101)
        self.assertEqual(Notification.objects.filter(user=self.handler).count(), 1)
        self.assertEqual(len(mail.outbox), 1)  # handler prefers email
        self.assertEqual(self.client.get(reverse("request_detail", args=[req.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("request_update", args=[req.pk]), {"status": "done", "priority": "normal", "resolution": "granted"}).status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, "open")  # requester cannot triage
        self.client.force_login(self.handler)
        self.client.post(reverse("request_update", args=[req.pk]), {"status": "done", "priority": "normal", "resolution": "granted", "note": "done"})
        req.refresh_from_db()
        self.assertEqual(req.status, "done")
        self.assertTrue(Notification.objects.filter(user=self.user).exists())
        r = self.client.get(reverse("request_list") + "?status=done")
        self.assertContains(r, "Need Metrics")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("notifications")), "done")
        self.client.post(reverse("notifications_read"))
        self.assertEqual(Notification.objects.filter(user=self.user, read_at__isnull=True).count(), 0)

    def test_profile_change_request_applies_on_done(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("my_profile"))
        self.assertContains(r, "Request a change")
        self.assertContains(r, 'disabled')  # office locked
        r = self.client.post(reverse("request_create"), {"kind": self.profile_kind.pk, "title": "Move me", "details": "relocating", "priority": "normal", "on_behalf_of": self.user.pk, "pl_office": self.tor.pk, "pl_title": "Engineer II"})
        req = Request.objects.get()
        self.assertEqual(req.payload["office"], str(self.tor.pk))
        self.client.force_login(self.hr_user)
        self.client.post(reverse("request_update", args=[req.pk]), {"status": "done", "priority": "normal", "resolution": "ok"})
        prof = Profile.objects.get(user=self.user)
        self.assertEqual((prof.office, prof.title), (self.tor, "Engineer II"))
        # HR can edit profiles directly, engineer cannot edit others
        self.assertEqual(self.client.get(reverse("person_edit", args=[self.user.pk])).status_code, 200)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("person_edit", args=[self.hr_user.pk])).status_code, 302)
