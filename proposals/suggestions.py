"""Cost-estimate suggestions drawn from previous (won) proposals.

Looks for fee items with similar names on won proposals and returns their
estimated and actual effort so the estimator sees what comparable work cost.
This is deliberately simple (token overlap + difflib) and will become a learned
model once actual project data accumulates.
"""

from decimal import Decimal
from difflib import SequenceMatcher

from django.db.models import Q

from .models import FeeItem, Proposal

STOP = {"the", "and", "of", "for", "to", "a", "an", "&", "-", "design"}


def _tokens(s: str):
    return {t for t in "".join(ch if ch.isalnum() else " " for ch in s.lower()).split() if t not in STOP and len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    jacc = len(ta & tb) / len(ta | tb) if (ta | tb) else 0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jacc, seq)


def suggest_for_item(name: str, exclude_proposal=None, kind: str | None = None, limit: int = 5, min_score: float = 0.45):
    if not name or len(name.strip()) < 3:
        return {"matches": [], "summary": None}
    qs = FeeItem.objects.filter(proposal__status=Proposal.Status.WON).select_related("proposal", "proposal__currency")
    if exclude_proposal is not None:
        qs = qs.exclude(proposal=exclude_proposal)
    if kind:
        qs = qs.filter(Q(kind=kind) | Q(kind="other"))
    scored = []
    for item in qs:
        score = similarity(name, item.name)
        if score >= min_score:
            est_hours = item.hours
            est_cost_base = item.proposal.cur.to_base(item.total)
            act_hours = item.actual_hours
            act_cost_base = Decimal(item.actuals.aggregate(t=__import__("django.db.models", fromlist=["Sum"]).Sum("cost"))["t"] or 0)
            scored.append(
                {
                    "item": item,
                    "score": round(score, 2),
                    "est_hours": est_hours,
                    "est_cost_base": est_cost_base,
                    "act_hours": act_hours if act_hours else None,
                    "act_cost_base": act_cost_base if act_cost_base else None,
                    "hours_ratio": (float(act_hours / est_hours) if est_hours and act_hours else None),
                }
            )
    scored.sort(key=lambda r: -r["score"])
    matches = scored[:limit]
    summary = None
    if matches:
        n = len(matches)
        avg_est_hours = sum((m["est_hours"] for m in matches), Decimal(0)) / n
        avg_est_cost = sum((m["est_cost_base"] for m in matches), Decimal(0)) / n
        with_act = [m for m in matches if m["act_hours"]]
        avg_act_hours = (sum((m["act_hours"] for m in with_act), Decimal(0)) / len(with_act)) if with_act else None
        ratios = [m["hours_ratio"] for m in with_act if m["hours_ratio"]]
        summary = {
            "n": n,
            "avg_est_hours": avg_est_hours,
            "avg_est_cost_base": avg_est_cost,
            "avg_act_hours": avg_act_hours,
            "avg_ratio": (sum(ratios) / len(ratios)) if ratios else None,
            "recommended_hours": (avg_act_hours if avg_act_hours else avg_est_hours),
        }
    return {"matches": matches, "summary": summary}
