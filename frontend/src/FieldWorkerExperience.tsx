import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useLocale, type Locale, type MessageKey } from "./i18n";

type Page = "report" | "queue";
type Category = "no_water" | "tanker_missed" | "dirty_water" | "leak" | "other";
type QueueState = "queued" | "submitted" | "merged" | "spam" | "invalid" | "needs_location";
type FieldReport = {
  id: string;
  category: Category;
  details: string;
  areaId: string;
  householdId: string;
  language: Locale;
  createdAt: string;
  latitude?: number;
  longitude?: number;
  state: QueueState;
  complaintId?: string;
  error?: string;
};

const databaseName = "jallekha-field-worker";
const storeName = "reports";
const demoReporterId = "DEMO-FW-01";

const copy: Record<Locale, Record<string, string>> = {
  en: {
    title: "Record a household report", intro: "Capture a water issue on someone’s behalf. Reports save on this device and can sync later.", demo: "SYNTHETIC DEMO", worker: "Sample worker ID", online: "Online", offline: "Offline · reports stay on this device", newReport: "New report", queue: "Saved reports", category: "What happened?", chooseCategory: "Choose an issue", noWater: "No water", tankerMissed: "Tanker did not arrive", dirtyWater: "Water looks or smells dirty", leak: "Leak or broken pipe", other: "Other water issue", household: "Household reference code", householdHint: "Use a non-personal code, not a resident’s name or phone number.", area: "Ward or area reference (optional)", areaHint: "Example: DEMO-WARD-12", location: "Or share this device’s location", locationDenied: "Location was not shared. Enter a household reference instead.", locationAdded: "Location added after your selection", details: "What did the household report? (optional)", detailsHint: "Do not enter names, phone numbers, or other personal details.", language: "Report language", save: "Save report on this device", sample: "Load sample report", requiredIssue: "Choose an issue before saving.", requiredPlace: "Add a household reference or choose to share this device’s location.", saveError: "This browser could not save the report.", saved: "Saved on this device. It will sync when online.", sampleLoaded: "Synthetic sample loaded. Review it before saving.", syncing: "Syncing…", sync: "Sync saved reports", empty: "No field reports saved on this device yet.", queued: "Waiting to sync", submitted: "Sent to intake", merged: "Linked to an existing report", spam: "Flagged for review", invalid: "Could not send", needsLocation: "Needs a location check", reportId: "Report ID", createdAt: "Recorded", locationLabel: "Location shared by worker", privacy: "This demo uses the sample worker ID DEMO-FW-01 and marks submitted reports as synthetic. Do not enter personal details. Location is included only if you choose to share it.", syncError: "Could not reach intake. Reports remain saved here.", unknownError: "The intake service returned an unrecognized result.",
  },
  te: {
    title: "కుటుంబం తరఫున సమస్య నమోదు", intro: "మరొకరి నీటి సమస్యను నమోదు చేయండి. నివేదికలు ఈ పరికరంలో సేవ్ చేసి, తర్వాత పంపవచ్చు.", demo: "కల్పిత డెమో", worker: "నమూనా సిబ్బంది ID", online: "ఆన్‌లైన్", offline: "ఆఫ్‌లైన్ · నివేదికలు ఈ పరికరంలోనే ఉంటాయి", newReport: "కొత్త నివేదిక", queue: "సేవ్ చేసిన నివేదికలు", category: "ఏం జరిగింది?", chooseCategory: "సమస్యను ఎంచుకోండి", noWater: "నీరు రాలేదు", tankerMissed: "ట్యాంకర్ రాలేదు", dirtyWater: "నీరు మురికిగా ఉంది లేదా వాసన వస్తోంది", leak: "లీక్ లేదా పగిలిన పైపు", other: "ఇతర నీటి సమస్య", household: "కుటుంబ సూచిక కోడ్", householdHint: "వ్యక్తిగతం కాని కోడ్ వాడండి; పేరు లేదా ఫోన్ నంబరు వద్దు.", area: "వార్డు లేదా ప్రాంత సూచిక (ఐచ్ఛికం)", areaHint: "ఉదా: DEMO-WARD-12", location: "లేదా ఈ పరికరం స్థానాన్ని పంచుకోండి", locationDenied: "స్థానం పంచుకోలేదు. బదులుగా కుటుంబ కోడ్ ఇవ్వండి.", locationAdded: "మీరు ఎంచుకున్న తర్వాత స్థానం జోడించబడింది", details: "కుటుంబం తెలిపిన విషయం (ఐచ్ఛికం)", detailsHint: "పేరు, ఫోన్ నంబరు లేదా వ్యక్తిగత వివరాలు ఇవ్వకండి.", language: "నివేదిక భాష", save: "ఈ పరికరంలో సేవ్ చేయండి", sample: "నమూనా నివేదికను లోడ్ చేయండి", requiredIssue: "సేవ్ చేయడానికి ముందు సమస్యను ఎంచుకోండి.", requiredPlace: "కుటుంబ కోడ్ ఇవ్వండి లేదా ఈ పరికరం స్థానాన్ని పంచుకోండి.", saveError: "ఈ బ్రౌజర్ నివేదికను సేవ్ చేయలేకపోయింది.", saved: "ఈ పరికరంలో సేవ్ అయింది. ఆన్‌లైన్‌లో ఉన్నప్పుడు పంపబడుతుంది.", sampleLoaded: "కల్పిత నమూనా లోడ్ అయింది. సేవ్ చేసే ముందు పరిశీలించండి.", syncing: "పంపుతోంది…", sync: "సేవ్ చేసిన నివేదికలు పంపండి", empty: "ఈ పరికరంలో ఇంకా క్షేత్ర నివేదికలు లేవు.", queued: "పంపడానికి వేచి ఉంది", submitted: "ఇంటేక్‌కు పంపబడింది", merged: "ఇప్పటికే ఉన్న నివేదికతో కలిపింది", spam: "పరిశీలనకు గుర్తించింది", invalid: "పంపలేకపోయింది", needsLocation: "స్థానాన్ని పరిశీలించాలి", reportId: "నివేదిక ID", createdAt: "నమోదు సమయం", locationLabel: "సిబ్బంది పంచుకున్న స్థానం", privacy: "ఈ డెమోలో నమూనా సిబ్బంది ID DEMO-FW-01 వాడుతుంది; పంపిన నివేదికలు కల్పితంగా గుర్తించబడతాయి. వ్యక్తిగత వివరాలు ఇవ్వకండి. మీరు ఎంచుకుంటేనే స్థానం జోడించబడుతుంది.", syncError: "ఇంటేక్ సేవను చేరుకోలేకపోయింది. నివేదికలు ఇక్కడే సేవ్ అయ్యాయి.", unknownError: "ఇంటేక్ సేవ గుర్తించని ఫలితాన్ని ఇచ్చింది.",
  },
  ur: {
    title: "گھرانے کی طرف سے رپورٹ درج کریں", intro: "کسی دوسرے کے پانی کا مسئلہ درج کریں۔ رپورٹ اس آلے پر محفوظ ہوگی اور بعد میں بھیجی جاسکتی ہے۔", demo: "مصنوعی ڈیمو", worker: "نمونہ کارکن ID", online: "آن لائن", offline: "آف لائن · رپورٹیں اسی آلے پر رہیں گی", newReport: "نئی رپورٹ", queue: "محفوظ رپورٹیں", category: "کیا ہوا؟", chooseCategory: "مسئلہ منتخب کریں", noWater: "پانی نہیں آیا", tankerMissed: "ٹینکر نہیں آیا", dirtyWater: "پانی گندا لگتا ہے یا بدبو ہے", leak: "رساؤ یا ٹوٹا ہوا پائپ", other: "پانی کا دوسرا مسئلہ", household: "گھرانے کا حوالہ کوڈ", householdHint: "ایسا کوڈ دیں جس میں ذاتی معلومات نہ ہوں؛ نام یا فون نمبر نہیں۔", area: "وارڈ یا علاقے کا حوالہ (اختیاری)", areaHint: "مثلاً DEMO-WARD-12", location: "یا اس آلے کا مقام شیئر کریں", locationDenied: "مقام شیئر نہیں ہوا۔ اس کے بجائے گھرانے کا حوالہ درج کریں۔", locationAdded: "آپ کے انتخاب کے بعد مقام شامل کیا گیا", details: "گھرانے نے کیا بتایا؟ (اختیاری)", detailsHint: "نام، فون نمبر یا دوسری ذاتی معلومات نہ لکھیں۔", language: "رپورٹ کی زبان", save: "اس آلے پر رپورٹ محفوظ کریں", sample: "نمونہ رپورٹ لوڈ کریں", requiredIssue: "محفوظ کرنے سے پہلے مسئلہ منتخب کریں۔", requiredPlace: "گھرانے کا حوالہ درج کریں یا آلے کا مقام شیئر کریں۔", saveError: "یہ براؤزر رپورٹ محفوظ نہیں کرسکا۔", saved: "اس آلے پر محفوظ ہوگئی۔ آن لائن ہونے پر بھیج دی جائے گی۔", sampleLoaded: "مصنوعی نمونہ لوڈ ہوگیا۔ محفوظ کرنے سے پہلے دیکھ لیں۔", syncing: "بھیجا جارہا ہے…", sync: "محفوظ رپورٹیں بھیجیں", empty: "اس آلے پر ابھی کوئی میدانی رپورٹ محفوظ نہیں۔", queued: "بھیجنے کا انتظار", submitted: "انٹیک کو بھیج دیا گیا", merged: "موجودہ رپورٹ سے جوڑ دیا گیا", spam: "جائزے کے لیے نشان زد", invalid: "بھیجا نہیں جاسکا", needsLocation: "مقام کی جانچ ضروری ہے", reportId: "رپورٹ ID", createdAt: "درج کیا گیا", locationLabel: "کارکن کا شیئر کردہ مقام", privacy: "یہ ڈیمو نمونہ کارکن ID DEMO-FW-01 استعمال کرتا ہے؛ بھیجی گئی رپورٹیں مصنوعی نشان زد ہوں گی۔ ذاتی معلومات نہ دیں۔ مقام صرف آپ کے انتخاب پر شامل ہوتا ہے۔", syncError: "انٹیک سے رابطہ نہیں ہوا۔ رپورٹیں اسی آلے پر محفوظ ہیں۔", unknownError: "انٹیک سروس نے غیر متوقع نتیجہ دیا۔",
  },
  hi: {
    title: "परिवार की ओर से रिपोर्ट दर्ज करें", intro: "किसी और की पानी की समस्या दर्ज करें। रिपोर्ट इस डिवाइस पर सेव होगी और बाद में भेजी जा सकती है।", demo: "सिंथेटिक डेमो", worker: "नमूना कर्मचारी ID", online: "ऑनलाइन", offline: "ऑफ़लाइन · रिपोर्टें इसी डिवाइस पर रहेंगी", newReport: "नई रिपोर्ट", queue: "सेव की गई रिपोर्टें", category: "क्या हुआ?", chooseCategory: "समस्या चुनें", noWater: "पानी नहीं आया", tankerMissed: "टैंकर नहीं आया", dirtyWater: "पानी गंदा दिखता है या बदबू है", leak: "रिसाव या टूटा पाइप", other: "पानी की दूसरी समस्या", household: "परिवार संदर्भ कोड", householdHint: "बिना निजी जानकारी वाला कोड दें; नाम या फोन नंबर नहीं।", area: "वार्ड या इलाके का संदर्भ (ज़रूरी नहीं)", areaHint: "जैसे DEMO-WARD-12", location: "या इस डिवाइस की लोकेशन साझा करें", locationDenied: "लोकेशन साझा नहीं हुई। इसकी जगह परिवार संदर्भ कोड दें।", locationAdded: "आपकी सहमति के बाद लोकेशन जोड़ी गई", details: "परिवार ने क्या बताया? (ज़रूरी नहीं)", detailsHint: "नाम, फोन नंबर या दूसरी निजी जानकारी न लिखें।", language: "रिपोर्ट की भाषा", save: "इस डिवाइस पर रिपोर्ट सेव करें", sample: "नमूना रिपोर्ट लोड करें", requiredIssue: "सेव करने से पहले समस्या चुनें।", requiredPlace: "परिवार संदर्भ दें या इस डिवाइस की लोकेशन साझा करें।", saveError: "यह ब्राउज़र रिपोर्ट सेव नहीं कर पाया।", saved: "इस डिवाइस पर सेव हुई। ऑनलाइन होने पर भेजी जाएगी।", sampleLoaded: "सिंथेटिक नमूना लोड हुआ। सेव करने से पहले जाँचें।", syncing: "भेज रहे हैं…", sync: "सेव रिपोर्ट भेजें", empty: "इस डिवाइस पर अभी कोई मैदानी रिपोर्ट सेव नहीं है।", queued: "भेजने का इंतज़ार", submitted: "इंटेक को भेजी गई", merged: "मौजूदा रिपोर्ट से जोड़ी गई", spam: "समीक्षा के लिए चिह्नित", invalid: "भेज नहीं सके", needsLocation: "लोकेशन जांच ज़रूरी", reportId: "रिपोर्ट ID", createdAt: "दर्ज किया", locationLabel: "कर्मचारी द्वारा साझा लोकेशन", privacy: "यह डेमो नमूना कर्मचारी ID DEMO-FW-01 का उपयोग करता है; भेजी गई रिपोर्टें सिंथेटिक चिह्नित होंगी। निजी जानकारी न दें। लोकेशन तभी जुड़ेगी जब आप चुनेंगे।", syncError: "इंटेक से संपर्क नहीं हुआ। रिपोर्टें इसी डिवाइस पर सेव हैं।", unknownError: "इंटेक सेवा ने अनजान नतीजा दिया।",
  },
};

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(storeName, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open field report storage"));
  });
}

async function getReports(): Promise<FieldReport[]> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = db.transaction(storeName, "readonly").objectStore(storeName).getAll();
    request.onsuccess = () => resolve((request.result as FieldReport[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
    request.onerror = () => reject(request.error ?? new Error("Could not read field reports"));
  });
}

async function saveReport(report: FieldReport): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put(report);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not save field report"));
  });
}

function createId(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function stateText(report: FieldReport, words: Record<string, string>): string {
  return words[report.state] ?? words.queued;
}

export default function FieldWorkerExperience({ page, onNavigate }: { page: Page; onNavigate: (key: MessageKey) => void }) {
  const { locale } = useLocale();
  const words = copy[locale];
  const [reports, setReports] = useState<FieldReport[]>([]);
  const [category, setCategory] = useState<Category | "">("");
  const [details, setDetails] = useState("");
  const [householdId, setHouseholdId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [language, setLanguage] = useState<Locale>(locale);
  const [position, setPosition] = useState<{ latitude: number; longitude: number } | null>(null);
  const [message, setMessage] = useState("");
  const [storageReady, setStorageReady] = useState(false);
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);
  const [syncing, setSyncing] = useState(false);
  const syncingRef = useRef(false);
  const syncReportsRef = useRef<(items: FieldReport[]) => Promise<void>>(async () => undefined);

  const refresh = useCallback(async () => {
    try {
      setReports(await getReports());
      setStorageReady(true);
    } catch {
      setStorageReady(false);
      setMessage(words.saveError);
    }
  }, [words.saveError]);

  const syncReports = useCallback(async (items: FieldReport[]) => {
    if (!navigator.onLine || syncingRef.current) return;
    const pending = items.filter((report) => report.state === "queued");
    if (pending.length === 0) return;
    syncingRef.current = true;
    setSyncing(true);
    const endpoint = (import.meta.env.VITE_INTAKE_URL as string | undefined) || "/intake/batch";
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: pending.map((report) => ({
          client_id: report.id,
          client_created_at: report.createdAt,
          channel: "field_worker",
          reporter_id: demoReporterId,
          household_id: report.householdId || undefined,
          area_id: report.areaId || undefined,
          category: report.category,
          text: report.details,
          language_hint: report.language,
          ...(report.latitude !== undefined && report.longitude !== undefined ? { lat: report.latitude, lon: report.longitude } : {}),
          is_synthetic: true,
        })) }),
      });
      if (!response.ok) throw new Error("Intake service unavailable");
      const payload = await response.json() as { results?: Array<{ client_id?: string; status?: string; complaint_id?: string; complaint_status?: string; error?: string }> };
      for (const result of payload.results ?? []) {
        const current = pending.find((report) => report.id === result.client_id);
        if (!current) continue;
        const state: QueueState = result.status === "invalid" ? "invalid" : result.status === "spam" ? "spam" : result.status === "merged" || result.status === "duplicate" ? "merged" : result.complaint_status === "awaiting_location" ? "needs_location" : "submitted";
        await saveReport({ ...current, state, complaintId: result.complaint_id, error: result.error });
      }
      await refresh();
    } catch {
      setMessage(words.syncError);
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [refresh, words.syncError]);

  useEffect(() => { syncReportsRef.current = syncReports; }, [syncReports]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  useEffect(() => {
    const updateOnline = () => setOnline(navigator.onLine);
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
    };
  }, []);
  useEffect(() => {
    if (online && storageReady) void getReports().then((items) => { setReports(items); void syncReportsRef.current(items); });
  }, [online, storageReady]);

  function addLocation() {
    if (!navigator.geolocation) { setMessage(words.locationDenied); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => { setPosition({ latitude: coords.latitude, longitude: coords.longitude }); setMessage(words.locationAdded); },
      () => setMessage(words.locationDenied),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  }

  function loadSample() {
    setCategory("no_water");
    setHouseholdId("DEMO-HH-001");
    setAreaId("DEMO-WARD-12");
    setDetails("Synthetic sample: household reports no water today.");
    setPosition(null);
    setMessage(words.sampleLoaded);
  }

  async function submitReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!category) { setMessage(words.requiredIssue); return; }
    if (!householdId.trim() && !position) { setMessage(words.requiredPlace); return; }
    const report: FieldReport = {
      id: createId(), category, details: details.trim(), householdId: householdId.trim(), areaId: areaId.trim(), language,
      createdAt: new Date().toISOString(), ...(position ?? {}), state: "queued",
    };
    try {
      await saveReport(report);
      const updated = [report, ...reports];
      setReports(updated);
      setStorageReady(true);
      setCategory(""); setDetails(""); setHouseholdId(""); setAreaId(""); setPosition(null); setLanguage(locale);
      setMessage(words.saved);
      onNavigate("fieldWorkerQueue");
      if (online) void syncReports(updated);
    } catch {
      setMessage(words.saveError);
    }
  }

  const categoryLabels: Record<Category, string> = { no_water: words.noWater, tanker_missed: words.tankerMissed, dirty_water: words.dirtyWater, leak: words.leak, other: words.other };
  const statusClass: Record<QueueState, string> = { queued: "queued", submitted: "submitted", merged: "submitted", spam: "invalid", invalid: "invalid", needs_location: "needs_location" };

  return (
    <div className="field-worker-page">
      <div className="field-worker-status-row">
        <span className={online ? "resident-connectivity online" : "resident-connectivity offline"}><i />{online ? words.online : words.offline}</span>
        <span className="field-worker-demo-badge">{words.demo}</span>
      </div>
      <div className="field-worker-heading"><div><p className="eyebrow">{words.worker}: {demoReporterId}</p><h1>{words.title}</h1><p className="muted">{words.intro}</p></div><div className="field-worker-tabs"><button className={page === "report" ? "button button-dark" : "button button-secondary"} onClick={() => onNavigate("fieldWorkerNewReport")}>{words.newReport}</button><button className={page === "queue" ? "button button-dark" : "button button-secondary"} onClick={() => onNavigate("fieldWorkerQueue")}>{words.queue} ({reports.length})</button></div></div>
      {page === "report" && <section className="field-worker-form-card">
        <form onSubmit={(event) => void submitReport(event)}>
          <label>{words.category}<select value={category} onChange={(event) => setCategory(event.target.value as Category | "")}><option value="">{words.chooseCategory}</option>{(Object.keys(categoryLabels) as Category[]).map((item) => <option key={item} value={item}>{categoryLabels[item]}</option>)}</select></label>
          <label>{words.household}<input maxLength={64} value={householdId} onChange={(event) => setHouseholdId(event.target.value)} placeholder={words.householdHint} /></label>
          <label>{words.area}<input maxLength={64} value={areaId} onChange={(event) => setAreaId(event.target.value)} placeholder={words.areaHint} /></label>
          <button className="button button-secondary" type="button" onClick={addLocation}>{position ? words.locationAdded : words.location}</button>
          {position && <p className="field-worker-location-readout">{words.locationLabel}: {position.latitude.toFixed(4)}, {position.longitude.toFixed(4)}</p>}
          <label>{words.details}<textarea maxLength={500} rows={4} value={details} onChange={(event) => setDetails(event.target.value)} placeholder={words.detailsHint} /></label>
          <label>{words.language}<select value={language} onChange={(event) => setLanguage(event.target.value as Locale)}>{(["en", "te", "ur", "hi"] as const).map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></label>
          <p className="resident-privacy-note">{words.privacy}</p>
          {message && <p role="status" className="resident-status-message">{message}</p>}
          <div className="field-worker-form-actions"><button className="button button-dark" type="submit" disabled={!storageReady}>{words.save}</button><button className="text-button" type="button" onClick={loadSample}>{words.sample}</button></div>
        </form>
      </section>}
      {page === "queue" && <section className="field-worker-queue-section">
        <div className="field-worker-queue-heading"><div><h2>{words.queue}</h2><p className="muted">{online ? words.online : words.offline}</p></div><button className="button button-secondary" onClick={() => void syncReports(reports)} disabled={syncing || !online || reports.every((report) => report.state !== "queued")}>{syncing ? words.syncing : words.sync}</button></div>
        {message && <p role="status" className="resident-status-message">{message}</p>}
        {reports.length === 0 ? <p className="resident-empty-state">{words.empty}</p> : <div className="resident-request-list">{reports.map((report) => <article className="resident-request-card field-worker-report-card" key={report.id}>
          <div className="resident-request-card-head"><span className={`resident-request-state ${statusClass[report.state]}`}>{stateText(report, words)}</span><time dateTime={report.createdAt}>{new Date(report.createdAt).toLocaleString(locale)}</time></div>
          <h2>{categoryLabels[report.category]}</h2>
          <p>{report.areaId || report.householdId || words.locationLabel}</p>
          {report.details && <p>{report.details}</p>}
          <div className="resident-request-meta"><span>{words.reportId}: <code>{report.complaintId ?? report.id.slice(0, 8)}</code></span></div>
          {report.error && <small>{report.error}</small>}
        </article>)}</div>}
      </section>}
      <p className="resident-honesty-note">{words.privacy}</p>
    </div>
  );
}
