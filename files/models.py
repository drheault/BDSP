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

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.MOUNT)
    path = models.CharField(max_length=500, help_text="Local path (e.g. /mnt/projects or P:\\Projects) or UNC path (\\\\server\\share\\Projects).")
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=100, blank=True)
    allow_upload = models.BooleanField(default=True)
    project_folder_template = models.CharField(
        max_length=255, blank=True, default="{phase_name}/{project_number}",
        help_text="Relative folder of a project inside this root. Placeholders: {project_number}, {phase}, {phase_name}, {region}, {seq}.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


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
