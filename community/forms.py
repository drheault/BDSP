from django import forms

from .models import Comment, Endorsement, Profile, Rating, Skill, UserSkill


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Add a comment…"})}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "title", "office", "bio", "open_to_mentor", "looking_for_mentor", "linkedin"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


class UserSkillForm(forms.ModelForm):
    new_skill = forms.CharField(required=False, label="…or a new skill", help_text="Type a skill that is not in the list.")

    class Meta:
        model = UserSkill
        fields = ["skill", "self_level", "is_learning", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skill"].required = False
        self.fields["skill"].queryset = Skill.objects.all()

    def clean(self):
        data = super().clean()
        if not data.get("skill") and data.get("new_skill"):
            data["skill"], _ = Skill.objects.get_or_create(name=data["new_skill"].strip())
        if not data.get("skill"):
            self.add_error("skill", "Pick a skill or type a new one.")
        return data


class EndorsementForm(forms.ModelForm):
    class Meta:
        model = Endorsement
        fields = ["skill", "level", "context"]


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ["stars", "review"]
        widgets = {"stars": forms.NumberInput(attrs={"min": 1, "max": 5}), "review": forms.Textarea(attrs={"rows": 2, "placeholder": "What worked, what to improve"})}
