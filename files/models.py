"""File server access. A *root* is a folder the web server can see: a locally
mounted SMB share (recommended on the LAN) or a UNC path reached through the
smbprotocol client with stored credentials. Browsing, upload, download and a
sync that indexes a project's folder into project records all go through here."""

from django.conf import settings
from django.db import models


class FileRoot(models.Model):
    class Kind(models.TextChoices):
        MOUNT = "mount", "Mounted folder (local path)"
        SMB = "smb", "SMB share (UNC path + credentials)"

    class Purpose(models.TextChoices):
        PROJECTS = "projects", "Project folders (phases C / D / E)"
        BD = "bd", "Business development (phase B)"
        SHEETS = "sheets", "Printed material / project sheets"
        OTHER = "other", "Other"

    name = models.CharField(max_length=80)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.PROJECTS)
    phases = models.CharField(max_length=5, default="CDE", help_text="Which phases this location serves, e.g. B or CDE.")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MOUNT)
    path = models.CharField(max_length=500, help_text="Local path (e.g. /mnt/projects or P:\\Projects) or UNC path (\\\\server\\share\\Projects).")
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=100, blank=True)
    allow_upload = models.BooleanField(default=True)
    project_folder_template = models.CharField(
        max_length=255, blank=True, default="{country}/{project_number}",
        help_text="Relative folder of a project inside this root. Placeholders: {country}, {region}, {seq}, {seq4}, {phase}, {phase_lower}, {phase_name}, {project_number}, {number}.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def context_for(self, proposal):
        region = proposal.region
        return {
            "country": (region.country if region else "canada"), "region": (region.code if region else ""), "seq": proposal.sequence or "",
            "seq4": f"{proposal.sequence:04d}" if proposal.sequence else "", "phase": proposal.phase, "phase_lower": proposal.phase.lower(),
            "phase_name": proposal.phase_name, "project_number": proposal.project_number or proposal.number, "number": proposal.number,
        }

    def relative_folder(self, proposal) -> str:
        try:
            return (self.project_folder_template or "{project_number}").format(**self.context_for(proposal)).strip("/\\")
        except (KeyError, IndexError, ValueError):
            return proposal.project_number or proposal.number

    def full_path(self, proposal) -> str:
        rel = self.relative_folder(proposal)
        if self.kind == "smb" or self.path.startswith("\\\\"):
            return self.path.rstrip("\\/") + "\\" + rel.replace("/", "\\")
        return self.path.rstrip("/") + "/" + rel

    @classmethod
    def for_proposal(cls, proposal):
        """The active root whose phases include the proposal's phase (first by order)."""
        for root in cls.objects.filter(is_active=True):
            if proposal.phase in (root.phases or "").upper():
                return root
        return None


class SyncLog(models.Model):
    root = models.ForeignKey(FileRoot, on_delete=models.CASCADE, related_name="syncs")
    proposal = models.ForeignKey("proposals.Proposal", on_delete=models.CASCADE, null=True, blank=True, related_name="file_syncs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    files_seen = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
