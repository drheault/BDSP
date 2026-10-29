from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from crm.models import Client, Contact
from proposals.models import Proposal


class CrmTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("u", "u@x.com", "p"))

    def test_client_crud_and_contacts(self):
        r = self.client.post(reverse("client_create"), {"name": "Metro", "sector": "public"})
        self.assertEqual(r.status_code, 302)
        cl = Client.objects.get(name="Metro")
        r = self.client.post(reverse("contact_add", args=[cl.pk]), {"name": "Dana", "email": "d@x.org"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "Dana")
        c = cl.contacts.get()
        r = self.client.post(reverse("contact_edit", args=[c.pk]), {"name": "Dana W", "email": "d@x.org"})
        self.assertContains(r, "Dana W")
        self.assertContains(self.client.get(reverse("client_list"), {"q": "dana"}, HTTP_HX_REQUEST="true"), "Metro")
        self.assertEqual(self.client.get(reverse("contact_options"), {"client": cl.pk}).content.count(b"<option"), 2)
        self.client.post(reverse("contact_delete", args=[c.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(Contact.objects.count(), 0)

    def test_cannot_delete_client_with_proposals(self):
        cl = Client.objects.create(name="Metro")
        Proposal.objects.create(title="P", client=cl)
        self.client.post(reverse("client_delete", args=[cl.pk]))
        self.assertTrue(Client.objects.filter(pk=cl.pk).exists())
