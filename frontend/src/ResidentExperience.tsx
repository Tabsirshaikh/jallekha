import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useLocale, type Locale, type MessageKey } from "./i18n";

type ResidentPage = "home" | "report" | "requests" | "ward";
type Category = "no_water" | "tanker_missed" | "dirty_water" | "leak" | "other";
type QueueState = "queued" | "submitted" | "needs_location" | "invalid";

type ResidentReport = {
  id: string;
  category: Category;
  details: string;
  areaLabel: string;
  createdAt: string;
  latitude?: number;
  longitude?: number;
  state: QueueState;
  complaintId?: string;
  error?: string;
};

const databaseName = "jallekha-resident";
const storeName = "reports";
const copy: Record<Locale, Record<string, string>> = {
  en: {
    online: "Online", offline: "Offline · reports stay on this device", reportTitle: "Tell us about a water issue", reportIntro: "Choose what happened. You can send it when you are back online.", category: "What happened?", chooseCategory: "Choose one", noWater: "No water", tankerMissed: "Tanker did not arrive", dirtyWater: "Water looks or smells dirty", leak: "Leak or broken pipe", other: "Something else", details: "Add a short detail (optional)", detailsHint: "Do not include a phone number or personal details.", area: "Ward or area name (saved on this device only)", areaHint: "For example, your neighbourhood", useLocation: "Add my current location", locationAdded: "Location added", locationDenied: "Location was not shared. You can still save the report.", submit: "Save report", back: "Back to home", requestsTitle: "Your reports", emptyRequests: "No reports saved on this device yet.", queued: "Waiting to sync", submitted: "Sent to JalLekha", needsLocation: "Saved · location check needed", invalid: "Could not send", reportId: "Report number", savedOnDevice: "Saved on this device", deliveryCode: "Delivery code", noDelivery: "No delivery is assigned yet", deliveryUnavailable: "A real delivery code will appear here when the service assigns a visit.", wardCard: "Your area card", areaCardIntro: "Area saved on this device", noArea: "Add an area name when you report an issue to see it here.", wardUnavailable: "Verified ward updates and service times are not connected yet.", noData: "No live ward data", demoNotice: "This app is not connected to a live water service. Reports stay on this device until the intake service is configured.", privacy: "Your saved reports and location remain on this device until sync. Do not use this demo for urgent requests.", sync: "Try sending saved reports", syncing: "Sending…", required: "Choose what happened before saving.", storageError: "This browser could not save the report. Please try another browser.",
  },
  te: {
    online: "ఆన్‌లైన్", offline: "ఆఫ్‌లైన్ · నివేదికలు ఈ పరికరంలోనే ఉంటాయి", reportTitle: "నీటి సమస్యను తెలియజేయండి", reportIntro: "ఏం జరిగిందో ఎంచుకోండి. ఆన్‌లైన్‌లోకి వచ్చినప్పుడు పంపవచ్చు.", category: "ఏం జరిగింది?", chooseCategory: "ఒకటి ఎంచుకోండి", noWater: "నీరు రాలేదు", tankerMissed: "ట్యాంకర్ రాలేదు", dirtyWater: "నీరు మురికిగా ఉంది", leak: "లీక్ లేదా పగిలిన పైపు", other: "ఇంకేదైనా", details: "చిన్న వివరాన్ని జోడించండి (ఐచ్ఛికం)", detailsHint: "ఫోన్ నంబర్ లేదా వ్యక్తిగత వివరాలు ఇవ్వకండి.", area: "వార్డు లేదా ప్రాంతం పేరు (ఈ పరికరంలో మాత్రమే సేవ్ అవుతుంది)", areaHint: "ఉదా: మీ పరిసర ప్రాంతం", useLocation: "నా ప్రస్తుత ప్రాంతాన్ని జోడించండి", locationAdded: "ప్రాంతం జోడించబడింది", locationDenied: "ప్రాంతాన్ని పంచుకోలేదు. అయినా నివేదికను సేవ్ చేయవచ్చు.", submit: "నివేదికను సేవ్ చేయండి", back: "మొదటి పేజీకి వెళ్లండి", requestsTitle: "మీ నివేదికలు", emptyRequests: "ఈ పరికరంలో ఇంకా నివేదికలు లేవు.", queued: "పంపడానికి వేచి ఉంది", submitted: "JalLekhaకు పంపబడింది", needsLocation: "సేవ్ అయింది · ప్రాంతం నిర్ధారించాలి", invalid: "పంపడం సాధ్యం కాలేదు", reportId: "నివేదిక సంఖ్య", savedOnDevice: "ఈ పరికరంలో సేవ్ అయింది", deliveryCode: "డెలివరీ కోడ్", noDelivery: "ఇంకా డెలివరీ కేటాయించలేదు", deliveryUnavailable: "సేవ డెలివరీని కేటాయించిన తర్వాత నిజమైన కోడ్ ఇక్కడ కనిపిస్తుంది.", wardCard: "మీ ప్రాంతం సమాచారం", areaCardIntro: "పరికరంలో సేవ్ చేసిన ప్రాంతం", noArea: "ఇక్కడ చూపించడానికి నివేదికలో ప్రాంతం పేరును జోడించండి.", wardUnavailable: "ధృవీకరించిన వార్డు సమాచారం, సరఫరా సమయాలు ఇంకా అనుసంధానం కాలేదు.", noData: "ప్రత్యక్ష వార్డు సమాచారం లేదు", demoNotice: "ఈ యాప్ ప్రత్యక్ష నీటి సేవకు అనుసంధానం కాలేదు. intake సేవ అమర్చే వరకు నివేదికలు ఈ పరికరంలోనే ఉంటాయి.", privacy: "పంపే వరకు నివేదికలు, ప్రాంత వివరాలు ఈ పరికరంలోనే ఉంటాయి. అత్యవసర అభ్యర్థనలకు ఈ డెమోను వాడకండి.", sync: "సేవ్ చేసిన నివేదికలను పంపండి", syncing: "పంపుతోంది…", required: "సేవ్ చేయడానికి ముందు సమస్యను ఎంచుకోండి.", storageError: "ఈ బ్రౌజర్ నివేదికను సేవ్ చేయలేకపోయింది. మరో బ్రౌజర్‌లో ప్రయత్నించండి.",
  },
  ur: {
    online: "آن لائن", offline: "آف لائن · رپورٹیں اسی آلے پر رہیں گی", reportTitle: "پانی کا مسئلہ بتائیں", reportIntro: "جو ہوا وہ منتخب کریں۔ آن لائن ہونے پر آپ بھیج سکتے ہیں۔", category: "کیا ہوا؟", chooseCategory: "ایک منتخب کریں", noWater: "پانی نہیں آیا", tankerMissed: "ٹینکر نہیں آیا", dirtyWater: "پانی گندا لگتا ہے یا بدبو ہے", leak: "رساؤ یا ٹوٹا ہوا پائپ", other: "کوئی اور مسئلہ", details: "مختصر تفصیل لکھیں (اختیاری)", detailsHint: "فون نمبر یا ذاتی معلومات نہ لکھیں۔", area: "وارڈ یا علاقے کا نام (صرف اسی آلے پر محفوظ ہوگا)", areaHint: "مثلاً آپ کا محلہ", useLocation: "میرا موجودہ مقام شامل کریں", locationAdded: "مقام شامل ہوگیا", locationDenied: "مقام شیئر نہیں کیا گیا۔ آپ پھر بھی رپورٹ محفوظ کرسکتے ہیں۔", submit: "رپورٹ محفوظ کریں", back: "گھر واپس جائیں", requestsTitle: "آپ کی رپورٹیں", emptyRequests: "اس آلے پر ابھی کوئی رپورٹ محفوظ نہیں۔", queued: "بھیجنے کا انتظار", submitted: "JalLekha کو بھیجا گیا", needsLocation: "محفوظ · مقام کی جانچ ضروری ہے", invalid: "بھیجا نہیں جاسکا", reportId: "رپورٹ نمبر", savedOnDevice: "اسی آلے پر محفوظ", deliveryCode: "ترسیل کا کوڈ", noDelivery: "ابھی کوئی ترسیل مقرر نہیں", deliveryUnavailable: "سروس کے دورے مقرر کرنے پر اصل کوڈ یہاں دکھایا جائے گا۔", wardCard: "آپ کے علاقے کی معلومات", areaCardIntro: "آلے پر محفوظ علاقہ", noArea: "یہاں دیکھنے کے لیے رپورٹ میں علاقے کا نام شامل کریں۔", wardUnavailable: "تصدیق شدہ وارڈ کی تازہ معلومات اور وقت ابھی منسلک نہیں ہیں۔", noData: "وارڈ کی تازہ معلومات نہیں", demoNotice: "یہ ایپ پانی کی براہ راست سروس سے منسلک نہیں ہے۔ انٹیک سروس کی ترتیب تک رپورٹیں اسی آلے پر رہیں گی۔", privacy: "بھیجنے تک رپورٹیں اور مقام اسی آلے پر رہتے ہیں۔ فوری مدد کے لیے یہ ڈیمو استعمال نہ کریں۔", sync: "محفوظ رپورٹیں بھیجنے کی کوشش کریں", syncing: "بھیجا جارہا ہے…", required: "محفوظ کرنے سے پہلے مسئلہ منتخب کریں۔", storageError: "یہ براؤزر رپورٹ محفوظ نہیں کرسکا۔ کسی دوسرے براؤزر میں کوشش کریں۔",
  },
  hi: {
    online: "ऑनलाइन", offline: "ऑफ़लाइन · रिपोर्टें इसी डिवाइस पर रहेंगी", reportTitle: "पानी की समस्या बताएं", reportIntro: "क्या हुआ, चुनें। ऑनलाइन होने पर आप इसे भेज सकते हैं।", category: "क्या हुआ?", chooseCategory: "एक चुनें", noWater: "पानी नहीं आया", tankerMissed: "टैंकर नहीं आया", dirtyWater: "पानी गंदा दिखता है या बदबू है", leak: "रिसाव या टूटा पाइप", other: "कुछ और", details: "छोटी जानकारी जोड़ें (ज़रूरी नहीं)", detailsHint: "फोन नंबर या निजी जानकारी न लिखें।", area: "वार्ड या इलाके का नाम (सिर्फ इसी डिवाइस पर सेव होगा)", areaHint: "जैसे आपका मोहल्ला", useLocation: "मेरा मौजूदा स्थान जोड़ें", locationAdded: "स्थान जोड़ दिया गया", locationDenied: "स्थान साझा नहीं हुआ। आप फिर भी रिपोर्ट सेव कर सकते हैं।", submit: "रिपोर्ट सेव करें", back: "घर वापस जाएं", requestsTitle: "आपकी रिपोर्टें", emptyRequests: "इस डिवाइस पर अभी कोई रिपोर्ट सेव नहीं है।", queued: "भेजने का इंतज़ार", submitted: "JalLekha को भेजी गई", needsLocation: "सेव हुई · स्थान की जांच ज़रूरी", invalid: "भेज नहीं सके", reportId: "रिपोर्ट नंबर", savedOnDevice: "इसी डिवाइस पर सेव", deliveryCode: "डिलीवरी कोड", noDelivery: "अभी कोई डिलीवरी तय नहीं", deliveryUnavailable: "सेवा की डिलीवरी तय होने पर असली कोड यहां दिखेगा।", wardCard: "आपके इलाके की जानकारी", areaCardIntro: "डिवाइस पर सेव इलाका", noArea: "यहां देखने के लिए रिपोर्ट में इलाके का नाम जोड़ें।", wardUnavailable: "सत्यापित वार्ड अपडेट और सेवा का समय अभी जुड़ा नहीं है।", noData: "वार्ड की ताज़ा जानकारी नहीं", demoNotice: "यह ऐप पानी की लाइव सेवा से जुड़ा नहीं है। इंटेक सेवा सेट होने तक रिपोर्टें इसी डिवाइस पर रहेंगी।", privacy: "भेजने तक रिपोर्टें और स्थान इसी डिवाइस पर रहते हैं। ज़रूरी सहायता के लिए इस डेमो का उपयोग न करें।", sync: "सेव रिपोर्ट भेजने की कोशिश करें", syncing: "भेज रहे हैं…", required: "सेव करने से पहले समस्या चुनें।", storageError: "यह ब्राउज़र रिपोर्ट सेव नहीं कर पाया। दूसरे ब्राउज़र में कोशिश करें।",
  },
};

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(storeName, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open local report storage"));
  });
}

async function getReports(): Promise<ResidentReport[]> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = db.transaction(storeName, "readonly").objectStore(storeName).getAll();
    request.onsuccess = () => resolve((request.result as ResidentReport[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
    request.onerror = () => reject(request.error ?? new Error("Could not read local reports"));
  });
}

async function saveReport(report: ResidentReport): Promise<void> {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put(report);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not save report"));
  });
}

function createId(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function queueStatus(report: ResidentReport, text: Record<string, string>) {
  if (report.state === "submitted") return text.submitted;
  if (report.state === "needs_location") return text.needsLocation;
  if (report.state === "invalid") return text.invalid;
  return text.queued;
}

export default function ResidentExperience({ page, onNavigate }: { page: ResidentPage; onNavigate: (item: MessageKey) => void }) {
  const { locale, t } = useLocale();
  const words = copy[locale];
  const [reports, setReports] = useState<ResidentReport[]>([]);
  const [category, setCategory] = useState<Category | "">("");
  const [details, setDetails] = useState("");
  const [areaLabel, setAreaLabel] = useState("");
  const [position, setPosition] = useState<{ latitude: number; longitude: number } | null>(null);
  const [message, setMessage] = useState("");
  const [storageReady, setStorageReady] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);

  const refresh = useCallback(async () => {
    try {
      setReports(await getReports());
      setStorageReady(true);
    } catch {
      setMessage(words.storageError);
      setStorageReady(false);
    }
  }, [words.storageError]);

  const syncReports = useCallback(async (items: ResidentReport[]) => {
    const endpoint = (import.meta.env.VITE_INTAKE_URL as string | undefined) || "/intake/batch";
    if (!endpoint || !navigator.onLine || syncing) return;
    const pending = items.filter((report) => report.state === "queued");
    if (!pending.length) return;
    setSyncing(true);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: pending.map((report) => ({
          client_id: report.id,
          channel: "app",
          category: report.category,
          text: report.details,
          language_hint: locale,
          ...(report.latitude !== undefined && report.longitude !== undefined ? { lat: report.latitude, lon: report.longitude } : {}),
        })) }),
      });
      if (!response.ok) throw new Error("Intake service unavailable");
      const payload = await response.json() as { results?: Array<{ client_id?: string; status?: string; complaint_id?: string; complaint_status?: string; error?: string }> };
      for (const result of payload.results ?? []) {
        const current = pending.find((report) => report.id === result.client_id);
        if (!current) continue;
        const state: QueueState = result.status === "invalid" ? "invalid" : result.status === "spam" ? "invalid" : result.complaint_status === "awaiting_location" ? "needs_location" : "submitted";
        await saveReport({ ...current, state, complaintId: result.complaint_id, error: result.error });
      }
      await refresh();
    } catch {
      setMessage(words.queued);
    } finally {
      setSyncing(false);
    }
  }, [locale, refresh, syncing, words.queued]);
  const syncReportsRef = useRef(syncReports);

  useEffect(() => { syncReportsRef.current = syncReports; }, [syncReports]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const updateOnline = () => {
      const isOnline = navigator.onLine;
      setOnline(isOnline);
    };
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

  async function submitReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!category) { setMessage(words.required); return; }
    const report: ResidentReport = {
      id: createId(), category, details: details.trim(), areaLabel: areaLabel.trim(), createdAt: new Date().toISOString(),
      ...(position ?? {}), state: "queued",
    };
    try {
      await saveReport(report);
      const updated = [report, ...reports];
      setReports(updated);
      setStorageReady(true);
      setCategory(""); setDetails(""); setAreaLabel(""); setPosition(null); setMessage(words.queued);
      onNavigate("residentRequests");
      if (online) void syncReports(updated);
    } catch {
      setMessage(words.storageError);
    }
  }

  function addLocation() {
    if (!navigator.geolocation) { setMessage(words.locationDenied); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => { setPosition({ latitude: coords.latitude, longitude: coords.longitude }); setMessage(words.locationAdded); },
      () => setMessage(words.locationDenied),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  }

  const latestArea = reports.find((report) => report.areaLabel)?.areaLabel;
  return (
    <div className="resident-page resident-experience">
      <div className="resident-state-row"><span className={online ? "resident-connectivity online" : "resident-connectivity offline"}><i />{online ? words.online : words.offline}</span><span>{words.savedOnDevice}</span></div>
      {page === "home" && <>
        <section className="resident-hero"><div className="resident-hero-copy"><p className="eyebrow">{t("neighbourhoodHyderabad")}</p><h1>{t("waterSupportTitle")}</h1><p>{t("residentIntro")}</p><button className="button button-dark" onClick={() => onNavigate("residentReport")}>{t("reportWaterIssue")}</button></div><div className="water-art" aria-hidden="true"><span className="sun-orb" /><span className="water-drop">💧</span><span className="art-ripple ripple-one" /><span className="art-ripple ripple-two" /></div></section>
        <div className="resident-notice"><span className="notice-icon">⌖</span><span><strong>{words.wardCard}</strong><small>{latestArea ?? words.noArea}</small></span><button className="text-button" onClick={() => onNavigate("residentUpdates")}>{words.noData}</button></div>
        <div className="section-heading resident-section-heading"><div><h2>{t("whatToDo")}</h2><p className="muted">{t("chooseOption")}</p></div></div>
        <div className="action-grid"><button className="action-card" onClick={() => onNavigate("residentRequests")}><span className="action-icon teal">💧</span><span className="action-copy"><strong>{t("trackRequest")}</strong><small>{t("trackRequestDescription")}</small></span><span aria-hidden="true">→</span></button><button className="action-card" onClick={() => onNavigate("residentReport")}><span className="action-icon coral">!</span><span className="action-copy"><strong>{t("reportWaterIssue")}</strong><small>{t("reportWaterDescription")}</small></span><span aria-hidden="true">→</span></button><button className="action-card" onClick={() => onNavigate("residentUpdates")}><span className="action-icon blue">⌖</span><span className="action-copy"><strong>{t("seeWardUpdates")}</strong><small>{t("wardUpdatesDescription")}</small></span><span aria-hidden="true">→</span></button></div>
      </>}
      {page === "report" && <section className="resident-form-card"><button className="text-button" onClick={() => onNavigate("residentHome")}>← {words.back}</button><h1>{words.reportTitle}</h1><p className="muted">{words.reportIntro}</p><form onSubmit={(event) => void submitReport(event)}>
        <label>{words.category}<select value={category} onChange={(event) => setCategory(event.target.value as Category | "")}><option value="">{words.chooseCategory}</option><option value="no_water">{words.noWater}</option><option value="tanker_missed">{words.tankerMissed}</option><option value="dirty_water">{words.dirtyWater}</option><option value="leak">{words.leak}</option><option value="other">{words.other}</option></select></label>
        <label>{words.details}<textarea maxLength={500} rows={4} value={details} onChange={(event) => setDetails(event.target.value)} placeholder={words.detailsHint} /></label>
        <label>{words.area}<input maxLength={64} value={areaLabel} onChange={(event) => setAreaLabel(event.target.value)} placeholder={words.areaHint} /></label>
        <button className="button button-secondary" type="button" onClick={addLocation}>{position ? words.locationAdded : words.useLocation}</button>
        <p className="resident-privacy-note">{words.privacy}</p>
        {message && <p role="status" className="resident-status-message">{message}</p>}
        <button className="button button-dark" type="submit" disabled={!storageReady}>{words.submit}</button>
      </form></section>}
      {page === "requests" && <section className="resident-list-section"><div className="resident-section-title"><div><p className="eyebrow">{t("residentRequests")}</p><h1>{words.requestsTitle}</h1></div><button className="button button-secondary" onClick={() => void syncReports()} disabled={syncing}>{syncing ? words.syncing : words.sync}</button></div>
        {reports.length === 0 ? <p className="resident-empty-state">{words.emptyRequests}</p> : <div className="resident-request-list">{reports.map((report) => <article className="resident-request-card" key={report.id}><div className="resident-request-card-head"><span className={`resident-request-state ${report.state}`}>{queueStatus(report, words)}</span><time dateTime={report.createdAt}>{new Date(report.createdAt).toLocaleDateString(locale)}</time></div><h2>{words[report.category === "no_water" ? "noWater" : report.category === "tanker_missed" ? "tankerMissed" : report.category === "dirty_water" ? "dirtyWater" : report.category === "leak" ? "leak" : "other"]}</h2>{report.areaLabel && <p>{words.areaCardIntro}: {report.areaLabel}</p>}{report.details && <p>{report.details}</p>}<div className="resident-request-meta">{report.complaintId && <span>{words.reportId}: {report.complaintId}</span>}<span>{words.deliveryCode}: <strong>{words.noDelivery}</strong></span></div><small>{report.state === "needs_location" ? words.needsLocation : report.state === "queued" ? words.savedOnDevice : report.error ?? words.deliveryUnavailable}</small></article>)}</div>}
      </section>}
      {page === "ward" && <section className="resident-ward-card"><p className="eyebrow">{words.wardCard}</p><h1>{latestArea ?? words.areaCardIntro}</h1><span className="resident-data-badge">{words.noData}</span><p>{latestArea ? words.wardUnavailable : words.noArea}</p><div className="resident-ward-placeholder"><span aria-hidden="true">⌖</span><strong>{words.deliveryCode}</strong><small>{words.deliveryUnavailable}</small></div><button className="button button-secondary" onClick={() => onNavigate("residentReport")}>{t("reportWaterIssue")}</button></section>}
      <p className="resident-honesty-note">{words.demoNotice}</p>
    </div>
  );
}
