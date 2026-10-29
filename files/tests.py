import os
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Region
from files.models import FileRoot
from proposals.models import Proposal


class FileTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("u", "u@x.com", "p"))
        self.dir = tempfile.mkdtemp()
        self.root = FileRoot.objects.create(name="Share", kind="mount", path=self.dir, project_folder_template="{phase_name}/{project_number}")
        on = Region.objects.create(code="ON", name="Ontario")
        self.p = Proposal.objects.create(title="P", region=on, sequence=640, phase="E", status="won")  # 640E
        os.makedirs(os.path.join(self.dir, "Execution", "640E", "Site visits"))
        with open(os.path.join(self.dir, "Execution", "640E", "Site visits", "SVR-001.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 test")

    def test_browse_download_upload_and_sync(self):
        r = self.client.get(reverse("file_home"))
        self.assertContains(r, "reachable")
        r = self.client.get(reverse("file_browse", args=[self.root.pk, "Execution/640E"]))
        self.assertContains(r, "Site visits")
        r = self.client.get(reverse("file_download", args=[self.root.pk, "Execution/640E/Site visits/SVR-001.pdf"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("file_browse", args=[self.root.pk, "../../etc"])).status_code, 200)  # traversal is clamped to root
        from django.core.files.uploadedfile import SimpleUploadedFile

        r = self.client.post(reverse("file_upload", args=[self.root.pk]), {"rel": "Execution/640E", "files": SimpleUploadedFile("photo.jpg", b"img"), "folder": "Photos"})
        self.assertTrue(os.path.exists(os.path.join(self.dir, "Execution", "640E", "photo.jpg")))
        self.assertTrue(os.path.isdir(os.path.join(self.dir, "Execution", "640E", "Photos")))
        r = self.client.post(reverse("sync_project", args=[self.p.pk]), {"root": self.root.pk})
        self.assertEqual(r.status_code, 302)
        kinds = {rec.kind for rec in self.p.records.all()}
        self.assertIn("site_visit", kinds)
        self.assertEqual(self.p.records.count(), 2)
        self.client.post(reverse("sync_project", args=[self.p.pk]), {"root": self.root.pk})
        self.assertEqual(self.p.records.count(), 2)  # idempotent
