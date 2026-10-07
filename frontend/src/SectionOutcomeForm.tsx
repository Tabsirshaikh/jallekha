import { useRef, useState, type FormEvent } from "react";
import { apiFetch } from "./api";
import { useAuth } from "./auth";
import { useLocale } from "./i18n";
import { useApi } from "./useApi";
import "./SectionOutcomeForm.css";
import WeeklyPriorityPanel from "./WeeklyPriorityPanel";

const copy = {
  en: { title: "Check booking access on the ground", question: "Could people not book a tanker?", section: "Section visited", date: "Visit date", note: "Visit note", yes: "Yes", no: "No", unclear: "Unclear", save: "Save visit outcome", saving: "Saving…", saved: "Visit outcome saved", pending: "Visit saved; the audit record is pending. Submit again to retry.", error: "Could not save the visit. Your answers are still here.", loadError: "Could not load section visits", empty: "No sections are waiting for a visit", progress: "Not yet checked on the ground: {n} distinct, decisive visits; {min} needed to measure precision.", precision: "Among {n} distinct sections checked, {p} confirmed that people could not book.", choose: "Choose an answer", signIn: "Sign in as an officer or field worker to record a visit." },
  te: { title: "క్షేత్రస్థాయిలో బుకింగ్ అవకాశాన్ని పరిశీలించండి", question: "ప్రజలు ట్యాంకర్ బుక్ చేయలేకపోయారా?", section: "సందర్శించిన విభాగం", date: "సందర్శన తేదీ", note: "సందర్శన గమనిక", yes: "అవును", no: "కాదు", unclear: "స్పష్టంగా లేదు", save: "సందర్శన ఫలితాన్ని భద్రపరచండి", saving: "భద్రపరుస్తోంది…", saved: "సందర్శన ఫలితం భద్రపరచబడింది", pending: "సందర్శన భద్రపరచబడింది; తనిఖీ నమోదు పెండింగ్‌లో ఉంది. మళ్లీ సమర్పించండి.", error: "సందర్శనను భద్రపరచలేకపోయాము. మీ సమాధానాలు ఇక్కడే ఉన్నాయి.", loadError: "విభాగ సందర్శనలను లోడ్ చేయలేకపోయాము", empty: "సందర్శన కోసం వేచి ఉన్న విభాగాలు లేవు", progress: "ఇంకా క్షేత్రస్థాయి పరిశీలన సరిపోలేదు: {n} వేర్వేరు స్పష్టమైన సందర్శనలు; ఖచ్చితత్వం కొలవడానికి {min} అవసరం.", precision: "పరిశీలించిన {n} వేర్వేరు విభాగాలలో, {p} ప్రజలు బుక్ చేయలేకపోయారని నిర్ధారించాయి.", choose: "ఒక సమాధానం ఎంచుకోండి", signIn: "సందర్శన నమోదు చేయడానికి అధికారి లేదా క్షేత్ర సిబ్బందిగా సైన్ ఇన్ చేయండి." },
  ur: { title: "موقع پر بکنگ کی رسائی جانچیں", question: "کیا لوگ ٹینکر بک نہیں کر پائے؟", section: "دورہ کیا گیا سیکشن", date: "دورے کی تاریخ", note: "دورے کا نوٹ", yes: "ہاں", no: "نہیں", unclear: "واضح نہیں", save: "دورے کا نتیجہ محفوظ کریں", saving: "محفوظ ہو رہا ہے…", saved: "دورے کا نتیجہ محفوظ ہو گیا", pending: "دورہ محفوظ ہے؛ آڈٹ اندراج باقی ہے۔ دوبارہ جمع کریں۔", error: "دورہ محفوظ نہیں ہو سکا۔ آپ کے جواب یہیں ہیں۔", loadError: "سیکشن کے دورے لوڈ نہیں ہو سکے", empty: "کسی سیکشن کا دورہ باقی نہیں", progress: "ابھی زمینی جانچ کافی نہیں: {n} الگ واضح دورے؛ درستگی ناپنے کے لیے {min} درکار ہیں۔", precision: "جانچے گئے {n} الگ سیکشنوں میں، {p} نے تصدیق کی کہ لوگ بک نہیں کر سکے۔", choose: "ایک جواب منتخب کریں", signIn: "دورہ درج کرنے کے لیے افسر یا فیلڈ ورکر کے طور پر سائن ان کریں۔" },
  hi: { title: "मौके पर बुकिंग की पहुँच जाँचें", question: "क्या लोग टैंकर बुक नहीं कर पाए?", section: "देखा गया सेक्शन", date: "दौरे की तारीख", note: "दौरे का नोट", yes: "हाँ", no: "नहीं", unclear: "स्पष्ट नहीं", save: "दौरे का परिणाम सहेजें", saving: "सहेज रहे हैं…", saved: "दौरे का परिणाम सहेज दिया गया", pending: "दौरा सहेजा गया; ऑडिट रिकॉर्ड बाकी है। दोबारा जमा करें।", error: "दौरा सहेज नहीं सके। आपके जवाब यहीं हैं।", loadError: "सेक्शन के दौरे लोड नहीं हो सके", empty: "किसी सेक्शन का दौरा बाकी नहीं है", progress: "अभी मौके की जाँच पर्याप्त नहीं: {n} अलग स्पष्ट दौरे; सटीकता मापने के लिए {min} चाहिए।", precision: "जाँचे गए {n} अलग सेक्शन में, {p} ने पुष्टि की कि लोग बुक नहीं कर पाए।", choose: "एक जवाब चुनें", signIn: "दौरा दर्ज करने के लिए अधिकारी या मैदानी कर्मचारी के रूप में साइन इन करें।" },
};
const fill = (text: string, values: Record<string, string | number>) => text.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? ""));
type Section = { section_id: string; section: string; division: string };
type Summary = { decisive_sections: number; minimum_decisive_sections: number; precision: number | null };

export default function SectionOutcomeForm({ onSaved }: { onSaved?: () => void }) {
  const { locale } = useLocale();
  const w = copy[locale];
  const { status, role } = useAuth();
  const enabled = status === "signed-in" && (role === "officer" || role === "field_worker");
  const sections = useApi<{ items: Section[]; total: number }>(enabled ? "/field-checks/sections?limit=200" : null);
  const summary = useApi<Summary>(enabled ? "/field-checks/summary" : null);
  const [sectionId, setSectionId] = useState("");
  const [outcome, setOutcome] = useState<"yes" | "no" | "unclear" | "">("");
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Calcutta", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const id = useRef<string | null>(null);
  const selected = sectionId || sections.data?.items[0]?.section_id || "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!outcome || !selected) { setMessage(w.choose); return; }
    setSaving(true);
    id.current ??= crypto.randomUUID();
    try {
      const result = await apiFetch<{ ledger_missing: boolean }>("/field-checks/outcomes", { method: "POST", body: { id: id.current, section_id: selected, could_not_book: outcome, checked_on: date, note } });
      setMessage(result.ledger_missing ? w.pending : w.saved);
      if (!result.ledger_missing) { id.current = null; setNote(""); setOutcome(""); onSaved?.(); sections.reload(); }
      summary.reload();
    } catch { setMessage(w.error); }
    finally { setSaving(false); }
  }

  if (!enabled) return <p className="muted">{w.signIn}</p>;
  const progress = summary.data;
  return <section className="atlas-checks section-outcome-form">
    <h2>{w.title}</h2>
    {progress && <p>{progress.precision === null ? fill(w.progress, { n: progress.decisive_sections, min: progress.minimum_decisive_sections }) : fill(w.precision, { n: progress.decisive_sections, p: new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(progress.precision) })}</p>}
    {sections.error ? <p role="alert">{w.loadError}</p> : sections.data?.items.length === 0 ? <p>{w.empty}</p> : <form onSubmit={(event) => void submit(event)}>
      <label>{w.section}<select value={selected} onChange={(event) => { setSectionId(event.target.value); id.current = null; }} disabled={saving}>{sections.data?.items.map((row) => <option key={row.section_id} value={row.section_id}>{row.section}</option>)}</select></label>
      <fieldset disabled={saving}><legend>{w.question}</legend>{(["yes", "no", "unclear"] as const).map((value) => <label key={value}><input type="radio" name="booking-access-outcome" value={value} checked={outcome === value} onChange={() => { setOutcome(value); id.current = null; }} />{w[value]}</label>)}</fieldset>
      <label>{w.date}<input type="date" required value={date} max={today} disabled={saving} onChange={(event) => { setDate(event.target.value); id.current = null; }} /></label>
      <label>{w.note}<textarea value={note} disabled={saving} maxLength={2000} onChange={(event) => { setNote(event.target.value); id.current = null; }} /></label>
      <button className="button button-dark" type="submit" disabled={saving || !sections.live || !selected || !outcome}>{saving ? w.saving : w.save}</button>
    </form>}
    {message && <p role="status">{message}</p>}
    <WeeklyPriorityPanel onSaved={onSaved} />
  </section>;
}
