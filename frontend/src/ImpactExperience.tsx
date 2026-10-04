import { useMemo, useState } from "react";
import snapshot from "./data/u9Impact.json";
import { useAuth } from "./auth";
import DataSourceChip from "./DataSource";
import { useLocale, type Locale } from "./i18n";
import { impactFromApi, METRICS, policyDifference, type ApiImpact, type ImpactRow, type Metric, type RealBaselines } from "./impactAdapter";
import { canFetchOfficerData, liveReason, liveReasonCopy } from "./liveReason";
import { useApi } from "./useApi";
import "./ImpactExperience.css";

const snapshotRows = snapshot.rows as ImpactRow[];
const snapshotBaselines = snapshot.real_baselines as RealBaselines;
const replayOptions = [...new Set(snapshotRows.map((row)=>row.replay))];

const basisCopy = {
  en:{title:"Observed data context",delivered:"Delivered / booked",recent:"Jun–Aug 2026",bookingGini:"Booking concentration (Gini)",source:"Source"},
  te:{title:"గమనించిన డేటా సందర్భం",delivered:"పంపిణీ / బుకింగ్‌లు",recent:"జూన్–ఆగస్టు 2026",bookingGini:"బుకింగ్ కేంద్రీకరణ (Gini)",source:"మూలం"},
  ur:{title:"مشاہدہ شدہ ڈیٹا",delivered:"فراہم / بکنگ",recent:"جون تا اگست 2026",bookingGini:"بکنگ کا ارتکاز (Gini)",source:"ماخذ"},
  hi:{title:"देखे गए डेटा का संदर्भ",delivered:"डिलीवरी / बुकिंग",recent:"जून–अगस्त 2026",bookingGini:"बुकिंग का संकेंद्रण (Gini)",source:"स्रोत"},
} satisfies Record<Locale,Record<string,string>>;

const copy = {
  en:{title:"Policy impact sandbox",intro:"Compare simulated service, waiting time, fairness and route-efficiency measures across replay policies.",demo:"A8 · SIMULATION",caveat:"These are replay results across random seeds, not observed outcomes or a forecast. Baseline booking totals are real; all policy results shown here are simulations.",scenario:"Scenario",replay:"Replay",metric:"Measure",seeds:"Random seeds",mean:"Mean",range:"Across seeds",baseline:"B1 reference",difference:"Difference vs B1",source:"Source",duplicates:"Duplicate merge impact",unavailable:"Not available",unavailableNote:"This replay has no complaints and duplicate calibration is not available.",empty:"No results for this selection.",label:"All displayed result values are SIMULATION.",metricNames:{served_share:"Share of bookings served",need_weighted_unmet_share:"Need-weighted unmet share",mean_wait_days:"Mean wait (days)",gini_fill_rate:"Gini of fill rate",jain_fill_rate:"Jain fairness index",worst_group_fill_rate:"Worst-group fill rate",km_per_kl:"Route km per kL"},replays:{main_2025:"2025 replay",secondary_2023:"2023 replay"},scenarios:{fleet:"Fleet capacity",tight:"Tight capacity"}},
  te:{title:"విధాన ప్రభావ నమూనా",intro:"పునఃప్లే విధానాల మధ్య సేవ, నిరీక్షణ, సమానత్వం, మార్గ సామర్థ్యాన్ని పోల్చండి.",demo:"A8 · అనుకరణ",caveat:"ఇవి వేర్వేరు యాదృచ్ఛిక విత్తనాలతో చేసిన పునఃప్లే ఫలితాలు; గమనించిన ఫలితాలు లేదా అంచనా కాదు. బుకింగ్ మొత్తాలు నిజమైనవి; ఇక్కడి విధాన ఫలితాలు అనుకరణ.",scenario:"పరిస్థితి",replay:"పునఃప్లే",metric:"కొలమానం",seeds:"యాదృచ్ఛిక విత్తనాలు",mean:"సగటు",range:"విత్తనాల పరిధి",baseline:"B1 ఆధారం",difference:"B1తో తేడా",source:"మూలం",duplicates:"నకిలీ ఫిర్యాదుల కలపడం",unavailable:"అందుబాటులో లేదు",unavailableNote:"ఈ పునఃప్లేలో ఫిర్యాదులు లేవు; నకిలీ ఫిర్యాదుల అంచనా అందుబాటులో లేదు.",empty:"ఈ ఎంపికకు ఫలితాలు లేవు.",label:"చూపిన ఫలితాలన్నీ అనుకరణ.",metricNames:{served_share:"సేవ అందిన బుకింగ్‌ల వాటా",need_weighted_unmet_share:"అవసర బరువుతో సేవ అందని వాటా",mean_wait_days:"సగటు నిరీక్షణ (రోజులు)",gini_fill_rate:"పంపిణీ అసమానత (Gini)",jain_fill_rate:"న్యాయ సూచిక (Jain)",worst_group_fill_rate:"అత్యల్ప సమూహ సేవ వాటా",km_per_kl:"ప్రతి kLకు మార్గ కి.మీ."},replays:{main_2025:"2025 పునఃప్లే",secondary_2023:"2023 పునఃప్లే"},scenarios:{fleet:"బృంద సామర్థ్యం",tight:"తక్కువ సామర్థ్యం"}},
  ur:{title:"پالیسی اثر کا نمونہ",intro:"دوبارہ چلائی گئی پالیسیوں میں خدمت، انتظار، انصاف اور راستے کی کارکردگی کا موازنہ کریں۔",demo:"A8 · تخمینہ",caveat:"یہ مختلف اتفاقی بیجوں کے ساتھ دوبارہ چلانے کے نتائج ہیں، مشاہدہ شدہ نتائج یا پیش گوئی نہیں۔ بکنگ کی بنیادی تعداد حقیقی ہے؛ یہاں دکھائے گئے پالیسی نتائج تخمینی ہیں۔",scenario:"منظرنامہ",replay:"دوبارہ چلانا",metric:"پیمانہ",seeds:"اتفاقی بیج",mean:"اوسط",range:"بیجوں کی حد",baseline:"B1 حوالہ",difference:"B1 سے فرق",source:"ماخذ",duplicates:"نقل شکایات کا اثر",unavailable:"دستیاب نہیں",unavailableNote:"اس دوبارہ چلانے میں شکایات نہیں اور نقل کی جانچ دستیاب نہیں۔",empty:"اس انتخاب کے لیے نتائج نہیں۔",label:"تمام دکھائے گئے نتائج تخمینی ہیں۔",metricNames:{served_share:"فراہم شدہ بکنگ کا حصہ",need_weighted_unmet_share:"ضرورت کے وزن کے مطابق غیر فراہم شدہ حصہ",mean_wait_days:"اوسط انتظار (دن)",gini_fill_rate:"فراہمی کا Gini",jain_fill_rate:"انصاف کا Jain اشاریہ",worst_group_fill_rate:"سب سے کم گروپ کی فراہمی",km_per_kl:"ہر kL کے لیے راستے کے کلومیٹر"},replays:{main_2025:"2025 دوبارہ چلانا",secondary_2023:"2023 دوبارہ چلانا"},scenarios:{fleet:"بیڑے کی گنجائش",tight:"کم گنجائش"}},
  hi:{title:"नीति प्रभाव सैंडबॉक्स",intro:"रीप्ले नीतियों में सेवा, प्रतीक्षा, निष्पक्षता और मार्ग दक्षता की तुलना करें।",demo:"A8 · सिमुलेशन",caveat:"ये अलग-अलग रैंडम सीड के साथ रीप्ले परिणाम हैं, देखे गए नतीजे या पूर्वानुमान नहीं। बुकिंग के आधार आँकड़े वास्तविक हैं; यहाँ के नीति परिणाम सिमुलेशन हैं।",scenario:"परिदृश्य",replay:"रीप्ले",metric:"माप",seeds:"रैंडम सीड",mean:"औसत",range:"सीड की सीमा",baseline:"B1 संदर्भ",difference:"B1 से अंतर",source:"स्रोत",duplicates:"डुप्लिकेट शिकायतों का असर",unavailable:"उपलब्ध नहीं",unavailableNote:"इस रीप्ले में शिकायतें नहीं हैं और डुप्लिकेट मापन उपलब्ध नहीं है।",empty:"इस चयन के लिए परिणाम नहीं हैं।",label:"दिखाए गए सभी परिणाम सिमुलेशन हैं।",metricNames:{served_share:"सेवा मिली बुकिंग का हिस्सा",need_weighted_unmet_share:"ज़रूरत के भार के अनुसार अधूरी सेवा",mean_wait_days:"औसत प्रतीक्षा (दिन)",gini_fill_rate:"सेवा का Gini",jain_fill_rate:"निष्पक्षता Jain सूचकांक",worst_group_fill_rate:"सबसे कम समूह की सेवा",km_per_kl:"प्रति kL मार्ग किमी"},replays:{main_2025:"2025 रीप्ले",secondary_2023:"2023 रीप्ले"},scenarios:{fleet:"बेड़े की क्षमता",tight:"सीमित क्षमता"}},
} satisfies Record<Locale, { title:string; intro:string; demo:string; caveat:string; scenario:string; replay:string; metric:string; seeds:string; mean:string; range:string; baseline:string; difference:string; source:string; duplicates:string; unavailable:string; unavailableNote:string; empty:string; label:string; metricNames:Record<Metric,string>; replays:Record<string,string>; scenarios:Record<string,string> }>;

export default function ImpactExperience() {
  const { locale } = useLocale();
  const { status, role } = useAuth();
  const w = copy[locale];
  const basisWords = basisCopy[locale];
  const [replay,setReplay] = useState(snapshotRows[0]?.replay ?? "main_2025");
  const [scenario,setScenario] = useState(snapshotRows[0]?.scenario ?? "fleet");
  const [metric,setMetric] = useState<Metric>("served_share");
  // Live A8 results for this replay and scenario when an officer is signed in; the committed snapshot otherwise.
  const api = useApi<ApiImpact>(canFetchOfficerData(status, role) ? `/impact?replay=${encodeURIComponent(replay)}&scenario=${encodeURIComponent(scenario)}` : null);
  const liveView = useMemo(()=>api.live && api.data ? impactFromApi(api.data) : null,[api.live,api.data]);
  const live = liveView !== null;
  const reason = live ? null : liveReason(status, role, api.error);
  const baselines = liveView?.baselines ?? snapshotBaselines;
  const sourceText = live ? `GET /impact · ${snapshot.summary_source}` : snapshot.source;
  const availableScenarios = [...new Set(snapshotRows.filter((row)=>row.replay===replay).map((row)=>row.scenario))];
  const selected = useMemo(()=>liveView ? liveView.rows : snapshotRows.filter((row)=>row.replay===replay&&row.scenario===scenario),[liveView,replay,scenario]);
  const base = selected.find((row)=>row.policy==="B1");
  const replayDeliveredShare = baselines.delivered_share[replay] ?? null;
  const percentFmt = (value:number|null|undefined) => value===null||value===undefined?"—":new Intl.NumberFormat(locale,{style:"percent",maximumFractionDigits:2}).format(value);
  const fmt = (value:number|null) => {
    if(value===null) return "—";
    const percent = ["served_share","need_weighted_unmet_share","gini_fill_rate","jain_fill_rate","worst_group_fill_rate"].includes(metric);
    return percent ? new Intl.NumberFormat(locale,{style:"percent",maximumFractionDigits:2}).format(value) : new Intl.NumberFormat(locale,{maximumFractionDigits:3}).format(value);
  };
  return <div className="impact-page">
    <header className="impact-heading"><div><p className="eyebrow">F19 · A8</p><h1>{w.title}</h1><p className="muted">{w.intro}</p></div><div className="impact-heading-tags"><DataSourceChip state={{ live, loading: status==="checking" || api.loading, error: api.error }} /><span className="forecast-demo-badge">{w.demo}</span></div></header>
    {reason&&<p className="impact-live-reason" role="note">{liveReasonCopy[locale][reason]}</p>}
    <div className="impact-notice"><strong>{w.caveat}</strong><span>{w.source}: {sourceText}</span></div>
    <section className="impact-baseline"><div className="impact-baseline-heading"><h2>{basisWords.title}</h2><span>{basisWords.source}: {baselines.source}</span></div><div className="impact-baseline-grid"><article><span>{basisWords.delivered} · {replay==="main_2025"?w.replays.main_2025:w.replays.secondary_2023}</span><strong>{percentFmt(replayDeliveredShare)}</strong><small className="source-tag real">REAL</small></article><article><span>{basisWords.delivered} · {basisWords.recent}</span><strong>{percentFmt(baselines.delivered_share.jun_aug_2026)}</strong><small className="source-tag real">REAL</small></article><article><span>{basisWords.bookingGini}</span><strong>{baselines.booking_gini_sections===null?"—":baselines.booking_gini_sections.toFixed(3)}</strong><small className="source-tag derived">{baselines.booking_gini_basis}</small></article></div></section>
    <section className="impact-controls"><label>{w.replay}<select value={replay} onChange={(event)=>{const value=event.target.value;setReplay(value);const next=snapshotRows.find((row)=>row.replay===value)?.scenario;if(next)setScenario(next);}}>{replayOptions.map((value)=><option value={value} key={value}>{w.replays[value as keyof typeof w.replays] ?? value}</option>)}</select></label><label>{w.scenario}<select value={scenario} onChange={(event)=>setScenario(event.target.value)}>{availableScenarios.map((value)=><option value={value} key={value}>{w.scenarios[value as keyof typeof w.scenarios] ?? value}</option>)}</select></label><label>{w.metric}<select value={metric} onChange={(event)=>setMetric(event.target.value as Metric)}>{METRICS.map((value)=><option value={value} key={value}>{w.metricNames[value]}</option>)}</select></label></section>
    <section className="impact-cards" aria-label={w.metricNames[metric]}>{selected.length===0?<p className="muted">{w.empty}</p>:selected.map((row)=>{const value=row.metrics[metric];return <article className="impact-card" key={row.policy}><div className="impact-card-head"><h2>{row.policy}</h2><span className="source-tag simulation">{value.basis}</span></div>{liveView?.policies[row.policy]&&<p className="impact-policy">{liveView.policies[row.policy]}</p>}<strong className="impact-value">{fmt(value.mean)}</strong><span className="impact-metric-label">{w.metricNames[metric]}</span><div className="impact-range"><span>{w.range}</span><strong>{fmt(value.min)} – {fmt(value.max)}</strong></div><small>{row.seed_count ?? "—"} {w.seeds} · {value.basis}</small>{base&&row.policy!=="B1"&&<small>{w.difference}: {fmt(policyDifference(value.mean,base.metrics[metric].mean))} · {value.basis}</small>}</article>;})}</section>
    <section className="impact-unavailable"><span className="source-tag">UNAVAILABLE</span><div><h2>{w.duplicates}</h2><p>{liveView ? liveView.unavailableReason : `${snapshot.unavailable.reason} ${w.unavailableNote}`}</p></div></section>
    <p className="impact-footer">{w.label} · {w.source}: <code>{sourceText}</code></p>
  </div>;
}
