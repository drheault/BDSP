from django.db import models


class CompanyProfile(models.Model):
    """Singleton holding the firm's identity: name, logo, contact details, colours."""

    name = models.CharField(max_length=200, default="Your Engineering Firm")
    tagline = models.CharField(
        max_length=200, blank=True, default="Tunnels & Underground Structures"
    )
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#0f3d5e")
    accent_color = models.CharField(max_length=7, default="#e07a1f")
    proposal_footer = models.CharField(
        max_length=255,
        blank=True,
        default="Confidential — prepared for the exclusive use of the addressee.",
    )
    proposal_prefix = models.CharField(max_length=10, default="P")

    class Meta:
        verbose_name = "Company profile"

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
