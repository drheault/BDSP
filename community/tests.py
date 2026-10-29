from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from community.models import Endorsement, MentorMatch, Profile, Reaction, Skill, UserSkill, suggest_mentors
from proposals.models import Proposal


class CommunityTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.a = U.objects.create_user("ann", password="p", first_name="Ann")
        self.b = U.objects.create_user("bob", password="p", first_name="Bob")
        Profile.objects.create(user=self.a)
        Profile.objects.create(user=self.b)
        self.skill = Skill.objects.create(name="SEM design")
        self.client.force_login(self.a)

    def test_comments_and_reactions(self):
        p = Proposal.objects.create(title="P")
        ct = ContentType.objects.get_for_model(p).pk
        r = self.client.post(reverse("comment_add", args=[ct, p.pk]), {"body": "Looks good"}, HTTP_HX_REQUEST="true")
        self.assertContains(r, "Looks good")
        r = self.client.post(reverse("react", args=[ct, p.pk, "up"]), HTTP_HX_REQUEST="true")
        self.assertEqual(Reaction.score(p)["up"], 1)
        self.client.post(reverse("react", args=[ct, p.pk, "up"]), HTTP_HX_REQUEST="true")  # toggle off
        self.assertEqual(Reaction.score(p)["up"], 0)

    def test_skills_endorsement_and_mentor_matching(self):
        UserSkill.objects.create(user=self.b, skill=self.skill, self_level=4)
        UserSkill.objects.create(user=self.a, skill=self.skill, self_level=1, is_learning=True)
        r = self.client.post(reverse("endorse", args=[self.b.pk]), {"skill": self.skill.pk, "level": 5, "context": "Central cavern design"})
        self.assertEqual(r.status_code, 302)
        us = UserSkill.objects.get(user=self.b, skill=self.skill)
        self.assertEqual(us.combined_level, 4.5)
        self.assertEqual(self.client.post(reverse("endorse", args=[self.a.pk]), {"skill": self.skill.pk, "level": 5, "context": "x"}).status_code, 302)
        self.assertFalse(Endorsement.objects.filter(from_user=self.a, to_user=self.a).exists())
        sugg = suggest_mentors(self.a)
        self.assertEqual(sugg[0]["mentors"][0].user, self.b)
        self.client.post(reverse("mentor_propose", args=[self.b.pk]), {"skill": self.skill.pk})
        m = MentorMatch.objects.get()
        self.client.force_login(self.b)
        self.client.post(reverse("mentor_respond", args=[m.pk, "accept"]))
        m.refresh_from_db()
        self.assertEqual(m.status, "active")
        self.assertEqual(self.client.get(reverse("people")).status_code, 200)
        self.assertEqual(self.client.get(reverse("person", args=[self.a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("my_profile")).status_code, 200)
