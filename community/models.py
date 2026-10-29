"""Social layer: comments on anything, likes/dislikes that rank tools, profiles
with avatars, skills with self-assessment and peer endorsements, and the
mentor / mentee matching built on them."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Avg, Count, Q


class Comment(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField()
    is_internal = models.BooleanField(default=True, help_text="Internal notes never appear in exports.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"


class Reaction(models.Model):
    """Like / dislike on any object (tools, comments, project sheets…)."""

    UP, DOWN = 1, -1
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions")
    value = models.SmallIntegerField(choices=[(UP, "Like"), (DOWN, "Dislike")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("content_type", "object_id", "user")]

    @classmethod
    def score(cls, obj):
        ct = ContentType.objects.get_for_model(obj)
        qs = cls.objects.filter(content_type=ct, object_id=obj.pk)
        return {"up": qs.filter(value=cls.UP).count(), "down": qs.filter(value=cls.DOWN).count(), "score": sum(qs.values_list("value", flat=True))}


class Rating(models.Model):
    """1–5 star rating with optional review text (tools, uploads)."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings")
    stars = models.PositiveSmallIntegerField()
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("content_type", "object_id", "user")]

    @classmethod
    def summary(cls, obj):
        ct = ContentType.objects.get_for_model(obj)
        agg = cls.objects.filter(content_type=ct, object_id=obj.pk).aggregate(avg=Avg("stars"), n=Count("id"))
        return {"avg": round(agg["avg"] or 0, 1), "n": agg["n"]}


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    title = models.CharField(max_length=120, blank=True, help_text="e.g. Senior Tunnel Engineer")
    office = models.CharField(max_length=60, blank=True, help_text="Salzburg, London, Washington, Toronto, Tel Aviv…")
    bio = models.TextField(blank=True)
    open_to_mentor = models.BooleanField(default=True)
    looking_for_mentor = models.BooleanField(default=True)
    linkedin = models.URLField(blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def initials(self):
        n = (self.user.get_full_name() or self.user.username).split()
        return "".join(p[0] for p in n if p)[:2].upper()


class Skill(models.Model):
    """A competency (SEM design, Plaxis, TBM logistics…). Tagged so it ties to the same vocabulary as projects."""

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=60, blank=True, help_text="Design, Analysis, Site, Software, Management…")
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class UserSkill(models.Model):
    """Self-assessment: what I have, and what I am working on."""

    class Level(models.IntegerChoices):
        AWARE = 1, "Aware"
        WORKING = 2, "Working knowledge"
        PROFICIENT = 3, "Proficient"
        EXPERT = 4, "Expert"
        AUTHORITY = 5, "Recognised authority"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="holders")
    self_level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.WORKING)
    is_learning = models.BooleanField(default=False, help_text="Working on this skill — looking for a mentor.")
    note = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "skill")]
        ordering = ["-self_level", "skill__name"]

    def __str__(self):
        return f"{self.user} · {self.skill} ({self.get_self_level_display()})"

    @property
    def endorsed_level(self):
        agg = self.skill.endorsements.filter(to_user=self.user).aggregate(avg=Avg("level"), n=Count("id"))
        return {"avg": round(agg["avg"] or 0, 1), "n": agg["n"]}

    @property
    def combined_level(self):
        """Self-rating counts once; each endorsement counts once; capped by rules in Endorsement."""
        e = self.endorsed_level
        if not e["n"]:
            return float(self.self_level)
        return round((self.self_level + e["avg"] * e["n"]) / (1 + e["n"]), 1)


class Endorsement(models.Model):
    """Someone vouches for a colleague's skill. Controls: one per (from, to, skill);
    you cannot endorse yourself; a short justification is required; the endorser's
    own level in that skill weights nothing but is shown for context."""

    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="endorsements_given")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="endorsements_received")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="endorsements")
    level = models.PositiveSmallIntegerField(choices=UserSkill.Level.choices)
    context = models.CharField(max_length=200, help_text="Where you saw this skill in action (project, task).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("from_user", "to_user", "skill")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user} → {self.to_user}: {self.skill} {self.level}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.from_user_id and self.from_user_id == self.to_user_id:
            raise ValidationError("You cannot endorse yourself.")


class MentorMatch(models.Model):
    """A mentoring pair agreed by both sides (suggested by skills, confirmed by people)."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        ACTIVE = "active", "Active"
        DONE = "done", "Completed"
        DECLINED = "declined", "Declined"

    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentoring")
    mentee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mentored_by")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("mentor", "mentee", "skill")]

    def __str__(self):
        return f"{self.mentor} mentors {self.mentee} in {self.skill}"


def suggest_mentors(user, limit=10):
    """For each skill the user is learning, people who hold it at a high combined level."""
    out = []
    learning = UserSkill.objects.filter(user=user, is_learning=True).select_related("skill")
    for us in learning:
        holders = (
            UserSkill.objects.filter(skill=us.skill, is_learning=False, self_level__gte=3, user__profile__open_to_mentor=True)
            .exclude(user=user).select_related("user", "user__profile")
        )
        ranked = sorted(holders, key=lambda h: -h.combined_level)[:3]
        if ranked:
            out.append({"skill": us.skill, "mentors": ranked})
    return out[:limit]
