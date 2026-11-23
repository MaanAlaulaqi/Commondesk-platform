"""CommonDesk shared workspace HTTP API."""

import base64
import hashlib
import io
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

import jobs
from answers import render_answer
from db import cases, engine, events, insert_for, media, migrate, now, views
from store import (
    CATEGORIES,
    LANGS,
    SERVICE,
    STATUS,
    URGENCY,
    detail,
    scope,
    service_options,
    summaries,
)


@asynccontextmanager
async def lifespan(app):
    migrate()
    stop = threading.Event()
    thread = threading.Thread(
        target=jobs.run, args=(stop,), daemon=True, name="case-index"
    )
    if os.getenv("INDEX_ENABLED", "1") != "0":
        thread.start()
    yield
    stop.set()
    if thread.is_alive():
        thread.join(timeout=2)


app = FastAPI(title="CommonDesk", version="1.0", lifespan=lifespan)
origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[v.strip() for v in origins if v.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
MAX_MEDIA = 8 * 1024 * 1024


class BoundRequests:
    def __init__(self, app):
        self.app = app
        self.requests = {}
        self.last_clean = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        key = scope.get("client", ("unknown",))[0]
        clock = time.monotonic()
        if clock - self.last_clean > 60:
            self.requests = {
                k: v for k, v in self.requests.items() if v and v[-1] > clock - 60
            }
            self.last_clean = clock
        bucket = self.requests.setdefault(key, deque())
        while bucket and bucket[0] < clock - 60:
            bucket.popleft()
        if len(bucket) >= int(os.getenv("REQUESTS_PER_MINUTE", "120")):
            return await JSONResponse(
                {"detail": "Too many requests. Retry in one minute."}, 429
            )(scope, receive, send)
        bucket.append(clock)
        maximum = MAX_MEDIA + 65536 if scope["path"] == "/api/media" else 65536
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > maximum:
                return await JSONResponse(
                    {"detail": "Request exceeds the upload limit."}, 413
                )(scope, receive, send)
            if not message.get("more_body"):
                break
        # Replay the bounded body once; subsequent receives observe disconnect normally.
        served = False

        async def buffered():
            nonlocal served
            if served:
                return await receive()
            served = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        return await self.app(scope, buffered, send)


app.add_middleware(BoundRequests)


class Intake(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    language: Literal["en", "ar", "hi", "th", "ur"]
    intent: Literal["complaint", "suggestion", "feedback"] | None = None
    photo: str | None = Field(default=None, max_length=128)
    district: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    location_source: (
        Literal["pin", "manual", "device", "map", "geolocation", "coordinates", "gps"]
        | None
    ) = None
    clarification: str | None = Field(default=None, max_length=2000)
    manual_review: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=150)

    @model_validator(mode="after")
    def validate_intake(self):
        if not self.text.strip():
            raise ValueError("Enter a report")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both coordinates together")
        if self.latitude is None and (
            self.accuracy is not None or self.location_source
        ):
            raise ValueError("Location metadata requires a coordinate pair")
        return self


class Review(BaseModel):
    category: str | None = Field(default=None, max_length=60)
    urgency: Literal["high", "moderate", "low"] | None = None
    status: Literal["reported", "assigned", "completed"] | None = None
    service: Literal["dubai_rta_madinati", "unassigned"] | None = None
    feedback: Literal["up", "down"] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=150)
    note: str | None = Field(default=None, max_length=1000)


class Search(BaseModel):
    text: str = Field(default="", max_length=4000)
    photo: str | None = Field(default=None, max_length=128)
    source: Literal["seed", "live", "all", "archive"] = "all"
    filters: dict[str, str | None] = Field(default_factory=dict, max_length=12)
    limit: int = Field(default=20, ge=1, le=100)


class Answer(BaseModel):
    kind: Literal["status", "guidance", "report"] = "status"
    language: Literal["en", "ar", "hi", "th", "ur"] = "en"
    case_id: str | None = Field(default=None, max_length=150)
    source: Literal["seed", "live", "all", "archive"] = "all"
    question: str = Field(default="", max_length=4000)


def as_dict(row):
    return dict(row) if row else {}


def request_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def proposed(body):
    try:
        response = jobs.worker(
            "/proposal", body.model_dump(exclude_none=True), timeout=10
        )
        return {
            **response,
            "question": response.get("question") or response.get("clarification"),
        }
    except (httpx.HTTPError, ValueError):
        return {
            "intent": body.intent or "complaint",
            "category": "other",
            "urgency": "low",
            "interpretation": body.text,
            "evidence": "No automated assessment available; clerk review required.",
            "question": None,
            "version": "manual-intake-v1",
            "requires_review": True,
        }


@app.get("/healthz")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/readyz")
@app.get("/api/ready")
def ready():
    with engine.connect() as conn:
        conn.scalar(select(cases.c.id).limit(1))
    return {"status": "ready"}


@app.post("/api/proposal")
def proposal(body: Intake):
    return proposed(body)


@app.post("/api/media", status_code=201)
def upload(file: UploadFile = File(...)):
    original = file.file.read(MAX_MEDIA + 1)
    if len(original) > MAX_MEDIA:
        raise HTTPException(413, "Image too large")
    try:
        with Image.open(io.BytesIO(original)) as src:
            if src.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError
            if src.width * src.height > 16000000:
                raise ValueError
            src.load()
            # Keep orientation but exclude GPS, camera metadata and embedded payloads.
            image = ImageOps.exif_transpose(src).convert("RGB")
            image.thumbnail((2400, 2400))
            out = io.BytesIO()
            image.save(out, format="WEBP", quality=88, method=4)
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(
            415, "Supply a valid JPEG, PNG or WebP under 16 megapixels."
        )
    data = out.getvalue()
    mid = "img-" + hashlib.sha256(data).hexdigest()
    with engine.begin() as conn:
        conn.execute(
            insert_for(media)
            .values(
                id=mid,
                mime="image/webp",
                data=data,
                alt="Resident-submitted evidence",
                source="live",
            )
            .on_conflict_do_nothing()
        )
    return {"id": mid, "url": f"/api/media/{mid}"}


@app.get("/api/media/{mid}")
def image(mid: str):
    with engine.connect() as conn:
        row = conn.execute(
            select(media.c.mime, media.c.data).where(media.c.id == mid)
        ).first()
    if not row:
        raise HTTPException(404, "Media not found")
    return Response(
        content=row.data,
        media_type=row.mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public,max-age=86400",
        },
    )


@app.post("/api/cases", status_code=201)
def submit(body: Intake, request: Request):
    key = (
        body.idempotency_key
        or request.headers.get("Idempotency-Key")
        or uuid.uuid4().hex
    )
    if len(key) > 150:
        raise HTTPException(422, "Invalid replay key")
    digest = request_digest(body.model_dump(exclude={"idempotency_key"}))

    def replay(conn):
        found = conn.execute(
            select(cases.c.id, cases.c.request_hash).where(cases.c.requested_key == key)
        ).first()
        if found:
            if found.request_hash != digest:
                raise HTTPException(409, "Replay key already used for different input")
            return detail(conn, found.id)

    with engine.connect() as conn:
        previous = replay(conn)
        if previous:
            return previous
    prop = proposed(body)
    cid = "CD-" + uuid.uuid4().hex[:20].upper()
    at = now()
    day = datetime.fromisoformat(at).astimezone(ZoneInfo("Asia/Dubai")).date()
    with engine.begin() as conn:
        if body.photo and not conn.scalar(
            select(media.c.id).where(media.c.id == body.photo, media.c.source == "live")
        ):
            raise HTTPException(422, "Unknown uploaded media")
        row = dict(
            id=cid,
            source="live",
            incident_id=cid,
            language=body.language,
            text=body.text,
            intent=body.intent or prop["intent"],
            category=prop["category"],
            suggested_urgency=prop["urgency"],
            final_urgency=None,
            proposal=prop,
            latitude=body.latitude,
            longitude=body.longitude,
            accuracy=body.accuracy,
            location_source=body.location_source
            or ("manual" if body.latitude is not None else None),
            district=body.district,
            photo=body.photo,
            day=day.isoformat(),
            week_start=(day - timedelta(days=day.weekday())).isoformat(),
            created_at=at,
            status="reported",
            provenance="resident_submission",
            evidence_origin={},
            index_status="pending",
            requested_key=key,
            request_hash=digest,
            revision=1,
        )
        inserted = conn.scalar(
            insert_for(cases)
            .values(**row)
            .on_conflict_do_nothing(index_elements=[cases.c.requested_key]).returning(cases.c.id)
        )
        if inserted is None:
            return replay(conn)
        conn.execute(
            views.insert().values(
                case_id=cid, language=body.language, text=body.text, view_id=cid
            )
        )
        conn.execute(
            events.insert().values(
                case_id=cid,
                event_id=cid + "-receipt",
                type="status",
                status="reported",
                at=at,
                details={
                    "manual_review": body.manual_review,
                    "clarification": body.clarification,
                    "proposal": prop,
                },
            )
        )
        jobs.enqueue(conn, cid, 1)
        return detail(conn, cid)


@app.get("/api/cases")
def browse(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    checks = scope(request.query_params)
    with engine.connect() as conn:
        total = conn.scalar(select(func.count()).select_from(cases).where(*checks))
        rows = conn.execute(
            select(cases)
            .where(*checks)
            .order_by(cases.c.created_at.desc(), cases.c.id)
            .offset(offset)
            .limit(limit)
        ).mappings()
        return {
            "total": total,
            "items": summaries(conn, rows, request.query_params.get("locale")),
        }


@app.get("/api/map")
def map_items(request: Request):
    checks = scope(request.query_params)
    cols = (
        cases.c.id,
        cases.c.latitude,
        cases.c.longitude,
        cases.c.language,
        cases.c.category,
        cases.c.final_urgency,
        cases.c.status,
        cases.c.district,
        cases.c.source,
        cases.c.text,
    )
    with engine.connect() as conn:
        rows = conn.execute(
            select(*cols)
            .where(*checks, cases.c.latitude.is_not(None))
            .order_by(cases.c.id)
        ).mappings()
        items = [
            {**row, "urgency": row["final_urgency"] or "unreviewed"} for row in rows
        ]
    return {"total": len(items), "items": items}


@app.get("/api/facets")
def facets(request: Request):
    source = request.query_params.get("source", "all")
    checks = scope({"source": source})
    with engine.connect() as conn:

        def distinct(col):
            return list(
                conn.scalars(
                    select(col)
                    .where(*checks, col.is_not(None))
                    .distinct()
                    .order_by(col)
                )
            )

        return dict(
            category=distinct(cases.c.category),
            district=distinct(cases.c.district),
            language=LANGS,
            urgency=["unreviewed", *URGENCY],
            status=STATUS,
        )


@app.get("/api/insights")
def insights(request: Request):
    checks = scope(request.query_params)
    with engine.connect() as conn:

        def count(*extra):
            return conn.scalar(
                select(func.count()).select_from(cases).where(*checks, *extra)
            )

        def groups(col, by_date=False):
            n = func.count()
            q = (
                select(col.label("label"), n.label("count"))
                .where(*checks)
                .group_by(col)
            )
            return [
                dict(r)
                for r in conn.execute(
                    q.order_by(col) if by_date else q.order_by(n.desc(), col)
                ).mappings()
            ]

        return dict(
            total=count(),
            mapped=count(cases.c.latitude.is_not(None)),
            unreviewed=count(cases.c.final_urgency.is_(None)),
            high_open=count(
                cases.c.final_urgency == "high", cases.c.status != "completed"
            ),
            categories=groups(cases.c.category),
            weeks=groups(cases.c.week_start, True),
            urgencies=groups(func.coalesce(cases.c.final_urgency, "unreviewed")),
        )


@app.get("/api/cases/{cid}")
def get_case(cid: str, locale: str | None = None, language: str | None = None):
    if re.fullmatch(r"[0-9a-fA-F]{24}", cid):
        try:
            reply = httpx.get(jobs.WORKER_URL + "/archive/" + cid, timeout=30)
            if reply.status_code == 404:
                raise HTTPException(404, "Archive case not found")
            reply.raise_for_status()
            record = reply.json()
            return {
                **record,
                "original_text": record.get("text"),
                "original_language": "th",
                "events": [],
                "translations": {},
                "provenance": "historical_bangkok_archive",
                "service_options": [],
            }
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Historical archive is unavailable")
    with engine.connect() as conn:
        return detail(conn, cid, locale or language)


@app.post("/api/cases/{cid}/review")
def review(cid: str, body: Review, request: Request):
    changes = body.model_dump(exclude_none=True, exclude={"idempotency_key"})
    if not changes:
        raise HTTPException(422, "Provide at least one decision")
    if body.category and body.category not in CATEGORIES:
        raise HTTPException(422, "Unknown category")
    key = (
        body.idempotency_key
        or request.headers.get("Idempotency-Key")
        or uuid.uuid4().hex
    )
    if len(key) > 150:
        raise HTTPException(422, "Invalid replay key")
    eid = cid + "-review-" + hashlib.sha256(key.encode()).hexdigest()[:22]
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        row = (
            conn.execute(select(cases).where(cases.c.id == cid).with_for_update())
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(404, "Case not found")
        previous = conn.scalar(
            select(events.c.details).where(
                events.c.case_id == cid, events.c.event_id == eid
            )
        )
        if previous is not None:
            if previous["changes"] != changes:
                raise HTTPException(
                    409, "Replay key already used for a different review"
                )
            return detail(conn, cid)
        category = body.category or row["category"]
        if body.service == SERVICE["id"] and not service_options(category):
            raise HTTPException(
                422, "Madinati is offered for transit and footpath cases"
            )
        revision = row["revision"] + 1
        updates = {"revision": revision, "index_status": "pending"}
        if body.urgency:
            updates["final_urgency"] = body.urgency
        if body.status:
            updates["status"] = body.status
        if body.category:
            updates["category"] = body.category
        if body.service or (row["service"] and not service_options(category)):
            updates["service"] = (
                None if body.service in (None, "unassigned") else body.service
            )
        conn.execute(cases.update().where(cases.c.id == cid).values(**updates))
        conn.execute(
            events.insert().values(
                case_id=cid,
                event_id=eid,
                type="review",
                status=body.status,
                at=now(),
                details={
                    "changes": changes,
                    "previous": {
                        "category": row["category"],
                        "urgency": row["final_urgency"],
                        "status": row["status"],
                        "service": row["service"],
                    },
                    "proposal": row["proposal"],
                    "external_dispatch": False,
                },
            )
        )
        jobs.enqueue(conn, cid, revision)
        return detail(conn, cid)


def remote(path, payload):
    try:
        return jobs.worker(path, payload, timeout=120)
    except httpx.HTTPStatusError as exc:
        code = (
            exc.response.status_code
            if exc.response.status_code in (404, 422, 503)
            else 503
        )
        raise HTTPException(code, "Retrieval service could not serve this collection.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            503,
            "Retrieval service is unavailable. Saved reports remain accessible by case number.",
        )


@app.post("/api/search")
def search(body: Search):
    if not body.text.strip() and not body.photo:
        raise HTTPException(422, "Provide text or a reference photo")
    payload = body.model_dump(exclude_none=True)
    filters = {
        k: v
        for k, v in body.filters.items()
        if k
        in (
            "language",
            "category",
            "urgency",
            "district",
            "status",
            "date_from",
            "date_to",
        )
        and v
    }
    payload["filters"] = filters
    if body.photo:
        with engine.connect() as conn:
            data = conn.scalar(select(media.c.data).where(media.c.id == body.photo))
        if data is None:
            raise HTTPException(404, "Photo unavailable")
        payload["image_b64"] = base64.b64encode(data).decode()
    results = []
    for source in ("live", "seed") if body.source == "all" else (body.source,):
        if source != "archive":
            checks = scope({**filters, "source": source})
            with engine.connect() as conn:
                if not conn.scalar(select(cases.c.id).where(*checks).limit(1)):
                    continue
        raw = remote("/search", {**payload, "source": source})["items"]
        if source == "archive":
            results.extend(
                {**r, "source": "archive", "evidence_available": bool(r.get("text"))}
                for r in raw
            )
            continue
        ids = [r["id"] for r in raw]
        with engine.connect() as conn:
            rows = conn.execute(
                select(cases).where(cases.c.id.in_(ids), *checks)
            ).mappings()
            records = {
                r["id"]: r for r in summaries(conn, rows, filters.get("language"))
            }
        results.extend(
            {**records[r["id"]], "score": r.get("score", 0)}
            for r in raw
            if r["id"] in records
        )
    results.sort(key=lambda r: -r.get("score", 0))
    results = results[: body.limit]
    return {"items": results, "total": len(results)}


def public_answer(raw):
    citations = raw.get("citations", [])
    links = [
        {
            "id": c["id"],
            "label": c.get("label", c["id"]),
            "url": c.get("href", "").replace("#/cases/", "#/case/"),
            "excerpt": c.get("excerpt", ""),
        }
        for c in citations
    ]
    return {**raw, "citations": [item["id"] for item in links], "links": links}


@app.post("/api/answer")
def answer(body: Answer):
    record = None
    if body.case_id:
        record = get_case(body.case_id)
        if body.source not in ("all", record["source"]):
            raise HTTPException(404, "Case does not belong to selected source")
    if body.kind == "status":
        if not body.case_id:
            raise HTTPException(422, "A case ID is required")
        evidence = [e for e in record.get("events", []) if e.get("status")]
        result = render_answer(body.language, body.case_id, evidence)
        result["links"] = [
            {
                "id": k,
                "label": k,
                "url": f"#/case/{quote(body.case_id, safe='')}?event={quote(k, safe='')}",
            }
            for k in result["citations"]
        ]
        return result
    if body.kind == "report" and not record and body.question.strip():
        results = search(Search(text=body.question, source=body.source, limit=3))[
            "items"
        ]
    else:
        results = [record] if record else []
    payload = body.model_dump(exclude_none=True)
    payload["source"] = (
        record["source"]
        if record
        else (results[0]["source"] if results else body.source)
    )
    payload["reports"] = [
        {
            k: r.get(k)
            for k in (
                "id",
                "source",
                "text",
                "language",
                "service_options",
                "service",
                "category",
            )
        }
        for r in results
    ]
    for r in payload["reports"]:
        r["service_options"] = [opt["id"] for opt in (r["service_options"] or [])]
        r["selected_service"] = r.pop("service")
    if record:
        payload["case"] = payload["reports"][0]
    if body.kind == "report" and not results:
        # The API already searched the selected collection; suppress a second unhydrated lookup.
        payload["question"] = ""
    return public_answer(remote("/answer", payload))
