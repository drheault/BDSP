from django.test import TestCase

from proposals.models import Service
from tags.models import Tag, TagCategory, suggest_tags


class TagTests(TestCase):
    def test_set_tags_creates_and_replaces(self):
        cat = TagCategory.objects.create(name="Method", weight=1.5)
        Tag.objects.create(name="SEM / NATM", category=cat, aliases="NATM, sprayed concrete lining")
        svc = Service.objects.create(name="SEM tunnel design")
        svc.set_tags(["SEM / NATM", "Brand new"])
        self.assertEqual({t.name for t in svc.tags}, {"SEM / NATM", "Brand new"})
        self.assertEqual(Tag.objects.get(name="Brand new").category.name, "General")
        svc.set_tags(["Brand new"])
        self.assertEqual([t.name for t in svc.tags], ["Brand new"])
        self.assertEqual([t.name for t in suggest_tags("a NATM lining with sprayed concrete")], ["SEM / NATM"])
