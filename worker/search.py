"""Source-isolated Qdrant collections. Only live cases can be written via HTTP."""

from collections import OrderedDict
from datetime import date, datetime, time, timezone, timedelta
from functools import cached_property
import os
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models as q
from .encoders import Encoders
from .archive import evidence

COLLECTIONS = {
    "seed": "commondesk_seed_v1",
    "live": "commondesk_live_v1",
    "archive": "bangkok_archive_e5",
}
FACETS = {"category", "urgency", "status", "district", "language"}
DIM = 384


class Unavailable(Exception):
    pass


def connect(url=None, key=None):
    if url:
        parsed = urlsplit(url)
        return QdrantClient(
            url=url,
            port=parsed.port or (443 if parsed.scheme == "https" else 6333),
            api_key=key,
            timeout=30,
            check_compatibility=False,
        )
    return QdrantClient(path=os.environ.get("QDRANT_PATH", "/data/vectors"))


def point(view_id, case, text, image=None):
    vectors = {"text": text}
    if image is not None:
        vectors["photo"] = image
    return q.PointStruct(
        id=str(uuid5(NAMESPACE_URL, f"commondesk:{case['source']}:{view_id}")),
        payload=case,
        vector=vectors,
    )


def where(filters):
    clauses = []
    for k, value in filters.items():
        if value in (None, "", "all"):
            continue
        if k in FACETS:
            clauses.append(
                q.FieldCondition(key=k, match=q.MatchValue(value=str(value)))
            )
        elif k in ("date_from", "date_to"):
            day = datetime.combine(
                date.fromisoformat(value), time.min, tzinfo=timezone(timedelta(hours=4))
            )
            bounds = (
                {"gte": day} if k == "date_from" else {"lt": day + timedelta(days=1)}
            )
            clauses.append(
                q.FieldCondition(key="created_at", range=q.DatetimeRange(**bounds))
            )
        else:
            raise ValueError("Unsupported filter: " + k)
    return q.Filter(must=clauses) if clauses else None


class Store:
    def __init__(self):
        self.client = connect(os.getenv("QDRANT_URL"), os.getenv("QDRANT_API_KEY"))
        self.encoders = Encoders()
        self.archive_offsets = OrderedDict()

    @cached_property
    def archive(self):
        if os.getenv("ARCHIVE_QDRANT_URL"):
            return connect(
                os.environ["ARCHIVE_QDRANT_URL"], os.getenv("ARCHIVE_QDRANT_API_KEY")
            )
        return self.client

    def ensure(self, source, name=None):
        if source not in ("live", "seed"):
            raise ValueError("Read-only source")
        name = name or COLLECTIONS[source]
        if not self.client.collection_exists(name):
            self.client.create_collection(
                name,
                vectors_config={
                    k: q.VectorParams(size=DIM, distance=q.Distance.COSINE)
                    for k in ("text", "photo")
                },
            )
            if os.getenv("QDRANT_URL"):
                for k in sorted(FACETS):
                    self.client.create_payload_index(
                        name, k, q.PayloadSchemaType.KEYWORD, wait=True
                    )
                self.client.create_payload_index(
                    name, "created_at", q.PayloadSchemaType.DATETIME, wait=True
                )
        return name

    def index(self, body):
        case = body["case"]
        if (
            case.get("source") != "live"
            or not case.get("id")
            or not case.get("text", "").strip()
        ):
            raise ValueError("Expected live case with ID and text")
        payload = {
            k: case.get(k)
            for k in (
                "id",
                "source",
                "text",
                "language",
                "category",
                "status",
                "district",
                "created_at",
            )
        }
        payload["urgency"] = case.get("urgency") or "unreviewed"
        vector = self.encoders.encode("e5-small", "passage: " + payload["text"])
        image = (
            self.encoders.encode("dinov2-small", body["image_b64"])
            if body.get("image_b64")
            else None
        )
        self.client.upsert(
            self.ensure("live"),
            [point(payload["id"], payload, vector, image)],
            wait=True,
        )
        return {"id": payload["id"], "indexed": True}

    def archive_detail(self, report_id):
        item = evidence(report_id, self.archive_offsets.get(report_id))
        if item.get("evidence_available") or "source_offset" in item:
            return item
        if not any(
            a.alias_name == COLLECTIONS["archive"]
            for a in self.archive.get_aliases().aliases
        ):
            raise Unavailable("Archive alias has not been published")
        records, _ = self.archive.scroll(
            COLLECTIONS["archive"],
            scroll_filter=q.Filter(
                must=[
                    q.FieldCondition(
                        key="report_id", match=q.MatchValue(value=report_id)
                    )
                ]
            ),
            limit=1,
            with_payload=["source_offset"],
            with_vectors=False,
        )
        if not records:
            raise KeyError("Unknown archive identifier")
        return dict(item, source_offset=records[0].payload["source_offset"])

    def metadata(self, body):
        source = body.get("source")
        if source not in ("seed", "live") or not isinstance(body.get("id"), str):
            raise ValueError("Expected canonical seed or live case ID")
        changes = {
            k: body[k]
            for k in ("category", "urgency", "status", "district")
            if k in body
        }
        if "urgency" in changes:
            changes["urgency"] = changes["urgency"] or "unreviewed"
        if not changes:
            raise ValueError("No supported metadata supplied")
        selection = q.Filter(
            must=[q.FieldCondition(key="id", match=q.MatchValue(value=body["id"]))]
        )
        name = COLLECTIONS[source]
        if (
            not self.client.collection_exists(name)
            or not self.client.count(name, count_filter=selection, exact=True).count
        ):
            raise Unavailable("Case vectors are pending")
        self.client.set_payload(name, changes, points=selection, wait=True)
        return {"id": body["id"], "updated": True}

    def combined_search(self, body):
        limit = int(body.get("limit", 20))
        texts = self.search(dict(body, image_b64=None, limit=100))["items"]
        photos = self.search(dict(body, text="", limit=100))["items"]
        pairs = {i["id"]: (i["score"], i) for i in texts}
        photo_pairs = {i["id"]: (i["score"], i) for i in photos}
        items = fuse(pairs, photo_pairs, limit)
        return {"items": items, "total": len(items)}

    def search(self, body):
        source = body.get("source", "live")
        if not 1 <= int(body.get("limit", 20)) <= 100:
            raise ValueError("Limit outside 1 to 100")
        if source == "all":
            limit = int(body.get("limit", 20))
            # Each collection uses identical pinned encoders. Pool before multimodal fusion.
            # Both per-source candidate windows are fixed so archive cannot enter shared search.
            if body.get("text") and body.get("image_b64"):
                return self.combined_search(body)
            items = [
                item
                for part in ("seed", "live")
                for item in self.search(dict(body, source=part))["items"]
            ]
            items.sort(key=lambda x: (-x["score"], x["id"]))
            return {"items": items[:limit], "total": len(items[:limit])}
        if source not in COLLECTIONS:
            raise ValueError("Choose seed, live or archive")
        name = COLLECTIONS[source]
        limit = int(body.get("limit", 20))
        text = (body.get("text") or "").strip()
        image = body.get("image_b64")
        if not 1 <= limit <= 100 or len(text) > 8000 or (not text and not image):
            raise ValueError("Supply a query or photo and a limit of 1 to 100")
        filters = body.get("filters") or {}
        query_filter = where(filters)
        if source == "archive":
            if not any(
                a.alias_name == name for a in self.archive.get_aliases().aliases
            ):
                raise Unavailable("Archive alias has not been published")
            if image or query_filter:
                raise ValueError("Archive supports unfiltered text lookup only")
            vv = self.encoders.encode("e5-small", "query: " + text)
            hits = self.archive.query_points(
                name, query=vv, limit=limit, with_payload=True
            ).points
            items = [
                dict(
                    evidence(h.payload["report_id"], h.payload["source_offset"]),
                    score=h.score,
                )
                for h in hits
            ]
            for item in items:
                self.archive_offsets[item["id"]] = item["source_offset"]
                self.archive_offsets.move_to_end(item["id"])
                if len(self.archive_offsets) > 1024:
                    self.archive_offsets.popitem(last=False)
            return {
                "items": items,
                "total": len(items),
                "evidence_available": bool(os.getenv("ARCHIVE_CATALOG")),
            }
        if not self.client.collection_exists(name):
            return {"items": [], "total": 0}

        # Score each language view against its own text; return one canonical submission.
        # Only the bounded candidate union enters fusion on large shared collections.
        window = min(500, max(100, limit * 5))

        def retrieve(kind, vector):
            hits = self.client.query_points(
                name,
                using=kind,
                query=vector,
                query_filter=query_filter,
                limit=window,
                with_payload=True,
            ).points
            seen = {}
            for h in sorted(
                hits,
                key=lambda h: (-h.score, h.payload["id"], h.payload.get("view_id", "")),
            ):
                seen.setdefault(h.payload["id"], (h.score, h.payload))
            return seen

        texts = (
            retrieve("text", self.encoders.encode("e5-small", "query: " + text))
            if text
            else {}
        )
        photos = (
            retrieve("photo", self.encoders.encode("dinov2-small", image))
            if image
            else {}
        )
        if not (text and image):
            hits = texts if text else photos
            items = [dict(p, score=s) for s, p in list(hits.values())[:limit]]
        else:
            items = fuse(texts, photos, limit)
        return {"items": items, "total": len(items)}


def fuse(texts, photos, limit):
    ids = list(texts) + [i for i in photos if i not in texts]
    ranks = {cid: n for n, cid in enumerate(photos, 1)}
    ranked = []
    for t, cid in enumerate(ids, 1):
        # Missing text candidates have equal reciprocal rank below the text cutoff.
        text_rank = t if cid in texts else len(texts) + 1
        tr = 1 / (60 + text_rank)
        score = 2 * tr
        if cid in photos:
            adjusted = 0.5 + (ranks[cid] - 0.5) * len(ids) / len(photos)
            score = tr + 1 / (60 + adjusted)
        ranked.append(dict((texts.get(cid) or photos[cid])[1], score=score))
    return sorted(ranked, key=lambda x: (-x["score"], x["id"]))[:limit]
