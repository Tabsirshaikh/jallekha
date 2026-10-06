import { useMemo } from "react";
import { useLocale, type Locale, type MessageKey } from "./i18n";
import { useAuth } from "./auth";
import { useApi } from "./useApi";
import { adaptLiveNeed, type EvidenceDataset } from "./evidenceAdapter";
import evidence from "./data/u5Evidence.json";
import sectionChecks from "./data/u5SectionChecks.json";
import "./EvidenceExperience.css";

const snapshot = evidence as EvidenceDataset;
const checkCopy = {
  en: { checks: "Sections with low bookings to check", checksNote: "Few bookings per connection compared with similar sections" },
  te: { checks: "తక్కువ బుకింగ్‌లు ఉన్న, పరిశీలించాల్సిన విభాగాలు", checksNote: "ఇలాంటి విభాగాలతో పోలిస్తే కనెక్షన్‌కు తక్కువ బుకింగ్‌లు" },
  ur: { checks: "کم بکنگ والے سیکشن جن کی جانچ کرنی ہے", checksNote: "ملتے جلتے سیکشنوں سے فی کنکشن کم بکنگ" },
  hi: { checks: "कम बुकिंग वाले सेक्शन जिनकी जाँच करनी है", checksNote: "मिलते-जुलते सेक्शन की तुलना में प्रति कनेक्शन कम बुकिंग" },
};
type Plan = { plan_id: string; day: string; status: string; flags_total: number; checked_total: number };

const copy = {
  en: { title: "Today at a glance", intro: "What needs your attention today. Click a card to open it.", signIn: "Sign in as an officer to see today's live numbers.", rising: "Wards where need may be rising", risingNone: "No ward shows 2 or more warning signs", checks: "Wards with low bookings to check", checksNote: "Far fewer bookings than similar wards", top: "Top {n} areas take {p} of tankers", topNote: "Booking concentration", plan: "Latest plan", planNone: "No plan yet", planDraft: "{day}: waiting for your approval", planApproved: "{day}: approved", planFlags: "{n} groups to check before approval", open: "Open", steps: "What to do today", step1: "Check the need map", step1Note: "See where need may be rising and why", step2: "Review and approve the plan", step2Note: "Check the flagged groups, then approve with a reason", step3: "Answer questions and contests", step3Note: "Explain a decision to a resident or councillor", more: "Also", forecast: "Forecast and shortage warning", impact: "Impact of the fair plan", liveDash: "—" },
  te: { title: "ఈరోజు ఒక్క చూపులో", intro: "ఈరోజు మీ దృష్టి అవసరమైనవి. తెరవడానికి కార్డుపై నొక్కండి.", signIn: "ఈరోజు ప్రత్యక్ష సంఖ్యల కోసం అధికారిగా సైన్ ఇన్ చేయండి.", rising: "అవసరం పెరుగుతుండవచ్చు ఉన్న వార్డులు", risingNone: "ఏ వార్డులోనూ 2 లేదా ఎక్కువ హెచ్చరిక సూచనలు లేవు", checks: "తక్కువ బుకింగ్‌లు ఉన్న, పరిశీలించాల్సిన వార్డులు", checksNote: "ఇలాంటి వార్డుల కంటే చాలా తక్కువ బుకింగ్‌లు", top: "పై {n} ప్రాంతాలు ట్యాంకర్లలో {p} తీసుకుంటున్నాయి", topNote: "బుకింగ్ కేంద్రీకరణ", plan: "తాజా ప్రణాళిక", planNone: "ఇంకా ప్రణాళిక లేదు", planDraft: "{day}: మీ ఆమోదం కోసం వేచి ఉంది", planApproved: "{day}: ఆమోదించబడింది", planFlags: "ఆమోదానికి ముందు పరిశీలించాల్సిన {n} గుంపులు", open: "తెరవండి", steps: "ఈరోజు చేయాల్సినవి", step1: "అవసర పటం చూడండి", step1Note: "అవసరం ఎక్కడ, ఎందుకు పెరుగుతోందో చూడండి", step2: "ప్రణాళికను పరిశీలించి ఆమోదించండి", step2Note: "గుర్తించిన గుంపులను పరిశీలించి, కారణంతో ఆమోదించండి", step3: "ప్రశ్నలు, అభ్యంతరాలకు సమాధానం ఇవ్వండి", step3Note: "నివాసికి లేదా కౌన్సిలర్‌కు నిర్ణయాన్ని వివరించండి", more: "ఇంకా", forecast: "అంచనా మరియు కొరత హెచ్చరిక", impact: "న్యాయమైన ప్రణాళిక ప్రభావం", liveDash: "—" },
  ur: { title: "آج ایک نظر میں", intro: "آج کن چیزوں پر توجہ چاہیے۔ کھولنے کے لیے کارڈ پر کلک کریں۔", signIn: "آج کے براہِ راست اعداد دیکھنے کے لیے افسر کے طور پر سائن ان کریں۔", rising: "وارڈ جہاں ضرورت بڑھ رہی ہو سکتی ہے", risingNone: "کسی وارڈ میں 2 یا زیادہ انتباہی اشارے نہیں", checks: "کم بکنگ والے وارڈ جن کی جانچ ہونی ہے", checksNote: "ملتے جلتے وارڈوں سے بہت کم بکنگ", top: "سب سے اوپر کے {n} علاقے ٹینکروں کا {p} لیتے ہیں", topNote: "بکنگ کا ارتکاز", plan: "تازہ منصوبہ", planNone: "ابھی کوئی منصوبہ نہیں", planDraft: "{day}: آپ کی منظوری کا منتظر", planApproved: "{day}: منظور شدہ", planFlags: "منظوری سے پہلے {n} گروہوں کی جانچ", open: "کھولیں", steps: "آج کیا کرنا ہے", step1: "ضرورت کا نقشہ دیکھیں", step1Note: "دیکھیں ضرورت کہاں اور کیوں بڑھ رہی ہے", step2: "منصوبہ دیکھیں اور منظور کریں", step2Note: "نشان زدہ گروہ جانچیں، پھر وجہ کے ساتھ منظور کریں", step3: "سوالات اور اعتراضات کا جواب دیں", step3Note: "رہائشی یا کونسلر کو فیصلہ سمجھائیں", more: "مزید", forecast: "پیش گوئی اور قلت کی وارننگ", impact: "منصفانہ منصوبے کا اثر", liveDash: "—" },
  hi: { title: "आज एक नज़र में", intro: "आज किन बातों पर ध्यान देना है। खोलने के लिए कार्ड पर क्लिक करें।", signIn: "आज के लाइव आँकड़े देखने के लिए अधिकारी के रूप में साइन इन करें।", rising: "वार्ड जहाँ ज़रूरत बढ़ रही हो सकती है", risingNone: "किसी वार्ड में 2 या अधिक चेतावनी संकेत नहीं", checks: "कम बुकिंग वाले वार्ड जिनकी जाँच करनी है", checksNote: "मिलते-जुलते वार्डों से बहुत कम बुकिंग", top: "शीर्ष {n} इलाके टैंकरों का {p} लेते हैं", topNote: "बुकिंग संकेंद्रण", plan: "नवीनतम योजना", planNone: "अभी कोई योजना नहीं", planDraft: "{day}: आपकी मंज़ूरी का इंतज़ार", planApproved: "{day}: मंज़ूर", planFlags: "मंज़ूरी से पहले {n} समूहों की जाँच", open: "खोलें", steps: "आज क्या करना है", step1: "ज़रूरत का नक्शा देखें", step1Note: "देखें ज़रूरत कहाँ और क्यों बढ़ रही है", step2: "योजना देखें और मंज़ूर करें", step2Note: "चिह्नित समूह जाँचें, फिर कारण के साथ मंज़ूर करें", step3: "सवालों और आपत्तियों का जवाब दें", step3Note: "निवासी या पार्षद को निर्णय समझाएँ", more: "और", forecast: "पूर्वानुमान और कमी की चेतावनी", impact: "निष्पक्ष योजना का असर", liveDash: "—" },
} satisfies Record<Locale, Record<string, string>>;

const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k: string) => String(v[k] ?? ""));

export default function OfficerOverview({ onNavigate }: { onNavigate: (key: MessageKey) => void }) {
  const { locale } = useLocale();
  const w = { ...copy[locale], ...checkCopy[locale] };
  const nf = new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale);
  const pf = new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { style: "percent", maximumFractionDigits: 0 });
  const { status } = useAuth();
  const enabled = status !== "anonymous" && status !== "rejected";
  const liveApi = useApi<unknown>(enabled ? "/atlas/live" : null);
  const plansApi = useApi<{ items?: Plan[] }>(enabled ? "/plans?limit=200" : null);
  const checksApi = useApi<{ flagged_count: number }>(enabled ? "/underserved/section-checks?limit=1" : null);
  const checkCount = checksApi.live && Number.isFinite(checksApi.data?.flagged_count) ? checksApi.data!.flagged_count : sectionChecks.items.filter((row) => row.field_check_candidate).length;
  const need = useMemo(() => (liveApi.live ? adaptLiveNeed(liveApi.data) : null), [liveApi.live, liveApi.data]);
  const rising = need ? [...need.wards.values()].filter((x) => x.rising).length : null;
  const conc = need?.concentration;
  const topN = conc ? conc.topSections : snapshot.summary.equity.top_section_count;
  const topP = conc ? conc.topShare : snapshot.summary.equity.top_booking_share;
  const plans = plansApi.live && Array.isArray(plansApi.data?.items) ? plansApi.data!.items! : null;
  const latest = plans && plans.length ? [...plans].sort((a, b) => b.day.localeCompare(a.day))[0] : null;

  const card = (key: MessageKey, label: string, value: string, note: string, tone = "") => (
    <button className={"overview-card " + tone} onClick={() => onNavigate(key)}>
      <span className="overview-label">{label}</span>
      <strong className="overview-value">{value}</strong>
      <span className="overview-note">{note}</span>
    </button>
  );
  const step = (n: number, key: MessageKey, title: string, note: string) => (
    <li><button onClick={() => onNavigate(key)}><span className="overview-step">{n}</span><span><strong>{title}</strong><small>{note}</small></span><span aria-hidden="true">→</span></button></li>
  );

  return (
    <div className="overview-page">
      <header><h1>{w.title}</h1><p className="muted">{w.intro}</p></header>
      {!enabled && <p className="atlas-hint" role="note">{w.signIn}</p>}
      <div className="overview-cards">
        {card("officerWaterAccess", w.rising, rising === null ? w.liveDash : nf.format(rising), rising === 0 ? w.risingNone : "", rising ? "alert" : "")}
        {card("officerWaterAccess", w.checks, nf.format(checkCount), w.checksNote, "warn")}
        {card("officerWaterAccess", w.topNote, topP === null ? w.liveDash : pf.format(topP), fill(w.top, { n: nf.format(topN), p: topP === null ? "—" : pf.format(topP) }))}
        {card("officerAllocationPlan", w.plan, latest ? (latest.status === "APPROVED" ? fill(w.planApproved, { day: latest.day }) : fill(w.planDraft, { day: latest.day })) : plans ? w.planNone : w.liveDash,
          latest && latest.status !== "APPROVED" ? fill(w.planFlags, { n: nf.format(Math.max(0, latest.flags_total - latest.checked_total)) }) : "")}
      </div>
      <section className="overview-steps">
        <h2>{w.steps}</h2>
        <ol>
          {step(1, "officerWaterAccess", w.step1, w.step1Note)}
          {step(2, "officerAllocationPlan", w.step2, w.step2Note)}
          {step(3, "officerExplain", w.step3, w.step3Note)}
        </ol>
        <p className="overview-more"><span className="muted">{w.more}:</span> <button className="text-button" onClick={() => onNavigate("officerForecast")}>{w.forecast}</button> · <button className="text-button" onClick={() => onNavigate("officerImpact")}>{w.impact}</button></p>
      </section>
    </div>
  );
}
