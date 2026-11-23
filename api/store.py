"""Canonical browse queries shared by the list, charts, map and search hydration."""

from datetime import date
from fastapi import HTTPException
from sqlalchemy import or_, select
from db import cases, events, media, views

LANGS = ("en", "ar", "hi", "th", "ur")
URGENCY = ("low", "moderate", "high")
STATUS = ("reported", "assigned", "completed")
SERVICE = {
    "id": "dubai_rta_madinati",
    "name": "RTA Madinati",
    "url": "https://rta.ae/wps/portal/rta/ae/home/promotion/madinati-service",
}
CATEGORIES = (
    "drainage",
    "footpath",
    "lighting",
    "parks",
    "transit",
    "waste",
    "other",
    "unclassified",
)


def service_options(category):
    return [SERVICE] if category in ("footpath", "transit") else []


def scope(params):
    t = cases.c
    checks = []
    source = params.get("source") or "all"
    if source == "archive":
        raise HTTPException(
            422, "The historical archive supports semantic search only."
        )
    if source not in ("all", "live", "seed"):
        raise HTTPException(422, "Unknown collection")
    if source != "all":
        checks.append(t.source == source)
    for field in ("category", "district", "status"):
        if value := params.get(field):
            checks.append(t[field] == value)
    if value := params.get("urgency"):
        checks.append(
            t.final_urgency.is_(None)
            if value == "unreviewed"
            else t.final_urgency == value
        )
    if value := params.get("language"):
        checks.append(
            select(views.c.case_id)
            .where(views.c.case_id == t.id, views.c.language == value)
            .exists()
        )
    for key in ("date_from", "date_to"):
        if value := params.get(key):
            try:
                d = date.fromisoformat(value).isoformat()
            except ValueError:
                raise HTTPException(422, "Invalid date")
            checks.append(t.day >= d if key == "date_from" else t.day <= d)
    if value := params.get("q"):
        checks.append(
            or_(
                t.id.icontains(value, autoescape=True),
                select(views.c.case_id)
                .where(
                    views.c.case_id == t.id,
                    views.c.text.icontains(value, autoescape=True),
                )
                .exists(),
            )
        )
    if "ids" in params:
        ids = params["ids"].split(",")
        if len(ids) > 200:
            raise HTTPException(422, "Too many selected cases")
        checks.append(t.id.in_(ids))
    return checks


def summary(row, localized=None):
    raw = dict(row)
    result = {
        k: v
        for k, v in raw.items()
        if k not in ("requested_key", "request_hash", "day", "week_start")
    }
    result.update(
        original_text=raw["text"],
        original_language=raw["language"],
        urgency=raw["final_urgency"] or "unreviewed",
        photo_url=f"/api/media/{raw['photo']}" if raw["photo"] else None,
    )
    if localized:
        result.update(text=localized["text"], language=localized["language"])
    return result


def summaries(conn, rows, locale):
    rows = list(rows)
    wordings = {}
    if rows and locale:
        wordings = {
            v["case_id"]: v
            for v in conn.execute(
                select(views).where(
                    views.c.case_id.in_([r["id"] for r in rows]),
                    views.c.language == locale,
                )
            ).mappings()
        }
    return [summary(r, wordings.get(r["id"])) for r in rows]


def detail(conn, cid, locale=None):
    row = conn.execute(select(cases).where(cases.c.id == cid)).mappings().first()
    if row is None:
        raise HTTPException(404, "Case not found")
    texts = {
        v["language"]: v
        for v in conn.execute(select(views).where(views.c.case_id == cid)).mappings()
    }
    data = summary(row, texts.get(locale))
    data["photo_alt"] = conn.scalar(select(media.c.alt).where(media.c.id == row["photo"])) if row["photo"] else None
    data["translations"] = {lang: r["text"] for lang, r in texts.items()}
    data["events"] = [
        dict(e)
        for e in conn.execute(
            select(events)
            .where(events.c.case_id == cid)
            .order_by(events.c.at, events.c.event_id)
        ).mappings()
    ]
    data["service_options"] = service_options(data["category"])
    return data
