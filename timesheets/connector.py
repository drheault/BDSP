"""Office Timesheets sync.

Strategy: sync → adopt → replace.
* **sync** (this module): pull exports from OTS into ActualEntry automatically —
  either from a watched export folder (OTS scheduled export on the LAN share)
  or from an HTTP export endpoint. Runs on demand ("Sync now") or on a
  schedule (`manage.py sync_timesheets`, e.g. from cron / Task Scheduler).
* **adopt**: staff book time in BDSP; the connector pushes back (not built).
* **replace**: retire OTS.

Rows are filtered to projects in the configured phases (default C, D, E) so
BD-phase pursuits never receive billable hours by accident.
"""

import fnmatch
import io
import json
import os
from datetime import timedelta

from django.utils import timezone

from proposals.models import Proposal

from .importer import import_csv
from .models import ProcessedFile, SyncRun, TimesheetConnector


class SyncError(Exception):
    pass


def _rows_to_csv(rows) -> bytes:
    """Turn a JSON list of objects into CSV bytes for the shared importer."""
    import csv

    if not rows:
        return b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


class OfficeTimesheetsSync:
    def __init__(self, config: TimesheetConnector):
        self.config = config
        self.allowed_phases = set(config.only_phases.upper())

    # ---- transports --------------------------------------------------------
    def _folder_files(self):
        folder = self.config.export_folder
        if not folder or not os.path.isdir(folder):
            raise SyncError(f"Export folder not reachable: {folder or '(not set)'}")
        for name in sorted(os.listdir(folder)):
            if not fnmatch.fnmatch(name.lower(), self.config.file_pattern.lower()):
                continue
            full = os.path.join(folder, name)
            st = os.stat(full)
            fp = f"{name}:{st.st_size}:{int(st.st_mtime)}"
            if ProcessedFile.objects.filter(connector=self.config, fingerprint=fp).exists():
                continue
            yield name, full, fp

    def _http_fetch(self) -> bytes:
        import urllib.request

        if not self.config.base_url:
            raise SyncError("Export URL is not set.")
        since = (timezone.localdate() - timedelta(days=self.config.lookback_days)).isoformat()
        url = self.config.base_url + ("&" if "?" in self.config.base_url else "?") + f"since={since}"
        req = urllib.request.Request(url, headers={"Accept": "text/csv, application/json"})
        if self.config.api_key:
            req.add_header("Authorization", f"Bearer {self.config.api_key}")
        if self.config.username:
            import base64

            token = base64.b64encode(f"{self.config.username}:{self.config.password}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
        except Exception as e:  # network, auth, DNS…
            raise SyncError(f"HTTP export failed: {e}") from e
        if "json" in ctype or body[:1] in (b"[", b"{"):
            data = json.loads(body.decode("utf-8-sig"))
            rows = data.get("rows") or data.get("data") or data if isinstance(data, dict) else data
            return _rows_to_csv(rows)
        return body

    # ---- import with phase filter -----------------------------------------
    def _import(self, data: bytes, log: list):
        res = import_csv(io.BytesIO(data), source=self.config.kind)
        # drop entries created for projects outside the allowed phases
        from .models import ActualEntry

        bad = ActualEntry.objects.filter(source=self.config.kind, created_at__gte=self._started).exclude(proposal__phase__in=self.allowed_phases)
        dropped = bad.count()
        if dropped:
            log.append(f"Dropped {dropped} rows for projects outside phases {''.join(sorted(self.allowed_phases))}")
            bad.delete()
        res["created"] -= dropped
        return res

    # ---- entry point ------------------------------------------------------
    def run(self, trigger="manual") -> SyncRun:
        run = SyncRun.objects.create(connector=self.config, trigger=trigger)
        self._started = run.started_at
        log, files = [], 0
        try:
            if self.config.transport == TimesheetConnector.Transport.FOLDER:
                for name, full, fp in self._folder_files():
                    with open(full, "rb") as f:
                        res = self._import(f.read(), log)
                    ProcessedFile.objects.create(connector=self.config, name=name, fingerprint=fp)
                    files += 1
                    run.created += res["created"]
                    run.skipped += res["skipped"]
                    run.errors += len(res["errors"])
                    log.append(f"{name}: {res['created']} created, {res['skipped']} skipped, {len(res['errors'])} errors")
                    log.extend("  " + e for e in res["errors"][:20])
                if files == 0:
                    log.append("No new export files found.")
            else:
                res = self._import(self._http_fetch(), log)
                files = 1
                run.created, run.skipped, run.errors = res["created"], res["skipped"], len(res["errors"])
                log.append(f"HTTP export: {res['created']} created, {res['skipped']} skipped, {len(res['errors'])} errors")
                log.extend("  " + e for e in res["errors"][:20])
            run.status = SyncRun.Status.PARTIAL if run.errors else SyncRun.Status.OK
        except SyncError as e:
            run.status = SyncRun.Status.FAILED
            log.append(str(e))
        except Exception as e:  # pragma: no cover - defensive
            run.status = SyncRun.Status.FAILED
            log.append(f"Unexpected error: {e!r}")
        run.files = files
        run.finished_at = timezone.now()
        run.log = "\n".join(log)
        run.save()
        self.config.last_synced_at = run.finished_at
        self.config.last_result = f"{run.get_status_display()}: {run.created} created, {run.skipped} skipped, {run.errors} errors"
        self.config.save(update_fields=["last_synced_at", "last_result"])
        return run


def sync_now(trigger="manual") -> SyncRun:
    return OfficeTimesheetsSync(TimesheetConnector.get_solo()).run(trigger=trigger)
