import type { RoutingOption } from "./client";
import { useContext } from "react";
import { Field } from "./ui";
import { Locale, useWords } from "./locale";

const copy = {
  en: ["Property or asset", "Unknown", "Public asset", "Private property", "Emergency",
    "Official public service", "Private directory suggestion", "Fictional example",
    "Directory entries are suggestions only. CommonDesk does not endorse businesses or make official referrals.",
    "Saving records routing intent in the case history. No one is contacted or booked.",
    "Save the changed case details to see eligible service options.", "Routing intent recorded", "Routing selection cleared"],
  ar: ["نوع الموقع أو المرفق", "غير معروف", "مرفق عام", "عقار خاص", "حالة طارئة",
    "خدمة عامة رسمية", "اقتراح من دليل الشركات الخاصة", "مثال افتراضي",
    "إدراج الشركات في الدليل مجرد اقتراح. لا يزكّي CommonDesk الشركات ولا يصدر إحالات رسمية.",
    "يُسجّل الحفظ الجهة المقصودة في سجل البلاغ فقط، دون اتصال أو حجز.",
    "احفظ تفاصيل البلاغ المعدّلة لعرض خيارات الخدمة المتاحة.", "تم تسجيل الجهة المقصودة", "أُلغي اختيار الجهة المقصودة"],
  hi: ["संपत्ति या सुविधा का प्रकार", "अज्ञात", "सार्वजनिक सुविधा", "निजी संपत्ति", "आपात स्थिति",
    "आधिकारिक सार्वजनिक सेवा", "निजी निर्देशिका से सुझाव", "काल्पनिक उदाहरण",
    "निर्देशिका में व्यवसाय केवल सुझाव के रूप में दिए गए हैं। CommonDesk उनकी सिफारिश या आधिकारिक रेफ़रल नहीं करता।",
    "सहेजने पर केस के इतिहास में केवल इच्छित सेवा दर्ज होती है। कोई संपर्क या बुकिंग नहीं होती।",
    "उपलब्ध सेवाएँ देखने के लिए बदले हुए विवरण सहेजें।", "इच्छित सेवा दर्ज हुई", "चुनी हुई सेवा हटाई गई"],
  th: ["ประเภทของทรัพย์สินหรือสถานที่", "ไม่ทราบ", "ทรัพย์สินสาธารณะ", "ทรัพย์สินส่วนบุคคล", "เหตุฉุกเฉิน",
    "บริการของหน่วยงานรัฐ", "ตัวเลือกจากรายชื่อผู้ให้บริการเอกชน", "ตัวอย่างสมมติ",
    "รายชื่อนี้เป็นเพียงตัวเลือก CommonDesk ไม่ได้รับรองผู้ประกอบการหรือส่งต่อเรื่องอย่างเป็นทางการ",
    "เมื่อบันทึก ระบบจะเก็บเฉพาะบริการที่ตั้งใจเลือกไว้ในประวัติเรื่อง โดยไม่มีการติดต่อหรือนัดหมาย",
    "บันทึกข้อมูลที่แก้ไขเพื่อดูบริการที่เลือกได้", "บันทึกบริการที่ตั้งใจเลือกแล้ว", "ยกเลิกบริการที่เลือกแล้ว"],
  ur: ["جگہ یا اثاثے کی نوعیت", "نامعلوم", "عوامی اثاثہ", "نجی ملکیت", "ہنگامی صورت حال",
    "سرکاری عوامی خدمت", "نجی ڈائریکٹری کی تجویز", "فرضی مثال",
    "ڈائریکٹری میں کاروبار صرف بطور تجویز درج ہیں۔ CommonDesk ان کی توثیق یا باضابطہ حوالہ نہیں دیتا۔",
    "محفوظ کرنے سے کیس کی تاریخ میں صرف مطلوبہ خدمت درج ہوتی ہے۔ کسی سے رابطہ یا بکنگ نہیں ہوتی۔",
    "دستیاب خدمات دیکھنے کے لیے تبدیل شدہ تفصیلات محفوظ کریں۔", "مطلوبہ خدمت درج ہو گئی", "منتخب خدمت ہٹا دی گئی"],
} as const;
function labels(locale: string) {
  return copy[locale as keyof typeof copy] || copy.en;
}
export function ServiceRouting({ context, options, selection, current, pending, busy,
  onContext, onSelect }: {
  context: string; options: RoutingOption[]; selection: string; current?: string;
  pending: boolean; busy: boolean; onContext: (value: string) => void; onSelect: (value: string) => void;
}) {
  const words = labels(useContext(Locale)), t = useWords();
  const contexts = ["unknown", "public_asset", "private_premises", "emergency"];
  const label = (o: RoutingOption) => [
    o.kind === "private_directory" ? words[6] : words[5], o.name, o.fictional && words[7],
  ].filter(Boolean).join(" · ");
  const eligible = options.filter(o => o.kind === "private_directory" || o.kind === "public_authority"
    || (!o.kind && o.id === "dubai_rta_madinati"));
  return <>
    <Field label={words[0]}>
      <select data-ui-action="service_select" value={context} disabled={busy} onChange={e => onContext(e.target.value)}>
        {contexts.map((v, i) => <option key={v} value={v}>{words[i+1]}</option>)}
      </select>
    </Field>
    {pending ? <p role="status">{words[10]}</p> : (eligible.length > 0 || current) && <>
      <Field label={t("service")}>
        <select data-ui-action="service_select" value={selection} disabled={busy} onChange={e => onSelect(e.target.value)}>
          <option value="">{eligible.find(o => o.id === current)?.name || t("choose")}</option>
          {current && <option value="unassigned">{t("unassigned")}</option>}
          {eligible.map(o => <option key={o.id} value={o.id}>{label(o)}</option>)}
        </select>
      </Field>
      <p>{words[9]}</p>
      {eligible.some(o => o.kind === "private_directory") && <p>{words[8]}</p>}
      {eligible.map(o => o.url?.startsWith("https://")
        ? <a key={o.id} id={"service-" + o.id} className="service-link"
            href={o.url} target="_blank" rel="noreferrer"><bdi>{label(o)}</bdi></a>
        : <p key={o.id} id={"service-" + o.id} tabIndex={-1}><bdi>{label(o)}</bdi></p>)}
    </>}
  </>;
}

export function RoutingHistory({ selected }: { selected: RoutingOption | null }) {
  const words = labels(useContext(Locale));
  return <p>{selected ? <>{words[11]} · {selected.kind === "private_directory" ? words[6] : words[5]}
    {" · "}<bdi>{selected.name}</bdi>{selected.fictional && <> · {words[7]}</>}</> : words[12]}</p>;
}
