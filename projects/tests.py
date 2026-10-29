from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
import tempfile

from projects.models import PastProject

MEDIA = tempfile.mkdtemp()


def _png():
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (20, 20), (10, 20, 30)).save(buf, format="PNG")
    return SimpleUploadedFile("t.png", buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA)
class ProjectTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("u", password="p"))

    def test_create_upload_cover_delete(self):
        r = self.client.post(reverse("project_create"), {"name": "Riverside", "kind": "tunnel", "client_name": "Metro", "highlights": "a\nb"})
        self.assertEqual(r.status_code, 302)
        pr = PastProject.objects.get()
        self.assertEqual(pr.highlight_list, ["a", "b"])
        r = self.client.post(reverse("image_add", args=[pr.pk]), {"images": [_png(), _png()], "caption": "cap"}, HTTP_HX_REQUEST="true")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(pr.images.count(), 2)
        second = pr.images.last()
        self.client.post(reverse("image_cover", args=[second.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(pr.cover.pk, second.pk)
        self.assertEqual(self.client.get(reverse("project_detail", args=[pr.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse("project_list"), {"kind": "tunnel"}, HTTP_HX_REQUEST="true"), "Riverside")
        self.client.post(reverse("image_delete", args=[second.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(pr.images.count(), 1)
