"""Assemble the canonical case and media manifests from translated photo-backed reports."""

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker.intake import proposal


SOURCE_CATEGORIES = {
    "ทางเท้า": "footpath",
    "น้ำท่วม": "drainage",
    "ท่อระบายน้ำ": "drainage",
    "ขยะ": "waste",
    "แท็กซี่/รถเมล์": "transit",
    "ต้นไม้และสวนสาธารณะ": "parks",
}


def package(root):
    edits_file = root / "translation-edits.json"
    edits = json.loads(edits_file.read_text()) if edits_file.exists() else {}
    pairs = {
        pair["id"]: pair
        for line in (root / "pairs.jsonl").read_text().splitlines()
        if (pair := json.loads(line))
    }
    assets = []
    rows = []
    for line in (root / "translated.jsonl").read_text().splitlines():
        pair = json.loads(line)
        cid = pair["id"]
        translations = {**pair.pop("translations"), **edits.pop(cid, {})}
        if pair != pairs.pop(cid, None):
            raise ValueError(f"Translation stage changed original evidence for {cid}")
        if date.fromisoformat(pair["date"]).year != 2024:
            raise ValueError(f"Unexpected source year for {cid}")
        if set(translations) != {"en", "ar", "hi", "ur"}:
            raise ValueError(f"Expected four target languages for {cid}")
        texts = {
            "th": pair["text"],
            **{lang: translations[lang] for lang in ("en", "ar", "hi", "ur")},
        }
        if not all(text.strip() for text in texts.values()):
            raise ValueError(f"Incomplete translation set for {cid}")
        props = proposal(
            {"text": pair["text"], "language": "th", "intent": "complaint"}
        )
        origin = dict(
            dataset="Bangkok Traffy Fondue",
            report_id=pair["report_id"],
            source_category=pair["label"],
            source_offset=pair["source_offset"],
            report_date=pair["date"],
            image_sha256=pair["source_image_sha256"],
            image_version="prepared initial report photo",
        )
        assets.append(
            dict(
                id=cid,
                path=pair["path"],
                alt="",
                sha256=sha256((root / pair["path"]).read_bytes()).hexdigest(),
                source=origin,
            )
        )
        created_at = pair["date"] + "T12:00:00+07:00"
        for lang, text in texts.items():
            rows.append(
                dict(
                    submission_id=cid,
                    incident_id=cid,
                    case_id=f"{cid}-{lang}",
                    media_id=cid,
                    language=lang,
                    text=text,
                    is_primary_view=lang == "th",
                    text_origin="original_thai"
                    if lang == "th"
                    else "translation_from_thai",
                    district=pair["district"],
                    lat=pair["lat"],
                    lon=pair["lon"],
                    created_at=created_at,
                    intent="complaint",
                    category=SOURCE_CATEGORIES.get(pair["label"], props["category"]),
                    urgency_suggested=props["urgency"],
                    urgency_confirmed=None,
                    urgency_reason_code=props["urgency_reason"],
                    status="reported",
                    service_options=[],
                    selected_service=None,
                    provenance="bangkok_source_pair_simulated_dubai_location",
                    events=[
                        dict(
                            event_id=f"{cid}-reported", at=created_at, status="reported"
                        )
                    ],
                )
            )
    if pairs or edits:
        raise ValueError("Source pairs or translation edits have missing cases")
    if len({asset["sha256"] for asset in assets}) != len(assets):
        raise ValueError("Two packaged reports share an identical displayed photo")
    if len(assets) != len({asset["id"] for asset in assets}):
        raise ValueError("Duplicate canonical submission")
    (root / "reports.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    (root / "media/manifest.json").write_text(
        json.dumps({"assets": assets}, ensure_ascii=False)
    )
    (root / "manifest.json").write_text(
        json.dumps(
            dict(
                collection="DubaiV2Example",
                year=2024,
                submission_count=len(assets),
                photo_count=len(assets),
                language_views=len(rows),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    package(parser.parse_args().root)
