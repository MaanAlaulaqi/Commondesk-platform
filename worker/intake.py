"""Auditable multilingual intake rules. Signals describe the submitted wording."""

import re

TERMS = {
    "private_plumbing": (
        "leaking tap", "leaky faucet", "leaking kitchen sink", "toilet cistern",
        "تسرب من الصنبور", "تسريب الصنبور", "نل ٹپک", "نل سے پانی ٹپک", "नल टपक", "नल से पानी टपक",
        "ก๊อกน้ำรั่ว", "ชักโครกรั่ว",
    ),
    "private_electrical": (
        "wall socket", "power outlet", "light switch", "circuit breaker",
        "مقبس كهربائي", "مفتاح الإضاءة", "بجلی کا ساکٹ", "بجلی کا سوئچ",
        "बिजली का सॉकेट", "बिजली का स्विच", "เต้ารับไฟฟ้า", "สวิตช์ไฟ",
    ),
    "drainage": (
        "drain",
        "flood",
        "overflow",
        "waterlogging",
        "naali",
        "nali",
        "naala",
        "نالی",
        "نکاسی",
        "سیلاب",
        "تصريف",
        "بالوعة",
        "مجرى",
        "غرق",
        "नाली",
        "नाला",
        "जलभराव",
        "बाढ़",
        "ท่อ",
        "ระบาย",
        "น้ำท่วม",
    ),
    "lighting": (
        "streetlight",
        "street light",
        "lighting",
        "lamp",
        "batti",
        "روشنی",
        "بتی",
        "إنارة",
        "انارة",
        "مصباح",
        "إضاءة",
        "बत्ती",
        "लाइट",
        "ไฟถนน",
        "ไฟส่อง",
    ),
    "footpath": (
        "pavement",
        "sidewalk",
        "footpath",
        "crossing",
        "فٹ پاتھ",
        "رصيف",
        "ممر",
        "फुटपाथ",
        "पैदल",
        "ทางเท้า",
        "ทางม้าลาย",
    ),
    "waste": (
        "rubbish",
        "trash",
        "garbage",
        "waste",
        "kachra",
        "کچرا",
        "نفايات",
        "قمامة",
        "कचरा",
        "कूड़ा",
        "ขยะ",
    ),
    "transit": (
        "bus",
        "transit",
        "station",
        "بس",
        "محطة",
        "حافلة",
        "बस",
        "รถเมล์",
        "ป้ายรถ",
    ),
    "parks": (
        "park",
        "playground",
        "پارک",
        "حديقة",
        "ملعب",
        "पार्क",
        "สวนสาธารณะ",
        "สนามเด็กเล่น",
    ),
}
HIGH = (
    "exposed wire",
    "electric shock",
    "sparking",
    "on fire",
    "smoke",
    "open manhole",
    "live wire",
    "مكشوف",
    "بجلی کا جھٹکا",
    "खुला मैनहोल",
    "करंट",
    "สายไฟขาด",
    "ไฟรั่ว",
)
SUGGEST = ("suggest", "please add", "تجویز", "اقتراح", "सुझाव", "เสนอ")
THANK = ("thank", "شکریہ", "شكرا", "شكرًا", "धन्यवाद", "ขอบคุณ")
GAP = {
    "en": (
        "Which feature is affected, and what happened?",
        "Is the drain blocked, or is its cover damaged?",
        "Your report mentions",
        "Please confirm the issue or send it for manual review.",
    ),
    "ar": (
        "ما المرفق المتأثر وماذا حدث؟",
        "هل المصرف مسدود أم أن غطاءه تالف؟",
        "ورد في بلاغك",
        "يرجى تأكيد المشكلة أو إرسالها للمراجعة اليدوية.",
    ),
    "ur": (
        "کون سی سہولت متاثر ہے اور کیا ہوا؟",
        "کیا نالی بند ہے یا اس کا ڈھکن خراب ہے؟",
        "آپ کی رپورٹ میں درج ہے",
        "مسئلے کی تصدیق کریں یا دستی جائزے کے لیے بھیجیں۔",
    ),
    "hi": (
        "कौन सी सुविधा प्रभावित है और क्या हुआ?",
        "नाली बंद है या उसका ढक्कन टूटा है?",
        "आपकी रिपोर्ट में लिखा है",
        "समस्या की पुष्टि करें या मैन्युअल समीक्षा के लिए भेजें।",
    ),
    "th": (
        "สิ่งใดได้รับผลกระทบและเกิดอะไรขึ้น",
        "ท่อระบายน้ำอุดตันหรือฝาท่อชำรุด",
        "รายงานของคุณระบุว่า",
        "โปรดยืนยันปัญหาหรือส่งให้เจ้าหน้าที่ตรวจสอบ",
    ),
}


def match(text, terms):
    for term in terms:
        # English uses words; allow plurals and common compounds via curated terms.
        pattern = (
            r"(?<![a-z])" + re.escape(term) + r"(?:s|ing)?(?![a-z])"
            if term.isascii()
            else re.escape(term)
        )
        # The short bus word also occurs inside the Arabic word for an electrical socket.
        if term == "بس":
            pattern = r"(?<!\w)بس(?!\w)"
        found = re.search(pattern, text, re.IGNORECASE)
        if found:
            return found.group()
    return None


def proposal(body):
    text = body.get("text", "").strip()
    lang = body.get("language", "en")
    if not text or lang not in GAP:
        raise ValueError("Expected complaint text and supported language")
    clarification = (body.get("clarification") or "").strip()
    observed = text + " " + clarification if clarification else text
    terms = [(k, match(observed, v)) for k, v in TERMS.items()]
    terms = [(k, v) for k, v in terms if v]
    category = terms[0][0] if len(terms) == 1 else "unclassified"
    intent = body.get("intent") or (
        "feedback"
        if match(text, THANK)
        else "suggestion"
        if match(text, SUGGEST)
        else "complaint"
    )
    if intent not in ("feedback", "suggestion", "complaint"):
        raise ValueError("Unsupported intake intent")
    hazard = match(observed, HIGH)
    urgency = "high" if hazard else "moderate"
    route = None
    if category == "unclassified":
        route = GAP[lang][0]
    elif category == "drainage" and not match(
        text,
        (
            "blocked",
            "blocking",
            "clogged",
            "broken",
            "cracked",
            "cover",
            "flood",
            "overflow",
            "بند",
            "مسدود",
            "غطاء",
            "ढक्कन",
            "बंद",
            "ตัน",
            "ฝา",
        ),
    ):
        route = GAP[lang][1]
    # The quote is copied directly from the input. The UI can render the rule separately.
    if clarification:
        route = None
    quote = observed[:320]
    return {
        "intent": intent,
        "category": category,
        "urgency": urgency,
        "version": "civic-intake-rules-v2",
        "interpretation": f"{GAP[lang][2]} «{quote}». {GAP[lang][3]}",
        "evidence": hazard or (terms[0][1] if terms else quote),
        "clarification": route,
        "service": None,
        "review_required": bool(route),
        "evidence_type": "resident_text",
        "urgency_reason": "reported_hazard_keyword"
        if hazard
        else "no_specific_hazard_keyword",
    }
