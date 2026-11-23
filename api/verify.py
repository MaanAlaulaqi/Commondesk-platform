"""Run public API acceptance against a local, seeded installation and live worker."""

import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.parse import urlsplit

import httpx
from PIL import Image

REPORTS = {
    "en": "A streetlight beside the demonstration bus shelter has an exposed wire.",
    "ar": "مصباح الإنارة مكسور عند مدخل الحديقة التجريبي.",
    "th": "ท่อระบายน้ำอุดตันที่ทางเข้าเขตทดลอง",
    "hi": "प्रदर्शन क्षेत्र में फुटपाथ टूटा हुआ है।",
    "ur": "تجرباتی گلی کی نالی بند ہے اور پانی جمع ہو رہا ہے۔",
}


def verify(base):
    if urlsplit(base).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Use a local, disposable acceptance workspace")
    client = httpx.Client(base_url=base.rstrip("/") + "/", timeout=150)

    def get(path, **params):
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def post(path, body):
        r = client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    counts = get("insights", source="seed")
    assert [counts[k] for k in ("total", "mapped", "unreviewed", "high_open")] == [
        2348,
        2231,
        747,
        145,
    ]
    assert len(get("map", source="seed")["items"]) == 2231
    photo_case = get("cases/bkk-st-009", locale="ur")
    assert (
        len(photo_case["translations"]) == 5
        and photo_case["language"] == "ur"
        and photo_case["original_language"] == "th"
    )
    photo = client.get("media/" + photo_case["photo"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/webp"
    img = BytesIO()
    Image.new("RGB", (32, 32), "yellow").save(img, format="PNG")
    uploaded = client.post(
        "media", files={"file": ("example.png", img.getvalue(), "image/png")}
    )
    uploaded.raise_for_status()
    image_id = uploaded.json()["id"]
    assert (
        client.post(
            "media", files={"file": ("fake.png", b"wrong", "image/png")}
        ).status_code
        == 415
    )
    cases = {}
    for lang, original in REPORTS.items():
        body = dict(
            text=original,
            language=lang,
            idempotency_key="acceptance-v1-" + lang,
            district="demo-loop",
        )
        if lang == "en":
            body.update(
                photo=image_id,
                latitude=25.21,
                longitude=55.28,
                location_source="manual",
            )
        if lang == "ar":
            body["manual_review"] = True
        prop = post("proposal", body)
        assert prop.get("evidence")
        case = post("cases", body)
        assert (
            case["id"] == post("cases", body)["id"]
            and case["original_text"] == original
        )
        assert (
            client.post(
                "cases", json={**body, "text": "conflicting submission"}
            ).status_code
            == 409
        )
        cases[lang] = case["id"]
    race_key = "acceptance-concurrent-" + uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=3) as pool:
        replies = list(
            pool.map(
                lambda _: post(
                    "cases",
                    {
                        "text": "Check an ambiguous fixture",
                        "language": "en",
                        "manual_review": True,
                        "idempotency_key": race_key,
                    },
                ),
                range(3),
            )
        )
    assert len({r["id"] for r in replies}) == 1
    q = post("proposal", {"text": "There is a problem", "language": "en"})
    assert q["question"]
    refined = post(
        "proposal",
        {
            "text": "There is a problem",
            "language": "en",
            "clarification": "the drain is blocked",
        },
    )
    assert refined["category"] == "drainage"
    assert (
        client.post(
            "cases", json={"text": "range", "language": "en", "latitude": 10}
        ).status_code
        == 422
    )
    approved = post(
        "cases/" + cases["en"] + "/review",
        dict(
            category="transit",
            urgency="high",
            status="assigned",
            service="dubai_rta_madinati",
            feedback="up",
            idempotency_key="qa-accept",
        ),
    )
    assert (
        approved["service"] == "dubai_rta_madinati"
        and approved["final_urgency"] == "high"
    )
    changed = post(
        "cases/" + cases["hi"] + "/review",
        dict(urgency="low", idempotency_key="qa-override", feedback="down"),
    )
    assert (
        changed["final_urgency"] == "low"
        and changed["suggested_urgency"] == changed["proposal"]["urgency"]
    )
    assert get("cases/" + cases["ur"])["final_urgency"] is None
    status = post(
        "answer", dict(case_id=cases["en"], kind="status", language="ur", source="live")
    )
    assert status["outcome"] == "assigned" and status["citations"][0] in {
        e["event_id"] for e in approved["events"]
    }
    assert status["citations"][0] in status["links"][0]["url"]
    assert (
        client.post(
            "answer",
            json=dict(case_id=cases["en"], kind="status", language="en", source="seed"),
        ).status_code
        == 404
    )
    guidance = post(
        "answer",
        dict(case_id=cases["en"], kind="guidance", language="hi", source="live"),
    )
    assert guidance["outcome"] == "guidance" and "rta.ae" in guidance["links"][0]["url"]
    abstain = post(
        "answer",
        dict(case_id=cases["ur"], kind="guidance", language="en", source="live"),
    )
    assert abstain["outcome"] == "no_evidence" and not abstain["links"]
    quote = post(
        "answer", dict(case_id=cases["ar"], kind="report", language="en", source="live")
    )
    assert REPORTS["ar"] in quote["text"] and quote["links"][0]["id"] == cases["ar"]
    for _ in range(90):
        pending = [
            cid
            for cid in cases.values()
            if get("cases/" + cid)["index_status"] != "indexed"
        ]
        if not pending:
            break
        time.sleep(2)
    assert not pending, pending
    searches = []
    for q, language in (
        ("blocked drain", "ur"),
        ("نالی بند", "th"),
        ("naali بند", "ur"),
        ("broken light", "ar"),
    ):
        found = post(
            "search",
            dict(
                text=q,
                source="live",
                filters={"district": "demo-loop", "language": language},
            ),
        )
        ids = [i["id"] for i in found["items"]]
        assert cases[language] in ids
        searches.append(
            {
                "query": q,
                "candidate_language": language,
                "rank": ids.index(cases[language]) + 1,
            }
        )
    for q in ("", "damaged transit stop"):
        result = post(
            "search", dict(text=q, photo=photo_case["photo"], source="seed", limit=5)
        )
        assert photo_case["id"] in [i["id"] for i in result["items"]]
    assert (
        post(
            "search",
            dict(
                text="street light",
                source="live",
                filters={"district": "missing-demo-district"},
            ),
        )["total"]
        == 0
    )
    assert get("cases", source="live", ids=",".join(cases.values()))["total"] == 5
    print(
        json.dumps(
            {
                "seed_counts": {
                    k: counts[k] for k in ("total", "mapped", "unreviewed", "high_open")
                },
                "cases": cases,
                "status_citation": status["links"][0],
                "guidance": guidance["links"][0]["url"],
                "search_smokes": searches,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8100/api")
    verify(parser.parse_args().api)
