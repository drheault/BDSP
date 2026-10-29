from django.contrib import admin

from .models import Comment, Endorsement, MentorMatch, Profile, Rating, Reaction, Skill, UserSkill

admin.site.register([Comment, Reaction, Rating, Profile, Endorsement, MentorMatch])


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category")


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ("user", "skill", "self_level", "is_learning")
