from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

import os
import tempfile

from core.models import AccessRole, CAPABILITY_KEYS, CompanyProfile, Currency, Region
from timesheets.connector import OfficeTimesheetsSync
from timesheets.models import TimesheetConnector
from proposals.models import Employee, FeeItem, FeeLine, Proposal, StaffRole
from timesheets.importer import import_csv
from timesheets.models import ActualEntry


class ImportTests(TestCase):
    def setUp(self):
        cad = Currency.objects.create(code="CAD", name="Canadian dollar", symbol="CA$")
        c = CompanyProfile.get_solo()
        c.default_currency = cad
        c.save()
        role = StaffRole.objects.create(title="Engineer", default_rate=100)
        self.emp = Employee.objects.create(name="Ann Lee", role=role, rate=120, external_id="E42")
        on = Region.objects.create(code="ON", name="Ontario")
        self.p = Proposal.objects.create(title="Won", status="won", region=on, sequence=610, phase="C")  # 610C
        self.item = FeeItem.objects.create(proposal=self.p, code="1", name="Drawings")
        FeeLine.objects.create(item=self.item, kind="labour", employee=self.emp, hours=100)

    def test_csv_import_matches_project_employee_and_item(self):
        csv = (
            "Date,Employee,Project,Task,Hours,ID\n"
            "2026-02-03,Ann Lee,610C,Drawings,7.5,r1\n"
            "03/02/2026,E42,610C,1,2,r2\n"
            "2026-02-04,Unknown Person,99-999,x,1,r3\n"
            "2026-02-05,Ann Lee,610C,,3,r1\n"
        )
        res = import_csv(BytesIO(csv.encode()), source="csv")
        self.assertEqual(res["created"], 2)
        self.assertEqual(res["skipped"], 1)
        self.assertEqual(len(res["errors"]), 1)
        e = ActualEntry.objects.get(external_id="r1")
        self.assertEqual(e.employee, self.emp)
        self.assertEqual(e.item, self.item)
        self.assertEqual(e.cost, Decimal("900"))  # 7.5 h × 120
        self.assertEqual(self.p.actual_hours, Decimal("9.5"))
        self.assertEqual(self.item.actual_hours, Decimal("9.5"))
        self.assertEqual(self.p.hours_variance_pct, -90.5)

    def test_folder_sync_imports_new_files_once_and_filters_phase(self):
        bd = Proposal.objects.create(title="BD pursuit", region=self.p.region, sequence=611)  # B-ON611, phase B
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "export1.csv"), "w") as f:
            f.write("date,employee,project,hours,id\n2026-03-01,Ann Lee,610C,4,x1\n2026-03-01,Ann Lee,B-ON611,2,x2\n")
        cfg = TimesheetConnector.get_solo()
        cfg.transport = "folder"
        cfg.export_folder = folder
        cfg.save()
        run = OfficeTimesheetsSync(cfg).run()
        self.assertEqual((run.status, run.files, run.created), ("ok", 1, 1))
        self.assertEqual(bd.actuals.count(), 0)  # phase B filtered out
        self.assertEqual(self.p.actuals.filter(source="ots").count(), 1)
        run2 = OfficeTimesheetsSync(cfg).run()
        self.assertEqual((run2.files, run2.created), (0, 0))  # same file not re-imported
        cfg.export_folder = "/nonexistent/path"
        cfg.save()
        self.assertEqual(OfficeTimesheetsSync(cfg).run().status, "failed")

    def test_actuals_views(self):
        u = get_user_model().objects.create_user("u", password="p")
        role = AccessRole.objects.create(name="Partners", capabilities=CAPABILITY_KEYS)
        role.users.add(u)
        self.client.force_login(u)
        r = self.client.post(reverse("actual_add", args=[self.p.pk]), {"date": "2026-02-01", "employee": self.emp.pk, "item": self.item.pk, "hours": "4"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.p.actuals.count(), 1)
        f = SimpleUploadedFile("t.csv", b"date,employee,hours\n2026-02-02,Ann Lee,2\n", content_type="text/csv")
        r = self.client.post(reverse("actual_import", args=[self.p.pk]), {"file": f, "source": "csv"})
        self.assertEqual(self.p.actuals.count(), 2)
        r = self.client.get(reverse("proposal_actuals", args=[self.p.pk]))
        self.assertContains(r, "Drawings")
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 200)
        self.assertEqual(self.client.get(reverse("integrations")).status_code, 200)
        r = self.client.post(reverse("integrations_sync"))
        self.assertEqual(r.status_code, 302)
