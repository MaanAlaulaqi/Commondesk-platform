"""Measure an isolated worker with invented complaints. Prints counters and timing only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import statistics
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

INPUTS = {
    "en": "The lamp by gate four is off. The other lamp is still working.",
    "hi": "चार नंबर गेट के पास वाली बत्ती बंद है। दूसरी बत्ती अभी भी जल रही है।",
    "ur": "گیٹ نمبر چار کے پاس والی بتی بند ہے۔ دوسری بتی ابھی بھی جل رہی ہے۔",
    "th": "ไฟข้างประตูหมายเลขสี่ดับ ส่วนไฟอีกดวงยังใช้งานได้",
    "ar": "المصباح بجانب البوابة الرابعة مطفأ. المصباح الآخر ما زال يعمل.",
}

def run(base):
    def translate(item):
        src, tgt, repeats = item
        data = json.dumps({"source_language":src, "target_language":tgt,
                           "text":" ".join([INPUTS[src]]*repeats)}).encode()
        start = time.monotonic()
        try:
            with urlopen(Request(base+"/translate", data=data, headers={"Content-Type":"application/json"}), timeout=120) as r:
                result = json.load(r)
                status = r.status if result.get("text") else 500
        except HTTPError as exc:
            status = exc.code
        return {"direction":src+":"+tgt, "status":status, "seconds":round(time.monotonic()-start,3)}
    pairs = [(a,b,1) for a in INPUTS for b in INPUTS if a!=b]
    cold=translate(pairs[0])
    samples=[translate(p) for p in pairs]
    longer=translate(("en","ar",4))
    with ThreadPoolExecutor(max_workers=4) as pool:
        burst=list(pool.map(translate,pairs[:4]))
    good=sorted(r["seconds"] for r in samples if r["status"]==200)
    return {"first_request":cold,"warm":samples,"longer":longer,"burst":burst,
            "p50_s":statistics.median(good) if good else None,
            "p95_s":good[math.ceil(.95*len(good))-1] if good else None}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("loopback_port",type=int)
    print(json.dumps(run(f"http://127.0.0.1:{p.parse_args().loopback_port}"),indent=2))
