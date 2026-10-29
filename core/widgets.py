"""Dashboard widgets. Each widget declares who gets it by default, which
capability it needs, how wide it is, and a `build(request, scope)` that returns
template context. `scope` carries the office filter: a partner in Toronto sees
Toronto unless they hold `view_all_offices`."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

ZERO = Decimal(0)


class Scope:
    def __init__(self, request):
        from core.permissions import effective_caps

        self.user = request.user
        self.caps = effective_caps(request)
        prof = getattr(request.user, "profile", None)
        self.office = prof.office if prof and prof.office_id else None
        self.all_offices = "view_all_offices" in self.caps or request.user.is_superuser or self.office is None
        self.label = "all offices" if self.all_offices else self.office.code

    def proposals(self):
        from proposals.models import Proposal

        qs = Proposal.objects.select_related("client", "owner", "currency", "office")
        return qs if self.all_offices else qs.filter(office=self.office)

    def actuals(self):
        from timesheets.models import ActualEntry

        qs = ActualEntry.objects.select_related("employee", "proposal")
        return qs if self.all_offices else qs.filter(employee__office=self.office)


REGISTRY = {}


def widget(key, title, description, cols=1, cap=None, default_for=("all",)):
    def deco(fn):
        REGISTRY[key] = {"key": key, "title": title, "description": description, "cols": cols, "cap": cap, "default_for": set(default_for), "build": fn}
        return fn

    return deco


@widget("pipeline", "Pipeline at a glance", "Open pursuits, pipeline and weighted value, win rate, stage counts.", cols=3, default_for=("Partners", "Associates", "Admins"))
def w_pipeline(request, scope):
    from core.models import CompanyProfile
    from proposals.models import Proposal

    base = CompanyProfile.get_solo().base_currency
    qs = scope.proposals()
    counts = {r["status"]: r["n"] for r in qs.values("status").annotate(n=Count("id"))}
    open_list = list(qs.filter(status__in=Proposal.OPEN_STATUSES))
    won, lost = counts.get("won", 0), counts.get("lost", 0)
    return {"base": base, "open_count": len(open_list), "pipeline_value": sum((p.fee_total_base for p in open_list), ZERO), "weighted_value": sum((p.weighted_value_base for p in open_list), ZERO),
            "win_rate": round(100 * won / (won + lost)) if (won + lost) else None, "won": won, "lost": lost,
            "pipeline": [{"key": k, "label": l, "count": counts.get(k, 0)} for k, l in Proposal.Status.choices]}


@widget("due_soon", "Due in the next 30 days", "Submissions coming up, and anything overdue.", default_for=("Partners", "Associates", "Engineers"))
def w_due(request, scope):
    from proposals.models import Proposal

    today = timezone.localdate()
    qs = scope.proposals().filter(status__in=Proposal.OPEN_STATUSES)
    return {"overdue": qs.filter(due_date__lt=today).order_by("due_date"), "due_soon": qs.filter(due_date__gte=today, due_date__lte=today + timedelta(days=30)).order_by("due_date")}


@widget("my_proposals", "My pursuits", "Proposals you lead.", default_for=("Associates", "Engineers"))
def w_mine(request, scope):
    from proposals.models import Proposal

    return {"items": Proposal.objects.filter(owner=request.user).select_related("client", "currency")[:8]}


@widget("recent_proposals", "Recent proposals", "Latest pursuits in your office.", cols=2, default_for=("Partners", "Associates", "Admins", "HR-Global", "HR-Local", "IT"))
def w_recent(request, scope):
    return {"items": scope.proposals()[:6]}


@widget("recent_sheets", "Recently added project sheets", "New or updated portfolio sheets.", default_for=("Partners", "Associates", "Engineers"))
def w_sheets(request, scope):
    from projects.models import PastProject

    return {"items": PastProject.objects.filter(is_published=True).prefetch_related("images").order_by("-updated_at")[:5]}


@widget("top_tools", "Top calculation tools", "Tools ranked by likes, ratings and use.", default_for=("Engineers", "Associates"))
def w_tools(request, scope):
    from calcs.models import Tool
    from community.models import Rating, Reaction

    rows = []
    for t in Tool.objects.filter(is_published=True):
        r, rt = Reaction.score(t), Rating.summary(t)
        rows.append({"tool": t, "up": r["up"], "rating": rt, "rank": r["score"] * 2 + rt["avg"] * rt["n"] + t.runs / 25})
    rows.sort(key=lambda x: (-x["rank"], x["tool"].name))
    return {"rows": rows[:6]}


@widget("my_calcs", "My saved calculations", "Calculations you saved, latest first.", default_for=("Engineers",))
def w_calcs(request, scope):
    from calcs.models import CalcRun

    return {"items": CalcRun.objects.filter(user=request.user).select_related("tool", "proposal")[:6]}


@widget("mentors", "Mentors for you", "Colleagues who hold the skills you are learning.", default_for=("Engineers",))
def w_mentors(request, scope):
    from community.models import suggest_mentors

    return {"items": suggest_mentors(request.user, limit=4)}


@widget("offices", "Offices", "Headcount, open pursuits, pipeline and hours booked in the last 90 days, per office.", cols=3, cap="view_all_offices", default_for=("Partners",))
def w_offices(request, scope):
    from core.models import CompanyProfile, Office
    from proposals.models import Proposal
    from timesheets.models import ActualEntry

    base = CompanyProfile.get_solo().base_currency
    since = timezone.localdate() - timedelta(days=90)
    rows = []
    for o in Office.objects.filter(is_active=True):
        open_qs = Proposal.objects.filter(office=o, status__in=Proposal.OPEN_STATUSES)
        hours = ActualEntry.objects.filter(employee__office=o, date__gte=since).aggregate(h=Sum("hours"))["h"] or 0
        rows.append({"office": o, "people": o.people.count(), "employees": o.employees.filter(is_active=True).count(), "open": open_qs.count(),
                     "pipeline": sum((p.fee_total_base for p in open_qs), ZERO), "won": Proposal.objects.filter(office=o, status="won").count(), "hours": hours})
    return {"rows": rows, "base": base}


@widget("hours", "Hours booked", "Timesheet hours in the last 8 weeks by person, from the sync.", cols=2, cap="view_actuals", default_for=("Partners", "HR-Global", "HR-Local"))
def w_hours(request, scope):
    today = timezone.localdate()
    since = today - timedelta(weeks=8)
    qs = scope.actuals().filter(date__gte=since)
    by_person = qs.values("employee__name", "employee_name").annotate(h=Sum("hours")).order_by("-h")[:10]
    weeks = []
    for i in range(8):
        start = since + timedelta(weeks=i)
        weeks.append({"label": start.strftime("%d %b"), "h": qs.filter(date__gte=start, date__lt=start + timedelta(weeks=1)).aggregate(h=Sum("hours"))["h"] or 0})
    mx = max((w["h"] for w in weeks), default=1) or 1
    return {"by_person": by_person, "weeks": weeks, "max": mx, "total": qs.aggregate(h=Sum("hours"))["h"] or 0}


@widget("active_projects", "Active projects", "Won work: estimate vs booked hours.", default_for=("Partners", "Associates"))
def w_active(request, scope):
    return {"items": scope.proposals().filter(status="won").exclude(project_status="complete")[:6]}


@widget("milestones", "Upcoming milestones", "Schedule milestones in the next 90 days.", default_for=("Associates", "Engineers"))
def w_milestones(request, scope):
    from proposals.models import Proposal
    from scheduling.models import Task

    today = timezone.localdate()
    qs = Task.objects.filter(is_milestone=True, start__gte=today, start__lte=today + timedelta(days=90), proposal__status__in=list(Proposal.OPEN_STATUSES) + ["won"]).select_related("proposal")
    if not scope.all_offices:
        qs = qs.filter(proposal__office=scope.office)
    return {"items": qs.order_by("start")[:8]}


@widget("news", "Tunnelling industry news", "Latest items from the configured feeds.", cols=2, default_for=("Partners", "Associates"))
def w_news(request, scope):
    from core.models import NewsItem, NewsSource

    return {"items": NewsItem.objects.select_related("source")[:8], "sources": NewsSource.objects.filter(is_active=True)}


@widget("weather", "Weather at the office", "Current conditions at your office (fetched in your browser from Open-Meteo).", default_for=("all",))
def w_weather(request, scope):
    from core.models import Office

    office = scope.office or Office.objects.filter(is_hq=True).first() or Office.objects.filter(is_active=True).first()
    return {"office": office}


@widget("quick_links", "Quick links", "Shortcuts to the things you open most.", default_for=("all",))
def w_links(request, scope):
    return {}


def default_keys(user):
    roles = {r.name for r in user.access_roles.all()}
    if user.is_superuser:
        roles.add("Partners")
    keys = [k for k, w in REGISTRY.items() if ("all" in w["default_for"]) or (roles & w["default_for"])]
    order = ["pipeline", "offices", "hours", "recent_proposals", "due_soon", "my_proposals", "active_projects", "milestones", "news", "top_tools", "my_calcs", "mentors", "recent_sheets", "weather", "quick_links"]
    return sorted(keys, key=lambda k: order.index(k) if k in order else 99)


def widgets_for(request):
    from core.permissions import effective_caps

    caps = effective_caps(request)
    prof = getattr(request.user, "profile", None)
    keys = list(prof.dashboard) if prof and prof.dashboard else default_keys(request.user)
    scope = Scope(request)
    out = []
    for key in keys:
        w = REGISTRY.get(key)
        if not w:
            continue
        if w["cap"] and w["cap"] not in caps and not request.user.is_superuser:
            continue
        try:
            ctx = w["build"](request, scope)
        except Exception as e:  # a broken widget never breaks the page
            ctx = {"error": str(e)}
        out.append({**w, "ctx": ctx})
    return out, scope, keys
