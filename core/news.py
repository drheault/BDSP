"""Fetch industry news from RSS/Atom feeds (runs on the office network; from
the shell with `manage.py fetch_news`, or the button under Settings → Offices)."""

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone as tz
from email.utils import parsedate_to_datetime

from django.utils import timezone

from .models import NewsItem, NewsSource


def _text(el, *names):
    for n in names:
        found = el.find(n)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def parse_feed(data: bytes):
    root = ET.fromstring(data)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for it in root.iter("item"):  # RSS
        link = _text(it, "link")
        date = _text(it, "pubDate")
        try:
            dt = parsedate_to_datetime(date) if date else timezone.now()
        except Exception:
            dt = timezone.now()
        items.append({"title": _text(it, "title")[:300], "url": link[:500], "summary": _text(it, "description")[:500], "published_at": dt})
    for it in root.findall(".//a:entry", ns):  # Atom
        link_el = it.find("a:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        date = _text(it, "a:updated", "a:published") if False else ((it.find("a:updated", ns).text if it.find("a:updated", ns) is not None else "") or "")
        try:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00")) if date else timezone.now()
        except Exception:
            dt = timezone.now()
        items.append({"title": (it.find("a:title", ns).text or "")[:300] if it.find("a:title", ns) is not None else "", "url": (link or "")[:500], "summary": ((it.find("a:summary", ns).text or "") if it.find("a:summary", ns) is not None else "")[:500], "published_at": dt})
    return [i for i in items if i["title"] and i["url"]]


def fetch_source(source: NewsSource, timeout=15) -> int:
    req = urllib.request.Request(source.url, headers={"User-Agent": "TunnelVision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    n = 0
    for it in parse_feed(data):
        if it["published_at"].tzinfo is None:
            it["published_at"] = it["published_at"].replace(tzinfo=tz.utc)
        _, created = NewsItem.objects.get_or_create(url=it["url"], defaults={"source": source, "title": it["title"], "summary": it["summary"], "published_at": it["published_at"]})
        n += int(created)
    return n


def fetch_all():
    ok = failed = items = 0
    for src in NewsSource.objects.filter(is_active=True):
        try:
            items += fetch_source(src)
            src.last_error = ""
            ok += 1
        except Exception as e:
            src.last_error = str(e)[:255]
            failed += 1
        src.last_fetched_at = timezone.now()
        src.save(update_fields=["last_error", "last_fetched_at"])
    return {"ok": ok, "failed": failed, "items": items}
