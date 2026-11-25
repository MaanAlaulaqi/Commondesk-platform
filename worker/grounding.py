"""Resolve status, report excerpts and one verified service guidance passage."""

from urllib.parse import quote

from .answers import render_answer

RTA = "https://rta.ae/wps/portal/rta/ae/home/promotion/madinati-service"
PASSAGE = "RTA Madinati is a service option for this report. Selecting a service records routing intent."
TEXT = {
    "en": (
        "The selected report says",
        "The official service option is RTA Madinati. Selecting it records routing intent.",
        "I could not find supporting evidence. Please specify a case or the service you mean.",
    ),
    "ar": (
        "يذكر البلاغ المحدد",
        "خيار الخدمة الرسمي هو «مدينتي» التابع لهيئة الطرق والمواصلات. يسجّل الاختيار جهة الإحالة المقصودة.",
        "لم أجد دليلاً يدعم الإجابة. يرجى تحديد البلاغ أو الخدمة المقصودة.",
    ),
    "ur": (
        "منتخب رپورٹ میں درج ہے",
        "سرکاری سروس آر ٹی اے مدینتی ہے۔ انتخاب سے مجوزہ حوالہ ریکارڈ ہوتا ہے۔",
        "مجھے تائیدی ثبوت نہیں ملا۔ براہ کرم کیس یا مطلوبہ سروس بتائیں۔",
    ),
    "hi": (
        "चुनी गई रिपोर्ट में लिखा है",
        "आधिकारिक सेवा विकल्प आरटीए मदीनती है। चयन से प्रस्तावित रेफ़रल दर्ज होता है।",
        "समर्थन में साक्ष्य नहीं मिला। कृपया केस या सेवा स्पष्ट करें।",
    ),
    "th": (
        "รายงานที่เลือกระบุว่า",
        "ตัวเลือกบริการอย่างเป็นทางการคือ RTA Madinati การเลือกเป็นการบันทึกความประสงค์ในการส่งต่อ",
        "ไม่พบหลักฐานสนับสนุน โปรดระบุเคสหรือบริการที่ต้องการ",
    ),
}


SERVICE_DIRECTORY = {
    "en": "The official RTA Madinati service page is linked below.",
    "ar": "يرد أدناه رابط الصفحة الرسمية لخدمة «مدينتي» التابعة لهيئة الطرق والمواصلات.",
    "ur": "آر ٹی اے کی مدینتی سروس کے سرکاری صفحے کا لنک نیچے ہے۔",
    "hi": "नीचे आरटीए की मदीनती सेवा के आधिकारिक पृष्ठ का लिंक है।",
    "th": "ลิงก์ด้านล่างเป็นหน้าอย่างเป็นทางการของบริการ RTA Madinati",
}


PRIVATE_GUIDANCE = {
    "en": "Private directory suggestion: {names}. A directory listing carries no endorsement or official referral.",
    "ar": "اقتراح من دليل الأعمال الخاصة: {names}. الإدراج في الدليل لا يعني التزكية أو الإحالة الرسمية.",
    "hi": "निजी सेवा निर्देशिका का सुझाव: {names}। सूची में नाम होना समर्थन या आधिकारिक रेफ़रल नहीं है।",
    "th": "ตัวเลือกจากไดเรกทอรีธุรกิจเอกชน: {names} การมีชื่อในไดเรกทอรีไม่ได้หมายถึงการรับรองหรือการส่งต่ออย่างเป็นทางการ",
    "ur": "نجی خدمات کی ڈائریکٹری کی تجویز: {names}۔ فہرست میں شمولیت کسی توثیق یا سرکاری حوالے کی ضمانت نہیں ہے۔",
}
FIXTURE_LABEL = {
    "en": "fictional example",
    "ar": "مثال خيالي",
    "hi": "काल्पनिक उदाहरण",
    "th": "ตัวอย่างสมมติ",
    "ur": "فرضی مثال",
}
INTENT = {
    "en": "The case history records a routing intention only. No request was sent.",
    "ar": "يسجل سجل الحالة نية التوجيه فقط. لم يُرسل أي طلب.",
    "hi": "केस इतिहास में केवल भेजने का इरादा दर्ज है। कोई अनुरोध नहीं भेजा गया।",
    "th": "ประวัติเคสบันทึกเพียงความตั้งใจในการส่งต่อ ยังไม่มีการส่งคำขอ",
    "ur": "کیس کی تاریخ میں صرف ارادۂ رجوع درج ہے۔ کوئی درخواست نہیں بھیجی گئی۔",
}


def answer(body):
    lang = body.get("language", "en")
    if lang not in TEXT:
        raise ValueError("Unsupported answer language")
    source = body.get("source", "live")
    kind = body.get("kind", "status")
    case_id = body.get("case_id") or ""
    link = "#/cases/" + quote(case_id, safe="")
    if kind == "status":
        res = render_answer(lang, case_id, body.get("events", []))
        res["citations"] = [
            dict(
                id=i,
                source=source,
                href=link + "?event=" + quote(i, safe=""),
                label=i,
                excerpt=next(
                    e["status"]
                    for e in body["events"]
                    if e.get("event_id") == i and e.get("case_id") == case_id
                ),
            )
            for i in res["citations"]
        ]
        return res
    if kind not in ("guidance", "report"):
        raise ValueError("Unsupported answer kind")
    abstain = {"text": TEXT[lang][2], "outcome": "no_evidence", "citations": []}
    reports = [
        r
        for r in body.get("reports") or []
        if r.get("source") == source and (not case_id or r.get("id") == case_id)
    ]
    if kind == "guidance":
        service_terms = ("madinati", "مدينتي", "مدینتی", "मदीनती", "มาดินาติ")
        query = (body.get("question") or "").casefold()
        named_rta = any(t in query for t in service_terms)
        report = (
            reports[0] if case_id and reports and source in ("live", "seed", "dubai2024") else {}
        )
        options = report.get("service_options") or []
        # Older API callers supplied ID strings for the single verified public passage.
        eligible = any(
            o == "dubai_rta_madinati"
            or (
                isinstance(o, dict)
                and o.get("id") == "dubai_rta_madinati"
                and o.get("kind") == "public_authority"
            )
            for o in options
        )
        private = [
            o
            for o in options
            if isinstance(o, dict)
            and o.get("kind") == "private_directory"
            and isinstance(o.get("id"), str)
            and o["id"].startswith("private_")
            and o.get("name")
        ]
        selected = report.get("selected_service")
        event_id = report.get("service_event_id")
        history = []
        if (
            selected
            and any(isinstance(o, dict) and o.get("id") == selected for o in options)
            and event_id
        ):
            history.append(
                dict(
                    id=event_id,
                    source=source,
                    href=link + "?event=" + quote(event_id, safe=""),
                    label=event_id,
                    excerpt=selected,
                )
            )
        if private and not named_rta:
            labels = [
                o["name"]
                + (" (" + FIXTURE_LABEL[lang] + ")" if o.get("fictional") else "")
                for o in private
            ]
            citations = [
                dict(
                    id=o["id"],
                    source=source,
                    href=link + "?service=" + quote(o["id"], safe=""),
                    label=name,
                    excerpt=name,
                )
                for o, name in zip(private, labels)
            ]
            text = PRIVATE_GUIDANCE[lang].format(names=", ".join(labels))
            return {
                "text": text + (" " + INTENT[lang] if history else ""),
                "outcome": "guidance",
                "citations": citations + history,
            }
        if not eligible and (case_id or not named_rta):
            return abstain
        return {
            "text": (TEXT[lang][1] if eligible else SERVICE_DIRECTORY[lang])
            + (" " + INTENT[lang] if history else ""),
            "outcome": "guidance",
            "citations": [
                {
                    "id": "dubai_rta_madinati",
                    "source": "guidance",
                    "href": RTA,
                    "label": "RTA Madinati",
                    "excerpt": "RTA Madinati",
                    "guidance_id": "dubai_rta_madinati",
                }
            ]
            + history,
        }
    if not reports or not reports[0].get("text") or not reports[0].get("id"):
        return abstain
    r = reports[0]
    excerpt = (r.get("original_text") or r["text"])[:500]
    return {
        "text": f"{TEXT[lang][0]} «{excerpt}»",
        "outcome": "report_excerpt",
        "citations": [
            {
                "id": r["id"],
                "source": source,
                "href": "#/cases/" + quote(r["id"], safe=""),
                "label": r["id"],
                "excerpt": excerpt,
            }
        ],
    }
