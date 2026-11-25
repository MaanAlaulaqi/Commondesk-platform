"""Recognize common civic topics while retaining the full wording of a specific query."""

import re
import unicodedata

from .intake import match

# The first five terms name the same topic in English, Arabic, Thai, Hindi and Urdu.
# Additional spellings and synonyms identify the topic without giving any language extra weight.
TOPICS = (
    (
        ("sidewalk", "رصيف", "ทางเท้า", "फुटपाथ", "فٹ پاتھ"),
        (
            "footpath",
            "pavement",
            "pedestrian walkway",
            "الرصيف",
            "الأرصفة",
            "أرصفة",
            "ฟุตบาท",
        ),
    ),
    (
        ("drain cover", "غطاء البالوعة", "ฝาท่อระบายน้ำ", "नाली का ढक्कन", "نالی کا ڈھکن"),
        ("manhole cover", "غطاء الصرف", "ฝาท่อ", "मैनहोल का ढक्कन"),
    ),
    (
        ("streetlight", "إنارة الشوارع", "ไฟถนน", "स्ट्रीट लाइट", "اسٹریٹ لائٹ"),
        ("street light", "street lighting", "مصباح الشارع", "ไฟทาง"),
    ),
    (
        ("garbage", "نفايات", "ขยะ", "कचरा", "کچرا"),
        ("rubbish", "trash", "النفايات", "قمامة", "कूड़ा"),
    ),
    (
        ("bus stop", "موقف الحافلات", "ป้ายรถเมล์", "बस स्टॉप", "بس اسٹاپ"),
        ("bus shelter", "موقف حافلات", "ป้ายรถโดยสาร"),
    ),
    (("tree", "شجرة", "ต้นไม้", "पेड़", "درخت"), ("أشجار", "الأشجار", "الشجرة")),
)


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[ـً-ْٰ]", "", text).strip(" ؟?!.،")


VOCABULARY = tuple(
    (anchors, tuple(normalize(term) for term in (*anchors, *aliases)))
    for anchors, aliases in TOPICS
)


def query_topic(text):
    normalized = normalize(text)
    found = []
    for anchors, terms in VOCABULARY:
        if normalized in terms:
            return anchors, True
        token = match(normalized, terms)
        if token:
            if normalized == token:
                return anchors, True
            found.append(anchors)
    return (found[0], False) if len(found) == 1 else (None, False)
