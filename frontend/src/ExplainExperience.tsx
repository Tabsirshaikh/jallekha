import { useEffect, useState, type FormEvent } from "react";
import { useLocale, type Locale } from "./i18n";
import "./ExplainExperience.css";

type ReasonCode = "ranking_wrong" | "need_data_wrong" | "service_class_wrong" | "delivery_not_received" | "other";
type OutcomeCode = "ranking_stands" | "ranking_changed" | "data_corrected" | "referred";
type Contest = { id: string; reason: ReasonCode; text: string; outcome?: OutcomeCode; reply?: string };

const copy = {
  en: { title:"Why this booking is in the queue", intro:"Read the factors behind a sample queue position and raise a contest for officer review.", demo:"SYNTHETIC PREVIEW · T7 routes not available", caveat:"Example values only. This screen does not call T7 or write to the ledger; contests and replies stay in this browser preview.", booking:"Sample booking", ward:"Sample Ward 12", status:"Waiting", place:"Queue place", capacity:"Today's capacity", tier:"Priority tier", arrived:"Arrival time", group:"Fairness group", entitlement:"Group entitlement", quantum:"Round-robin quantum", deficit:"Carried-over deficit", reason:"Queue reason", why:"Why this place?", explanation:"The booking is after today's capacity. Its position reflects its priority tier, arrival order, group entitlement and round-robin balance.", counterfactual:"Example counterfactual", counterfactualText:"An earlier arrival could move this booking up in the sample replay. The exact smallest change must come from the T7 service.", notInput:"Water debt is not an input to today's queue order.", contestTitle:"Contest this explanation", reasonCode:"Reason", detail:"What should the officer check?", detailHint:"Do not include names or phone numbers.", file:"File sample contest", contests:"Contest preview", filed:"Filed locally", pending:"Waiting for officer reply", replyTitle:"Officer reply", outcome:"Outcome", replyReason:"Reason for this decision", replyHint:"A reason is required for every reply.", submitReply:"Save sample reply", replied:"Reply saved in this preview", noContests:"No sample contests filed yet.", close:"Close", reasonLabels:{ranking_wrong:"Queue ranking seems wrong",need_data_wrong:"Need data may be wrong",service_class_wrong:"Service class may be wrong",delivery_not_received:"Delivery was not received",other:"Other reason"}, outcomeLabels:{ranking_stands:"Ranking stands",ranking_changed:"Ranking changed",data_corrected:"Data corrected",referred:"Referred for review"}, storedNote:"Demo only: no backend or ledger was updated." },
  te: { title:"ఈ బుకింగ్ క్రమంలో ఎందుకు ఉంది?", intro:"ఉదాహరణ క్రమానికి కారణాలు చూడండి; అధికారి పరిశీలనకు అభ్యంతరం పంపండి.", demo:"కల్పిత నమూనా · T7 మార్గాలు అందుబాటులో లేవు", caveat:"ఇవి ఉదాహరణ విలువలు. ఈ పేజీ T7 సేవను పిలవదు లేదా లెడ్జర్‌లో నమోదు చేయదు; అభ్యంతరాలు ఈ బ్రౌజర్ నమూనాలోనే ఉంటాయి.", booking:"నమూనా బుకింగ్", ward:"నమూనా వార్డు 12", status:"వేచి ఉంది", place:"క్యూలో స్థానం", capacity:"ఈ రోజు సామర్థ్యం", tier:"ప్రాధాన్యత స్థాయి", arrived:"వచ్చిన సమయం", group:"న్యాయ సమూహం", entitlement:"సమూహ కేటాయింపు", quantum:"రౌండ్-రాబిన్ పరిమాణం", deficit:"మిగిలిన లోటు", reason:"క్రమ కారణం", why:"ఈ స్థానం ఎందుకు?", explanation:"ఈ రోజు సామర్థ్యానికి మించి బుకింగ్ ఉంది. దాని స్థానం ప్రాధాన్యత, వచ్చిన క్రమం, సమూహ కేటాయింపు, రౌండ్-రాబిన్ సమతుల్యతపై ఆధారపడుతుంది.", counterfactual:"ఉదాహరణ ప్రత్యామ్నాయం", counterfactualText:"ఉదాహరణ పునఃప్లేలో ముందుగా రావడం వల్ల స్థానం మెరుగవవచ్చు. ఖచ్చితమైన కనిష్ఠ మార్పు T7 సేవ నుంచే రావాలి.", notInput:"ఈ రోజు క్రమంలో నీటి బాకీ ఒక ఇన్‌పుట్ కాదు.", contestTitle:"ఈ వివరణపై అభ్యంతరం", reasonCode:"కారణం", detail:"అధికారి ఏమి పరిశీలించాలి?", detailHint:"పేరు లేదా ఫోన్ నంబరు రాయకండి.", file:"ఉదాహరణ అభ్యంతరం పంపండి", contests:"అభ్యంతర నమూనా", filed:"ఇక్కడే నమోదు అయింది", pending:"అధికారి సమాధానం కోసం వేచి ఉంది", replyTitle:"అధికారి సమాధానం", outcome:"ఫలితం", replyReason:"నిర్ణయానికి కారణం", replyHint:"ప్రతి సమాధానానికి కారణం అవసరం.", submitReply:"ఉదాహరణ సమాధానాన్ని సేవ్ చేయండి", replied:"ఈ నమూనాలో సమాధానం సేవ్ అయింది", noContests:"ఇంకా నమూనా అభ్యంతరాలు లేవు.", close:"మూసివేయండి", reasonLabels:{ranking_wrong:"క్యూ క్రమం తప్పుగా ఉంది",need_data_wrong:"అవసర సమాచారం తప్పుగా ఉండవచ్చు",service_class_wrong:"సేవా తరగతి తప్పుగా ఉండవచ్చు",delivery_not_received:"నీరు అందలేదు",other:"ఇతర కారణం"}, outcomeLabels:{ranking_stands:"క్రమం అలాగే ఉంటుంది",ranking_changed:"క్రమం మార్చబడింది",data_corrected:"సమాచారం సరిచేశారు",referred:"పరిశీలనకు పంపారు"}, storedNote:"డెమో మాత్రమే: బ్యాకెండ్ లేదా లెడ్జర్ మారలేదు." },
  ur: { title:"یہ بکنگ قطار میں کیوں ہے؟", intro:"نمونے کی قطار کے عوامل دیکھیں اور افسر کے جائزے کے لیے اعتراض درج کریں۔", demo:"مصنوعی پیش منظر · T7 راستے دستیاب نہیں", caveat:"یہ صرف مثالیں ہیں۔ یہ صفحہ T7 کو کال یا لیجر میں اندراج نہیں کرتا؛ اعتراض اور جواب اسی براؤزر میں رہتے ہیں۔", booking:"نمونہ بکنگ", ward:"نمونہ وارڈ 12", status:"انتظار میں", place:"قطار میں جگہ", capacity:"آج کی گنجائش", tier:"ترجیحی درجہ", arrived:"آمد کا وقت", group:"انصاف کا گروپ", entitlement:"گروپ کا حصہ", quantum:"راؤنڈ رابن مقدار", deficit:"پچھلا بقایا", reason:"قطار کی وجہ", why:"یہ جگہ کیوں؟", explanation:"یہ بکنگ آج کی گنجائش سے آگے ہے۔ اس کی جگہ ترجیح، آمد کی ترتیب، گروپ کے حصے اور راؤنڈ رابن توازن پر منحصر ہے۔", counterfactual:"مثالی متبادل", counterfactualText:"مثالی دوبارہ حساب میں پہلے آنے سے جگہ بہتر ہوسکتی ہے۔ درست کم سے کم تبدیلی T7 سروس سے آنی چاہیے۔", notInput:"آج کی قطار میں پانی کا بقایا شامل نہیں۔", contestTitle:"اس وضاحت پر اعتراض", reasonCode:"وجہ", detail:"افسر کو کیا دیکھنا چاہیے؟", detailHint:"نام یا فون نمبر شامل نہ کریں۔", file:"نمونہ اعتراض درج کریں", contests:"اعتراض کا پیش منظر", filed:"یہیں درج ہوا", pending:"افسر کے جواب کا انتظار", replyTitle:"افسر کا جواب", outcome:"نتیجہ", replyReason:"فیصلے کی وجہ", replyHint:"ہر جواب کے ساتھ وجہ ضروری ہے۔", submitReply:"نمونہ جواب محفوظ کریں", replied:"اس پیش منظر میں جواب محفوظ ہوا", noContests:"ابھی کوئی نمونہ اعتراض نہیں۔", close:"بند کریں", reasonLabels:{ranking_wrong:"قطار کی ترتیب غلط لگتی ہے",need_data_wrong:"ضرورت کا ڈیٹا غلط ہوسکتا ہے",service_class_wrong:"سروس کی قسم غلط ہوسکتی ہے",delivery_not_received:"پانی نہیں پہنچا",other:"دوسری وجہ"}, outcomeLabels:{ranking_stands:"ترتیب برقرار",ranking_changed:"ترتیب تبدیل",data_corrected:"ڈیٹا درست کیا",referred:"جائزے کے لیے بھیجا"}, storedNote:"صرف ڈیمو: بیک اینڈ یا لیجر تبدیل نہیں ہوا۔" },
  hi: { title:"यह बुकिंग कतार में क्यों है?", intro:"नमूना कतार के कारण देखें और अधिकारी की समीक्षा के लिए आपत्ति दर्ज करें।", demo:"सिंथेटिक पूर्वावलोकन · T7 मार्ग उपलब्ध नहीं", caveat:"ये केवल उदाहरण हैं। यह पेज T7 को कॉल या लेजर में लिखता नहीं है; आपत्तियाँ और जवाब इसी ब्राउज़र में रहते हैं।", booking:"नमूना बुकिंग", ward:"नमूना वार्ड 12", status:"प्रतीक्षा में", place:"कतार में स्थान", capacity:"आज की क्षमता", tier:"प्राथमिकता स्तर", arrived:"आने का समय", group:"न्याय समूह", entitlement:"समूह का हिस्सा", quantum:"राउंड-रॉबिन मात्रा", deficit:"पिछला घाटा", reason:"कतार का कारण", why:"यह स्थान क्यों?", explanation:"यह बुकिंग आज की क्षमता से आगे है। इसका स्थान प्राथमिकता, आने का क्रम, समूह के हिस्से और राउंड-रॉबिन संतुलन पर निर्भर है।", counterfactual:"उदाहरण विकल्प", counterfactualText:"नमूना दोबारा चलाने में पहले आने से स्थान बेहतर हो सकता है। सही न्यूनतम बदलाव T7 सेवा से आना चाहिए।", notInput:"आज की कतार में पानी का बकाया शामिल नहीं है।", contestTitle:"इस स्पष्टीकरण पर आपत्ति", reasonCode:"कारण", detail:"अधिकारी को क्या जाँचना चाहिए?", detailHint:"नाम या फोन नंबर न लिखें।", file:"नमूना आपत्ति दर्ज करें", contests:"आपत्ति पूर्वावलोकन", filed:"यहीं दर्ज हुई", pending:"अधिकारी के जवाब का इंतज़ार", replyTitle:"अधिकारी का जवाब", outcome:"नतीजा", replyReason:"इस निर्णय का कारण", replyHint:"हर जवाब के लिए कारण ज़रूरी है।", submitReply:"नमूना जवाब सेव करें", replied:"इस पूर्वावलोकन में जवाब सेव हुआ", noContests:"अभी कोई नमूना आपत्ति दर्ज नहीं।", close:"बंद करें", reasonLabels:{ranking_wrong:"कतार क्रम गलत लगता है",need_data_wrong:"ज़रूरत का डेटा गलत हो सकता है",service_class_wrong:"सेवा वर्ग गलत हो सकता है",delivery_not_received:"पानी नहीं पहुँचा",other:"दूसरा कारण"}, outcomeLabels:{ranking_stands:"क्रम बरकरार",ranking_changed:"क्रम बदला",data_corrected:"डेटा सुधारा",referred:"समीक्षा के लिए भेजा"}, storedNote:"केवल डेमो: बैकएंड या लेजर नहीं बदला।" },
} satisfies Record<Locale, Record<string, unknown>>;

const reasons: ReasonCode[] = ["ranking_wrong", "need_data_wrong", "service_class_wrong", "delivery_not_received", "other"];
const outcomes: OutcomeCode[] = ["ranking_stands", "ranking_changed", "data_corrected", "referred"];
export default function ExplainExperience() {
  const { locale } = useLocale();
  const w = copy[locale];
  const [contests, setContests] = useState<Contest[]>(() => {
    try { return JSON.parse(localStorage.getItem("jallekha-u8-contests") ?? "null") ?? []; }
    catch { return []; }
  });
  const [reason, setReason] = useState<ReasonCode>("need_data_wrong");
  const [text, setText] = useState("");
  const [outcome, setOutcome] = useState<OutcomeCode>("referred");
  const [reply, setReply] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    try { localStorage.setItem("jallekha-u8-contests", JSON.stringify(contests)); }
    catch { /* Local persistence is optional for this preview. */ }
  }, [contests]);

  function fileContest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim()) return;
    setContests((current) => [{ id:`DEMO-C-${Date.now()}`, reason, text:text.trim() }, ...current]);
    setText("");
    setMessage(w.filed);
  }

  function replyToContest(event: FormEvent<HTMLFormElement>, id: string) {
    event.preventDefault();
    if (!reply.trim()) return;
    setContests((current) => current.map((contest) => contest.id === id ? { ...contest, outcome, reply:reply.trim() } : contest));
    setReply("");
    setMessage(w.replied);
  }

  return <div className="explain-page">
    <header className="explain-heading"><div><p className="eyebrow">F16 · T7</p><h1>{w.title}</h1><p className="muted">{w.intro}</p></div><span className="forecast-demo-badge">{w.demo}</span></header>
    <div className="explain-notice"><strong>{w.caveat}</strong><span>SYNTHETIC · {w.ward} · DEMO-BK-105</span></div>
    <section className="explain-panel"><div className="explain-panel-heading"><div><p className="eyebrow">{w.booking}</p><h2>DEMO-BK-105 · {w.ward}</h2></div><span className="explain-state">{w.status}</span></div>
      <div className="explain-facts"><div><span>{w.place}</span><strong>#5</strong></div><div><span>{w.capacity}</span><strong>3</strong></div><div><span>{w.tier}</span><strong>2</strong></div><div><span>{w.arrived}</span><strong>10:20</strong></div><div><span>{w.group}</span><strong>DEMO-G12</strong></div><div><span>{w.entitlement}</span><strong>2.0</strong></div><div><span>{w.quantum}</span><strong>1.0</strong></div><div><span>{w.deficit}</span><strong>0.0</strong></div></div>
      <div className="explain-detail"><h3>{w.why}</h3><p>{w.explanation}</p><small>{w.reason}: DRR · all values SYNTHETIC</small></div>
      <div className="explain-counterfactual"><span className="source-tag simulation">SIMULATION</span><div><h3>{w.counterfactual}</h3><p>{w.counterfactualText}</p><small>{w.notInput}</small></div></div>
    </section>
    <div className="explain-contest-grid">
      <section className="explain-panel"><p className="eyebrow">{w.contestTitle}</p><form className="explain-form" onSubmit={fileContest}>
        <label>{w.reasonCode}<select value={reason} onChange={(event)=>setReason(event.target.value as ReasonCode)}>{reasons.map((item)=><option key={item} value={item}>{w.reasonLabels[item]}</option>)}</select></label>
        <label>{w.detail}<textarea value={text} onChange={(event)=>setText(event.target.value)} maxLength={500} rows={3} placeholder={w.detailHint} /></label>
        <button className="button button-dark" type="submit" disabled={!text.trim()}>{w.file}</button>
      </form></section>
      <section className="explain-panel"><div className="explain-panel-heading"><div><p className="eyebrow">{w.contests}</p><h2>{contests.length}</h2></div></div>
        {contests.length===0?<p className="muted">{w.noContests}</p>:<div className="explain-contest-list">{contests.map((contest)=><article className="explain-contest" key={contest.id}><div><strong>{contest.id}</strong><span className="explain-state">{contest.outcome?w.replied:w.pending}</span></div><p>{w.reasonLabels[contest.reason]}</p><p>{contest.text}</p>{contest.reply?<div className="explain-reply"><strong>{w.outcomeLabels[contest.outcome!]}</strong><p>{contest.reply}</p></div>:<form className="explain-form" onSubmit={(event)=>replyToContest(event,contest.id)}><h3>{w.replyTitle}</h3><label>{w.outcome}<select value={outcome} onChange={(event)=>setOutcome(event.target.value as OutcomeCode)}>{outcomes.map((item)=><option key={item} value={item}>{w.outcomeLabels[item]}</option>)}</select></label><label>{w.replyReason}<textarea value={reply} onChange={(event)=>setReply(event.target.value)} maxLength={500} rows={2} placeholder={w.replyHint}/></label><button className="button button-secondary" type="submit" disabled={!reply.trim()}>{w.submitReply}</button></form>}</article>)}</div>}
      </section>
    </div>
    {message && <p className="explain-status" role="status">{message} · {w.storedNote}</p>}
    <p className="explain-footer">{w.storedNote}</p>
  </div>;
}
