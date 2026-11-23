import { useContext } from "react";
import { Field } from "./ui";
import { Locale, useWords } from "./locale";

const copy = {
  en: ["Property or asset", "Unknown", "Public asset", "Private property", "Emergency",
    "Official public service", "Private directory suggestion", "Fictional example",
    "Directory entries are suggestions only. CommonDesk does not endorse businesses or make official referrals.",
    "Saving records routing intent in the case history. No one is contacted or booked.",
    "Save the changed case details to see eligible service options.", "Private plumbing", "Private electrical maintenance"],
  ar: ["نوع الموقع أو المرفق", "غير معروف", "مرفق عام", "عقار خاص", "حالة طارئة",
    "خدمة عامة رسمية", "اقتراح من دليل الشركات الخاصة", "مثال افتراضي",
    "إدراج الشركات في الدليل مجرد اقتراح. لا يزكّي CommonDesk الشركات ولا يصدر إحالات رسمية.",
    "يُسجّل الحفظ الجهة المقصودة في سجل البلاغ فقط، دون اتصال أو حجز.",
    "احفظ تفاصيل البلاغ المعدّلة لعرض خيارات الخدمة المتاحة.", "سباكة العقارات الخاصة", "صيانة كهرباء العقارات الخاصة"],
  hi: ["संपत्ति या सुविधा का प्रकार", "अज्ञात", "सार्वजनिक सुविधा", "निजी संपत्ति", "आपात स्थिति",
    "आधिकारिक सार्वजनिक सेवा", "निजी निर्देशिका से सुझाव", "काल्पनिक उदाहरण",
    "निर्देशिका में व्यवसाय केवल सुझाव के रूप में दिए गए हैं। CommonDesk उनकी सिफारिश या आधिकारिक रेफ़रल नहीं करता।",
    "सहेजने पर केस के इतिहास में केवल इच्छित सेवा दर्ज होती है। कोई संपर्क या बुकिंग नहीं होती।",
    "उपलब्ध सेवाएँ देखने के लिए बदले हुए विवरण सहेजें।", "निजी संपत्ति की प्लंबिंग", "निजी संपत्ति का विद्युत रखरखाव"],
  th: ["ประเภทของทรัพย์สินหรือสถานที่", "ไม่ทราบ", "ทรัพย์สินสาธารณะ", "ทรัพย์สินส่วนบุคคล", "เหตุฉุกเฉิน",
    "บริการของหน่วยงานรัฐ", "ตัวเลือกจากรายชื่อผู้ให้บริการเอกชน", "ตัวอย่างสมมติ",
    "รายชื่อนี้เป็นเพียงตัวเลือก CommonDesk ไม่ได้รับรองผู้ประกอบการหรือส่งต่อเรื่องอย่างเป็นทางการ",
    "เมื่อบันทึก ระบบจะเก็บเฉพาะบริการที่ตั้งใจเลือกไว้ในประวัติเรื่อง โดยไม่มีการติดต่อหรือนัดหมาย",
    "บันทึกข้อมูลที่แก้ไขเพื่อดูบริการที่เลือกได้", "งานประปาในพื้นที่ส่วนบุคคล", "งานซ่อมบำรุงไฟฟ้าในพื้นที่ส่วนบุคคล"],
  ur: ["جگہ یا اثاثے کی نوعیت", "نامعلوم", "عوامی اثاثہ", "نجی ملکیت", "ہنگامی صورت حال",
    "سرکاری عوامی خدمت", "نجی ڈائریکٹری کی تجویز", "فرضی مثال",
    "ڈائریکٹری میں کاروبار صرف بطور تجویز درج ہیں۔ CommonDesk ان کی توثیق یا باضابطہ حوالہ نہیں دیتا۔",
    "محفوظ کرنے سے کیس کی تاریخ میں صرف مطلوبہ خدمت درج ہوتی ہے۔ کسی سے رابطہ یا بکنگ نہیں ہوتی۔",
    "دستیاب خدمات دیکھنے کے لیے تبدیل شدہ تفصیلات محفوظ کریں۔", "نجی ملکیت کی پلمبنگ", "نجی ملکیت کی برقی مرمت"],
} as const;
function labels(locale: string) {
  return copy[locale as keyof typeof copy] || copy.en;
}
export function privateCategory(code: string, locale: string) {
  if (code === "private_plumbing") return labels(locale)[11];
  if (code === "private_electrical") return labels(locale)[12];
}
export type RoutingOption = {
  id: string; name: string; kind?: "private_directory" | "public_authority";
  fictional?: boolean; url?: string | null;
};
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
      <select value={context} disabled={busy} onChange={e => onContext(e.target.value)}>
        {contexts.map((v, i) => <option key={v} value={v}>{words[i+1]}</option>)}
      </select>
    </Field>
    {pending ? <p role="status">{words[10]}</p> : (eligible.length > 0 || current) && <>
      <Field label={t("service")}>
        <select value={selection} disabled={busy} onChange={e => onSelect(e.target.value)}>
          <option value="">{eligible.find(o => o.id === current)?.name || t("choose")}</option>
          {current && <option value="unassigned">{t("unassigned")}</option>}
          {eligible.map(o => <option key={o.id} value={o.id}>{label(o)}</option>)}
        </select>
      </Field>
      <p>{words[9]}</p>
      {eligible.some(o => o.kind === "private_directory") && <p>{words[8]}</p>}
      {eligible.map(o => o.url?.startsWith("https://") && <a key={o.id} className="service-link"
        href={o.url} target="_blank" rel="noreferrer"><bdi>{label(o)}</bdi></a>)}
    </>}
  </>;
}
