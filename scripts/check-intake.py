"""Run against an empty local release before starting its inference worker."""
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "http://localhost:8000/api"
def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(BASE + path, data=data, headers={"Content-Type":"application/json"}), timeout=60) as response:
        return json.load(response)

assert request("/cases?source=live")["total"] == 0, "Use a clean local installation."
fixtures = {
    "en": "Demo fixture: the pavement by the bus stop is broken.",
    "ar": "بلاغ تجريبي: إنارة الشارع لا تعمل",
    "th": "ข้อมูลทดสอบ: มีน้ำท่วมขังบริเวณท่อระบายน้ำ",
    "hi": "परीक्षण रिपोर्ट: सड़क पर कूड़ा पड़ा है।",
    "ur": "آزمائشی رپورٹ: نالی بند ہے اور پانی جمع ہے۔",
}
ids = {}
for lang, wording in fixtures.items():
    body = dict(text=wording, language=lang, manual_review=True, idempotency_key="release-smoke-v1-"+lang)
    if lang=="en":
        body.update(latitude=25.21,longitude=55.30,location_source="manual")
    saved = request("/cases",body)
    assert request("/cases",body)["id"] == saved["id"]
    assert request("/cases/"+saved["id"])["text"] == wording
    ids[lang] = saved["id"]
assert request("/cases?source=live")["total"] == 5
out = Path(sys.argv[1])
out.parent.mkdir(exist_ok=True, parents=True)
out.write_text(json.dumps(ids,indent=2))
print("Five persisted submissions and five idempotent replays:",ids)
