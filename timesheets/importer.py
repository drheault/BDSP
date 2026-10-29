"""CSV / Office-Timesheets import into ActualEntry.

Expected columns (header names are matched case-insensitively, extra columns
are ignored): date, employee, hours, and optionally project_number, task,
cost, description, id. Rows are matched to proposals by project_number
(preferred) or the proposal supplied by the caller.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from proposals.models import Employee, FeeItem, Proposal

from .models import ActualEntry

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")
ALIASES = {
    "date": {"date", "day", "work date", "workdate"},
    "employee": {"employee", "name", "resource", "person", "staff", "employee name"},
    "hours": {"hours", "hrs", "time", "duration"},
    "project_number": {"project_number", "project", "project no", "project no.", "job", "job number", "project code"},
    "task": {"task", "item", "wbs", "activity", "phase", "deliverable"},
    "cost": {"cost", "amount", "value"},
    "description": {"description", "notes", "comment", "comments", "memo"},
    "id": {"id", "entry id", "row id", "external_id", "uid"},
}


def _parse_date(s):
    s = (s or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _dec(s):
    try:
        return Decimal(str(s).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _normalise(headers):
    out = {}
    for h in headers:
        key = (h or "").strip().lower()
        for canon, names in ALIASES.items():
            if key in names:
                out[h] = canon
    return out


def import_csv(file_obj, source="csv", default_proposal=None):
    raw = file_obj.read()
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    reader = csv.DictReader(io.StringIO(text))
    mapping = _normalise(reader.fieldnames or [])
    created, skipped, errors = 0, 0, []
    employees = {e.name.lower(): e for e in Employee.objects.all()}
    ext_ids = {e.initials.lower(): e for e in Employee.objects.exclude(initials="")}
    ext_ids.update({e.external_id.lower(): e for e in Employee.objects.exclude(external_id="")})

    for i, raw_row in enumerate(reader, start=2):
        row = {mapping.get(k, k): (v or "").strip() for k, v in raw_row.items() if k is not None}
        date = _parse_date(row.get("date"))
        hours = _dec(row.get("hours"))
        if not date or hours is None:
            errors.append(f"Row {i}: missing/invalid date or hours")
            continue
        proposal = default_proposal
        pn = row.get("project_number")
        if pn:
            proposal = Proposal.objects.filter(project_number__iexact=pn).first() or Proposal.objects.filter(number__iexact=pn).first() or proposal
        if proposal is None:
            errors.append(f"Row {i}: no proposal for project number '{pn}'")
            continue
        ext = row.get("id", "")
        if ext and ActualEntry.objects.filter(source=source, external_id=ext).exists():
            skipped += 1
            continue
        name = row.get("employee", "")
        emp = employees.get(name.lower()) or ext_ids.get(name.lower())
        item = None
        task = row.get("task", "")
        if task:
            item = FeeItem.objects.filter(proposal=proposal).filter(name__iexact=task).first() or FeeItem.objects.filter(proposal=proposal, code__iexact=task).first()
        ActualEntry.objects.create(
            proposal=proposal, item=item, employee=emp, employee_name=name, date=date, hours=hours,
            cost=_dec(row.get("cost")) if row.get("cost") else None, description=row.get("description", "")[:255],
            source=source, external_id=ext,
        )
        created += 1
    return {"created": created, "skipped": skipped, "errors": errors}
