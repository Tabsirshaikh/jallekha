import { useState, type FormEvent } from "react";
import { useLocale, type Locale } from "./i18n";

type DriverPage = "route" | "proof" | "help";
type Outcome = "confirmed" | "disputed" | "unconfirmed" | "failed";
type ResidentFeedback = "confirm" | "dispute";

const DEMO_OTP = "123456";

const stops = [
  { id: "DEMO-STOP-01", name: "Sample stop 01" },
  { id: "DEMO-STOP-02", name: "Sample stop 02" },
  { id: "DEMO-STOP-03", name: "Sample stop 03" },
];

const copy: Record<Locale, Record<string, string>> = {
  en: {
    demo: "SYNTHETIC · sample route", routeTitle: "Today’s route", routeIntro: "Example stops only. This route is not assigned to a driver.", stops: "Stops", firstStop: "First stop", routeStatus: "Route status", notAssigned: "Sample route", waiting: "Preview only", markArrived: "Record arrival in preview", arrivalSaved: "Arrival marked in this preview only", arrivalWarning: "A server must check GPS location before arrival is confirmed.", deliveryProof: "Delivery proof", enterOtp: "Enter the code from the registered representative", otpLabel: "6-digit delivery code", demoOtp: "Demo code: 123456", residentFeedback: "Simulated resident feedback", residentsConfirm: "Residents mostly confirm", residentsDispute: "Residents mostly dispute", checkCode: "Run delivery preview", otpLocalOnly: "Demo only: the code and resident feedback were evaluated with local sample logic; nothing was sent or saved.", previewResult: "Simulated outcome", outcomesTitle: "Possible delivery outcomes", confirmed: "Confirmed", disputed: "Disputed", unconfirmed: "Unconfirmed", failed: "Failed", confirmedRule: "OTP verified · residents mostly confirm", disputedRule: "OTP verified · residents mostly disagree", unconfirmedRule: "OTP not verified · residents mostly confirm", failedRule: "OTP not verified · residents mostly disagree", silence: "No replies are not counted as “no”. Without a majority, the outcome waits for the reply window and then uses the OTP result.", demoWarning: "Preview only · No route, arrival, OTP or delivery outcome is connected to a live service.", chooseStop: "Select a sample stop to preview the delivery steps.", helpTitle: "Driver help", helpText: "Use only a route assigned by your dispatcher. If your position cannot be checked or the resident cannot provide the code, contact your dispatcher. This preview cannot verify deliveries.", backRoute: "Back to route", route: "Route", openProof: "Open delivery steps", noCodeTitle: "Demo code is not a real delivery code",
  },
  te: {
    demo: "కల్పిత డేటా · నమూనా మార్గం", routeTitle: "ఈరోజు మార్గం", routeIntro: "ఇవి నమూనా నిలుపులు మాత్రమే. ఈ మార్గం డ్రైవర్‌కు కేటాయించలేదు.", stops: "నిలుపులు", firstStop: "మొదటి నిలుపు", routeStatus: "మార్గం స్థితి", notAssigned: "నమూనా మార్గం", waiting: "పరిదృశ్యం మాత్రమే", markArrived: "పరిదృశ్యంలో చేరినట్లు నమోదు చేయండి", arrivalSaved: "ఈ పరిదృశ్యంలో మాత్రమే చేరినట్లు గుర్తించబడింది", arrivalWarning: "చేరినట్లు నిర్ధారించడానికి సర్వర్ GPS ప్రాంతాన్ని తనిఖీ చేయాలి.", deliveryProof: "డెలివరీ నిర్ధారణ", enterOtp: "నమోదైన ప్రతినిధి ఇచ్చిన కోడ్‌ను నమోదు చేయండి", otpLabel: "6 అంకెల డెలివరీ కోడ్", demoOtp: "నమూనా కోడ్: 123456", residentFeedback: "నమూనా నివాసి అభిప్రాయం", residentsConfirm: "నివాసితులు ఎక్కువగా నిర్ధారించారు", residentsDispute: "నివాసితులు ఎక్కువగా అంగీకరించలేదు", checkCode: "డెలివరీ పరిదృశ్యాన్ని చూపండి", otpLocalOnly: "నమూనా మాత్రమే: కోడ్ మరియు నివాసి అభిప్రాయం స్థానిక నమూనా నియమాలతో పరిశీలించబడ్డాయి; ఏదీ పంపలేదు లేదా సేవ్ చేయలేదు.", previewResult: "నమూనా ఫలితం", outcomesTitle: "డెలివరీకి వచ్చే ఫలితాలు", confirmed: "నిర్ధారించబడింది", disputed: "వివాదం ఉంది", unconfirmed: "నిర్ధారణ లేదు", failed: "విఫలమైంది", confirmedRule: "OTP నిర్ధారించబడింది · ఎక్కువ మంది నివాసితులు అవును అన్నారు", disputedRule: "OTP నిర్ధారించబడింది · ఎక్కువ మంది నివాసితులు అంగీకరించలేదు", unconfirmedRule: "OTP నిర్ధారించలేదు · ఎక్కువ మంది నివాసితులు అవును అన్నారు", failedRule: "OTP నిర్ధారించలేదు · ఎక్కువ మంది నివాసితులు అంగీకరించలేదు", silence: "సమాధానం ఇవ్వకపోవడాన్ని ‘కాదు’గా లెక్కించరు. ఎక్కువ సమాధానాలు ఒకేలా లేకపోతే, సమాధాన సమయం వరకు వేచి ఉండి OTP ఫలితాన్ని ఉపయోగిస్తారు.", demoWarning: "పరిదృశ్యం మాత్రమే · మార్గం, చేరిక, OTP లేదా డెలివరీ ఫలితం ప్రత్యక్ష సేవకు అనుసంధానం కాలేదు.", chooseStop: "డెలివరీ దశలను చూడడానికి నమూనా నిలుపును ఎంచుకోండి.", helpTitle: "డ్రైవర్ సహాయం", helpText: "డిస్పాచర్ కేటాయించిన మార్గాన్నే ఉపయోగించండి. మీ స్థానాన్ని తనిఖీ చేయలేకపోతే లేదా నివాసి కోడ్ ఇవ్వలేకపోతే డిస్పాచర్‌ను సంప్రదించండి. ఈ పరిదృశ్యం డెలివరీలను నిర్ధారించదు.", backRoute: "మార్గానికి వెనక్కి", route: "మార్గం", openProof: "డెలివరీ దశలు తెరవండి", noCodeTitle: "ఇది నిజమైన డెలివరీ కోడ్ కాదు",
  },
  ur: {
    demo: "مصنوعی · نمونہ راستہ", routeTitle: "آج کا راستہ", routeIntro: "یہ صرف نمونہ مقامات ہیں۔ یہ راستہ کسی ڈرائیور کو نہیں دیا گیا۔", stops: "مقامات", firstStop: "پہلا مقام", routeStatus: "راستے کی حالت", notAssigned: "نمونہ راستہ", waiting: "صرف پیش منظر", markArrived: "پیش منظر میں آمد درج کریں", arrivalSaved: "آمد صرف اسی پیش منظر میں درج ہوئی", arrivalWarning: "آمد کی تصدیق سے پہلے سرور کو GPS مقام چیک کرنا ہوگا۔", deliveryProof: "ترسیل کی تصدیق", enterOtp: "رجسٹرڈ نمائندے سے ملا کوڈ درج کریں", otpLabel: "6 ہندسوں کا ترسیلی کوڈ", demoOtp: "نمونہ کوڈ: 123456", residentFeedback: "نمونہ رہائشی رائے", residentsConfirm: "زیادہ تر رہائشی تصدیق کرتے ہیں", residentsDispute: "زیادہ تر رہائشی اختلاف کرتے ہیں", checkCode: "ترسیل کا پیش منظر چلائیں", otpLocalOnly: "صرف نمونہ: کوڈ اور رہائشی رائے مقامی نمونہ قواعد سے دیکھی گئی؛ کچھ بھیجا یا محفوظ نہیں کیا گیا۔", previewResult: "نمونہ نتیجہ", outcomesTitle: "ترسیل کے ممکنہ نتائج", confirmed: "تصدیق شدہ", disputed: "اختلاف", unconfirmed: "غیر مصدقہ", failed: "ناکام", confirmedRule: "OTP تصدیق شدہ · زیادہ تر رہائشیوں نے ہاں کہا", disputedRule: "OTP تصدیق شدہ · زیادہ تر رہائشی متفق نہیں", unconfirmedRule: "OTP کی تصدیق نہیں · زیادہ تر رہائشیوں نے ہاں کہا", failedRule: "OTP کی تصدیق نہیں · زیادہ تر رہائشی متفق نہیں", silence: "جواب نہ دینا ‘نہیں’ شمار نہیں ہوتا۔ واضح اکثریت نہ ہو تو جواب کی مدت ختم ہونے تک انتظار کیا جاتا ہے، پھر OTP کا نتیجہ لیا جاتا ہے۔", demoWarning: "صرف پیش منظر · راستہ، آمد، OTP یا ترسیل کا نتیجہ کسی براہ راست سروس سے منسلک نہیں۔", chooseStop: "ترسیل کے مراحل دیکھنے کے لیے نمونہ مقام منتخب کریں۔", helpTitle: "ڈرائیور کی مدد", helpText: "صرف ڈسپیچر کا دیا ہوا راستہ استعمال کریں۔ اگر آپ کا مقام چیک نہ ہوسکے یا رہائشی کوڈ نہ دے سکے تو ڈسپیچر سے رابطہ کریں۔ یہ پیش منظر ترسیل کی تصدیق نہیں کرسکتا۔", backRoute: "واپس راستے پر", route: "راستہ", openProof: "ترسیل کے مراحل کھولیں", noCodeTitle: "یہ حقیقی ترسیلی کوڈ نہیں ہے",
  },
  hi: {
    demo: "सिंथेटिक · नमूना मार्ग", routeTitle: "आज का मार्ग", routeIntro: "ये सिर्फ नमूना पड़ाव हैं। यह मार्ग किसी ड्राइवर को नहीं दिया गया है।", stops: "पड़ाव", firstStop: "पहला पड़ाव", routeStatus: "मार्ग की स्थिति", notAssigned: "नमूना मार्ग", waiting: "सिर्फ पूर्वावलोकन", markArrived: "पूर्वावलोकन में पहुंच दर्ज करें", arrivalSaved: "पहुंच सिर्फ इसी पूर्वावलोकन में दर्ज हुई", arrivalWarning: "पहुंच की पुष्टि से पहले सर्वर को GPS स्थान जांचना होगा।", deliveryProof: "डिलीवरी की पुष्टि", enterOtp: "पंजीकृत प्रतिनिधि से मिला कोड डालें", otpLabel: "6 अंकों का डिलीवरी कोड", demoOtp: "नमूना कोड: 123456", residentFeedback: "नमूना निवासी प्रतिक्रिया", residentsConfirm: "अधिकतर निवासी पुष्टि करते हैं", residentsDispute: "अधिकतर निवासी असहमत हैं", checkCode: "डिलीवरी पूर्वावलोकन चलाएं", otpLocalOnly: "सिर्फ नमूना: कोड और निवासी प्रतिक्रिया स्थानीय नमूना नियमों से जांची गई; कुछ भेजा या सेव नहीं हुआ।", previewResult: "नमूना नतीजा", outcomesTitle: "डिलीवरी के संभावित नतीजे", confirmed: "पुष्टि हुई", disputed: "विवादित", unconfirmed: "पुष्टि नहीं हुई", failed: "विफल", confirmedRule: "OTP सही · अधिकतर निवासियों ने हां कहा", disputedRule: "OTP सही · अधिकतर निवासी सहमत नहीं", unconfirmedRule: "OTP की पुष्टि नहीं · अधिकतर निवासियों ने हां कहा", failedRule: "OTP की पुष्टि नहीं · अधिकतर निवासी सहमत नहीं", silence: "जवाब न देना ‘नहीं’ नहीं माना जाता। बहुमत न हो तो जवाब की अवधि तक इंतज़ार करके OTP का नतीजा लिया जाता है।", demoWarning: "सिर्फ पूर्वावलोकन · मार्ग, पहुंच, OTP या डिलीवरी का नतीजा लाइव सेवा से जुड़ा नहीं है।", chooseStop: "डिलीवरी के चरण देखने के लिए नमूना पड़ाव चुनें।", helpTitle: "ड्राइवर सहायता", helpText: "सिर्फ डिस्पैचर का दिया मार्ग इस्तेमाल करें। स्थान की जांच न हो सके या निवासी कोड न दे सके, तो डिस्पैचर से संपर्क करें। यह पूर्वावलोकन डिलीवरी की पुष्टि नहीं कर सकता।", backRoute: "मार्ग पर वापस जाएं", route: "मार्ग", openProof: "डिलीवरी के चरण खोलें", noCodeTitle: "यह असली डिलीवरी कोड नहीं है",
  },
};

export default function DriverExperience({ page, onNavigate }: { page: DriverPage; onNavigate: (item: "driverRoute" | "driverProof" | "help") => void }) {
  const { locale, t } = useLocale();
  const words = copy[locale];
  const [selectedStop, setSelectedStop] = useState<string | null>(null);
  const [arrivalRecorded, setArrivalRecorded] = useState(false);
  const [otp, setOtp] = useState("");
  const [residentFeedback, setResidentFeedback] = useState<ResidentFeedback>("confirm");
  const [previewOutcome, setPreviewOutcome] = useState<Outcome | null>(null);
  const [feedback, setFeedback] = useState("");

  function submitCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const otpVerified = otp === DEMO_OTP;
    setPreviewOutcome(otpVerified
      ? residentFeedback === "confirm" ? "confirmed" : "disputed"
      : residentFeedback === "confirm" ? "unconfirmed" : "failed");
    setOtp("");
    setFeedback(words.otpLocalOnly);
  }

  const outcomes: { id: Outcome; color: string; rule: string }[] = [
    { id: "confirmed", color: "confirmed", rule: words.confirmedRule },
    { id: "disputed", color: "disputed", rule: words.disputedRule },
    { id: "unconfirmed", color: "unconfirmed", rule: words.unconfirmedRule },
    { id: "failed", color: "failed", rule: words.failedRule },
  ];

  return (
    <div className="driver-page driver-experience">
      <div className="driver-heading"><div><p className="eyebrow">{t("driverWorkspace")}</p><h1>{page === "help" ? words.helpTitle : page === "proof" ? words.deliveryProof : words.routeTitle}</h1><p className="muted">{page === "help" ? words.helpText : words.routeIntro}</p></div><span className="driver-demo-badge">{words.demo}</span></div>
      {page === "route" && <>
        <section className="driver-route-card"><div className="route-card-top"><div><span className="route-label">{words.routeTitle}</span><h2>{words.notAssigned}</h2></div><span className="route-icon" aria-hidden="true">↗</span></div><p>{words.routeIntro}</p><div className="route-summary"><div><small>{words.stops}</small><strong>{stops.length}</strong></div><div><small>{words.firstStop}</small><strong>01</strong></div><div><small>{words.routeStatus}</small><strong>{words.waiting}</strong></div></div></section>
        <div className="driver-section-title"><h2>{t("atEachStop")}</h2><p className="muted">{t("stopIntro")}</p></div>
        <div className="driver-stop-list">{stops.map((stop, index) => <article className="driver-stop-card" key={stop.id}><span className="driver-stop-number">{String(index + 1).padStart(2, "0")}</span><div className="driver-stop-info"><strong>{stop.name}</strong><small>{stop.id} · {words.demo}</small></div><button className="button button-secondary" onClick={() => { setSelectedStop(stop.id); setArrivalRecorded(true); setFeedback(words.arrivalWarning); }}>{words.markArrived}</button></article>)}</div>
        {selectedStop && <div className="driver-arrival-state" role="status"><strong>{words.arrivalSaved}</strong><span>{selectedStop}</span><p>{words.arrivalWarning}</p><button className="button button-dark" onClick={() => onNavigate("driverProof")}>{words.openProof}</button></div>}
      </>}
      {page === "proof" && <>
        <button className="text-button" onClick={() => onNavigate("driverRoute")}>← {words.backRoute}</button>
        {!selectedStop ? <p className="driver-arrival-state">{words.chooseStop}</p> : <section className="driver-proof-panel"><span className="route-label">{selectedStop}</span><h2>{words.enterOtp}</h2><div className="driver-arrival-state compact"><strong>{arrivalRecorded ? words.arrivalSaved : words.arrivalWarning}</strong><p>{words.arrivalWarning}</p></div><form onSubmit={submitCode}><label htmlFor="driver-otp">{words.otpLabel}</label><input id="driver-otp" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))} required /><p className="driver-demo-code">{words.demoOtp}</p><fieldset className="driver-feedback-options"><legend>{words.residentFeedback}</legend><label><input type="radio" name="resident-feedback" checked={residentFeedback === "confirm"} onChange={() => setResidentFeedback("confirm")} /> {words.residentsConfirm}</label><label><input type="radio" name="resident-feedback" checked={residentFeedback === "dispute"} onChange={() => setResidentFeedback("dispute")} /> {words.residentsDispute}</label></fieldset><button className="button button-dark" type="submit" disabled={otp.length !== 6}>{words.checkCode}</button></form>{feedback && <p role="status" className="driver-feedback">{feedback}</p>}{previewOutcome && <div className={`driver-preview-outcome ${previewOutcome}`} role="status"><small>{words.previewResult}</small><strong>{words[previewOutcome]}</strong><span>{outcomes.find((outcome) => outcome.id === previewOutcome)?.rule}</span></div>}<h2>{words.outcomesTitle}</h2><div className="driver-outcome-list">{outcomes.map((outcome) => <article className={`driver-outcome ${outcome.color}`} key={outcome.id}><strong>{words[outcome.id]}</strong><span>{outcome.rule}</span></article>)}</div><p className="driver-silence-note">{words.silence}</p><p className="prototype-note">{words.noCodeTitle}</p></section>}
      </>}
      {page === "help" && <section className="driver-help-panel"><h2>{words.helpTitle}</h2><p>{words.helpText}</p><button className="button button-secondary" onClick={() => onNavigate("driverRoute")}>{words.route}</button></section>}
      <p className="driver-honesty-note">{words.demoWarning}</p>
    </div>
  );
}
