"""A single tagging system for everything: services, project sheets, proposals,
records (reports, drawings, calculations, models, presentations), tools, people.

Tags belong to a *category* (discipline, structure type, ground, method,
software, phase, client sector, document type…) so they can be browsed and so
relevance scoring can weight them. Any model becomes taggable by inheriting
`Taggable` and calling `obj.set_tags([...])`."""

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.text import slugify


class TagCategory(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    color = models.CharField(max_length=7, default="#6b7f99")
    weight = models.DecimalField(max_digits=4, decimal_places=2, default=1, help_text="Relevance weight when matching project sheets to proposals.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "tag categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    category = models.ForeignKey(TagCategory, on_delete=models.PROTECT, related_name="tags")
    description = models.CharField(max_length=200, blank=True)
    aliases = models.CharField(max_length=300, blank=True, help_text="Comma-separated synonyms used for auto-tagging and search.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__order", "name"]
        unique_together = [("category", "name")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(f"{self.category.slug}-{self.name}")
        super().save(*args, **kwargs)

    @property
    def usage(self):
        return self.items.count()

    @property
    def alias_list(self):
        return [a.strip().lower() for a in self.aliases.split(",") if a.strip()]


class TaggedItem(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="items")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("tag", "content_type", "object_id")]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.tag} → {self.content_object}"


class Taggable(models.Model):
    """Abstract mixin. Adds `tagged` relation and helpers."""

    tagged = GenericRelation(TaggedItem, related_query_name="%(class)s")

    class Meta:
        abstract = True

    @property
    def tags(self):
        return Tag.objects.filter(items__content_type=ContentType.objects.get_for_model(self), items__object_id=self.pk).select_related("category").distinct()

    @property
    def tag_names(self):
        return ", ".join(t.name for t in self.tags)

    def set_tags(self, names, default_category=None):
        """Replace tags from a list of names; unknown names are created in `default_category` (or 'General')."""
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(self)
        names = [n.strip() for n in names if n and n.strip()]
        keep = []
        for name in names:
            tag = Tag.objects.filter(name__iexact=name).first()
            if tag is None:
                cat = default_category or TagCategory.objects.get_or_create(name="General", defaults={"slug": "general"})[0]
                tag = Tag.objects.create(name=name, category=cat)
            keep.append(tag.pk)
            TaggedItem.objects.get_or_create(tag=tag, content_type=ct, object_id=self.pk)
        TaggedItem.objects.filter(content_type=ct, object_id=self.pk).exclude(tag_id__in=keep).delete()

    def add_tags(self, names, default_category=None):
        current = [t.name for t in self.tags]
        self.set_tags(current + [n for n in names if n not in current], default_category)


def suggest_tags(text: str, limit: int = 12):
    """Auto-tagging: tags whose name or aliases appear in the text."""
    text_l = (text or "").lower()
    if not text_l:
        return []
    hits = []
    for tag in Tag.objects.select_related("category"):
        needles = [tag.name.lower()] + tag.alias_list
        if any(n and n in text_l for n in needles):
            hits.append(tag)
    return hits[:limit]
