import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { ApiError, apiFetch } from "./api";
import { useAuth } from "./auth";
import DataSourceChip from "./DataSource";
import {
  driverMode, fallbackForError, newDeliveryId, outcomeKey,
  type DeliveryView, type DriverFallback, type LocationCheck, type Outcome, type OutcomeStatus, type Paged, type StopView, type VerifyResponse, type VerifyResult,
} from "./driverAdapter";
import { useLocale, type Locale } from "./i18n";
import { useApi } from "./useApi";

type DriverPage = "route" | "proof" | "help";
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

// Strings for the live mode (signed-in driver, T10 delivery-proof API). te / ur / hi are drafts for review.
const liveEn = {
  liveIntro: "Registered stops from the JalLekha server. Open a stop to record delivery proof.", driverLabel: "Driver", deliveriesRecorded: "Deliveries recorded", awaitingOutcome: "Waiting for outcome", stopCounts: "{reps} representatives · {residents} residents", syntheticStop: "Synthetic test stop", yourDeliveries: "Your deliveries", noDeliveries: "No deliveries recorded yet.", deliveriesUnavailable: "Your deliveries could not be loaded right now.", codeVerified: "Code verified", codeNotVerified: "Code not verified", pending: "Waiting for resident replies",
  reasonSignIn: "Sign in with a driver token to see your registered stops and record deliveries. Showing the sample route.", reasonNotDriver: "This is not a driver token. Sign in as a driver to record deliveries. Showing the sample route.", reasonUnreachable: "The server could not be reached. Showing the sample route.", reasonServer: "The server could not load your stops. Showing the sample route.", loadingStops: "Loading your stops…",
  liveNote: "Live · Stops and deliveries come from the JalLekha server. The code goes only to a stop’s registered representative, and the server checks that you are at the stop.",
  stopLabel: "Stop", chooseStopLive: "Choose a stop", stepStart: "1. Start the delivery", startDelivery: "Start delivery", started: "Delivery {id} started at {stop}.", stepCode: "2. Send the code to a registered representative", whoGetsCode: "Who should receive the code?", numberEnding: "number ending {digits}", sendCode: "Send code", sendNewCode: "Send a new code", codeSent: "Code sent to {rep}. Ask them for it; it is valid until {time}.",
  stepVerify: "3. Enter the code at the stop", checkAtLocation: "Check code at my location", checking: "Checking…", geoProblem: "Your position could not be read, so the code was checked without it. Turn on location for this site and try again.", retryLocation: "Try again with my location",
  resultVerified: "Code verified at the stop. Residents at this stop are now asked by SMS whether the water arrived.", resultAlreadyVerified: "This delivery’s code is already verified.", resultWrong: "That code is not right. Wrong tries so far: {n}. Too many wrong tries lock the code for this stop.", resultOutside: "You are about {distance} m from the stop. The code can only be checked within {radius} m. Move closer and try again; this try did not use up an attempt.", resultNoLocation: "No position was sent, so the server could not check that you are at the stop. This try did not use up an attempt.", resultInvalidLocation: "The position could not be used. Try again; this try did not use up an attempt.", resultLocked: "The code is locked for this stop after too many wrong tries. Contact your dispatcher.", resultExpired: "The code has expired. Send a new code.", resultNoOtp: "No code has been sent for this delivery yet. Send a code first.",
  outcomeHeading: "Delivery outcome", replies: "Resident replies: {replies} of {sampled} asked", countsDebt: "Counts toward water debt: {value}", yes: "Yes", no: "No", notDecided: "Not decided yet", refreshOutcome: "Refresh outcome",
  errorSignIn: "Sign in with a driver token to record deliveries.", errorNotDriver: "This is not a driver token. Sign in as a driver to record deliveries.", errorUnreachable: "The server could not be reached. Nothing was recorded; try again.", errorRefused: "The server did not accept this step: {message}",
};
type LiveKey = keyof typeof liveEn;

const liveCopy: Record<Locale, Record<LiveKey, string>> = {
  en: liveEn,
  te: {
    liveIntro: "JalLekha సర్వర్‌లో నమోదైన నిలుపులు. డెలివరీ నిర్ధారణ నమోదు చేయడానికి ఒక నిలుపును తెరవండి.", driverLabel: "డ్రైవర్", deliveriesRecorded: "నమోదైన డెలివరీలు", awaitingOutcome: "ఫలితం కోసం వేచి ఉంది", stopCounts: "{reps} ప్రతినిధులు · {residents} నివాసితులు", syntheticStop: "కల్పిత పరీక్ష నిలుపు", yourDeliveries: "మీ డెలివరీలు", noDeliveries: "ఇంకా డెలివరీలు నమోదు కాలేదు.", deliveriesUnavailable: "మీ డెలివరీలను ఇప్పుడు లోడ్ చేయలేకపోయాం.", codeVerified: "కోడ్ నిర్ధారించబడింది", codeNotVerified: "కోడ్ నిర్ధారించలేదు", pending: "నివాసితుల సమాధానాల కోసం వేచి ఉంది",
    reasonSignIn: "మీ నమోదైన నిలుపులు చూడడానికి మరియు డెలివరీలు నమోదు చేయడానికి డ్రైవర్ టోకెన్‌తో సైన్ ఇన్ చేయండి. నమూనా మార్గం చూపబడుతోంది.", reasonNotDriver: "ఇది డ్రైవర్ టోకెన్ కాదు. డెలివరీలు నమోదు చేయడానికి డ్రైవర్‌గా సైన్ ఇన్ చేయండి. నమూనా మార్గం చూపబడుతోంది.", reasonUnreachable: "సర్వర్‌ను చేరుకోలేకపోయాం. నమూనా మార్గం చూపబడుతోంది.", reasonServer: "సర్వర్ మీ నిలుపులను లోడ్ చేయలేకపోయింది. నమూనా మార్గం చూపబడుతోంది.", loadingStops: "మీ నిలుపులు లోడ్ అవుతున్నాయి…",
    liveNote: "ప్రత్యక్షం · నిలుపులు, డెలివరీలు JalLekha సర్వర్ నుండి వస్తాయి. కోడ్ నిలుపులో నమోదైన ప్రతినిధికి మాత్రమే వెళ్తుంది; మీరు నిలుపు వద్ద ఉన్నారో సర్వర్ తనిఖీ చేస్తుంది.",
    stopLabel: "నిలుపు", chooseStopLive: "నిలుపును ఎంచుకోండి", stepStart: "1. డెలివరీ ప్రారంభించండి", startDelivery: "డెలివరీ ప్రారంభించండి", started: "డెలివరీ {id} {stop} వద్ద ప్రారంభమైంది.", stepCode: "2. నమోదైన ప్రతినిధికి కోడ్ పంపండి", whoGetsCode: "కోడ్ ఎవరికి వెళ్లాలి?", numberEnding: "{digits}తో ముగిసే నంబరు", sendCode: "కోడ్ పంపండి", sendNewCode: "కొత్త కోడ్ పంపండి", codeSent: "కోడ్ {rep}కి పంపబడింది. వారిని అడగండి; ఇది {time} వరకు చెల్లుతుంది.",
    stepVerify: "3. నిలుపు వద్ద కోడ్ నమోదు చేయండి", checkAtLocation: "నా స్థానంలో కోడ్ తనిఖీ చేయండి", checking: "తనిఖీ చేస్తోంది…", geoProblem: "మీ స్థానాన్ని చదవలేకపోయాం, కాబట్టి కోడ్ స్థానం లేకుండా తనిఖీ చేయబడింది. ఈ సైట్‌కు స్థాన అనుమతి ఇచ్చి మళ్లీ ప్రయత్నించండి.", retryLocation: "నా స్థానంతో మళ్లీ ప్రయత్నించండి",
    resultVerified: "నిలుపు వద్ద కోడ్ నిర్ధారించబడింది. నీరు వచ్చిందో లేదో ఈ నిలుపు నివాసితులను ఇప్పుడు SMS ద్వారా అడుగుతున్నారు.", resultAlreadyVerified: "ఈ డెలివరీ కోడ్ ఇప్పటికే నిర్ధారించబడింది.", resultWrong: "ఆ కోడ్ సరైనది కాదు. ఇప్పటివరకు తప్పు ప్రయత్నాలు: {n}. ఎక్కువ తప్పు ప్రయత్నాలు చేస్తే ఈ నిలుపుకు కోడ్ లాక్ అవుతుంది.", resultOutside: "మీరు నిలుపు నుండి సుమారు {distance} మీ. దూరంలో ఉన్నారు. కోడ్‌ను {radius} మీ. లోపల మాత్రమే తనిఖీ చేయగలరు. దగ్గరకు వెళ్లి మళ్లీ ప్రయత్నించండి; ఈ ప్రయత్నం లెక్కలోకి రాలేదు.", resultNoLocation: "స్థానం పంపలేదు, కాబట్టి మీరు నిలుపు వద్ద ఉన్నారో సర్వర్ తనిఖీ చేయలేకపోయింది. ఈ ప్రయత్నం లెక్కలోకి రాలేదు.", resultInvalidLocation: "ఈ స్థానాన్ని ఉపయోగించలేకపోయాం. మళ్లీ ప్రయత్నించండి; ఈ ప్రయత్నం లెక్కలోకి రాలేదు.", resultLocked: "ఎక్కువ తప్పు ప్రయత్నాల వల్ల ఈ నిలుపుకు కోడ్ లాక్ అయింది. మీ డిస్పాచర్‌ను సంప్రదించండి.", resultExpired: "కోడ్ గడువు ముగిసింది. కొత్త కోడ్ పంపండి.", resultNoOtp: "ఈ డెలివరీకి ఇంకా కోడ్ పంపలేదు. ముందుగా కోడ్ పంపండి.",
    outcomeHeading: "డెలివరీ ఫలితం", replies: "నివాసితుల సమాధానాలు: అడిగిన {sampled} మందిలో {replies}", countsDebt: "నీటి బకాయిలో లెక్కిస్తారు: {value}", yes: "అవును", no: "కాదు", notDecided: "ఇంకా నిర్ణయం కాలేదు", refreshOutcome: "ఫలితాన్ని తాజాపరచండి",
    errorSignIn: "డెలివరీలు నమోదు చేయడానికి డ్రైవర్ టోకెన్‌తో సైన్ ఇన్ చేయండి.", errorNotDriver: "ఇది డ్రైవర్ టోకెన్ కాదు. డెలివరీలు నమోదు చేయడానికి డ్రైవర్‌గా సైన్ ఇన్ చేయండి.", errorUnreachable: "సర్వర్‌ను చేరుకోలేకపోయాం. ఏదీ నమోదు కాలేదు; మళ్లీ ప్రయత్నించండి.", errorRefused: "సర్వర్ ఈ దశను అంగీకరించలేదు: {message}",
  },
  ur: {
    liveIntro: "JalLekha سرور پر رجسٹرڈ مقامات۔ ترسیل کی تصدیق درج کرنے کے لیے کوئی مقام کھولیں۔", driverLabel: "ڈرائیور", deliveriesRecorded: "درج شدہ ترسیلیں", awaitingOutcome: "نتیجے کا انتظار", stopCounts: "{reps} نمائندے · {residents} رہائشی", syntheticStop: "مصنوعی آزمائشی مقام", yourDeliveries: "آپ کی ترسیلیں", noDeliveries: "ابھی کوئی ترسیل درج نہیں۔", deliveriesUnavailable: "آپ کی ترسیلیں ابھی لوڈ نہیں ہوسکیں۔", codeVerified: "کوڈ کی تصدیق ہوگئی", codeNotVerified: "کوڈ کی تصدیق نہیں ہوئی", pending: "رہائشیوں کے جوابات کا انتظار",
    reasonSignIn: "اپنے رجسٹرڈ مقامات دیکھنے اور ترسیل درج کرنے کے لیے ڈرائیور ٹوکن سے سائن ان کریں۔ نمونہ راستہ دکھایا جارہا ہے۔", reasonNotDriver: "یہ ڈرائیور ٹوکن نہیں ہے۔ ترسیل درج کرنے کے لیے ڈرائیور کے طور پر سائن ان کریں۔ نمونہ راستہ دکھایا جارہا ہے۔", reasonUnreachable: "سرور سے رابطہ نہیں ہوسکا۔ نمونہ راستہ دکھایا جارہا ہے۔", reasonServer: "سرور آپ کے مقامات لوڈ نہیں کرسکا۔ نمونہ راستہ دکھایا جارہا ہے۔", loadingStops: "آپ کے مقامات لوڈ ہورہے ہیں…",
    liveNote: "براہ راست · مقامات اور ترسیلیں JalLekha سرور سے آتی ہیں۔ کوڈ صرف مقام کے رجسٹرڈ نمائندے کو جاتا ہے، اور سرور جانچتا ہے کہ آپ مقام پر موجود ہیں۔",
    stopLabel: "مقام", chooseStopLive: "مقام منتخب کریں", stepStart: "1. ترسیل شروع کریں", startDelivery: "ترسیل شروع کریں", started: "ترسیل {id} مقام {stop} پر شروع ہوگئی۔", stepCode: "2. رجسٹرڈ نمائندے کو کوڈ بھیجیں", whoGetsCode: "کوڈ کسے ملنا چاہیے؟", numberEnding: "نمبر کے آخری ہندسے {digits}", sendCode: "کوڈ بھیجیں", sendNewCode: "نیا کوڈ بھیجیں", codeSent: "کوڈ {rep} کو بھیج دیا گیا۔ ان سے کوڈ پوچھیں؛ یہ {time} تک درست ہے۔",
    stepVerify: "3. مقام پر کوڈ درج کریں", checkAtLocation: "میرے مقام پر کوڈ جانچیں", checking: "جانچ ہورہی ہے…", geoProblem: "آپ کا مقام معلوم نہیں ہوسکا، اس لیے کوڈ مقام کے بغیر جانچا گیا۔ اس سائٹ کے لیے لوکیشن کی اجازت دیں اور دوبارہ کوشش کریں۔", retryLocation: "میرے مقام کے ساتھ دوبارہ کوشش کریں",
    resultVerified: "مقام پر کوڈ کی تصدیق ہوگئی۔ اب اس مقام کے رہائشیوں سے SMS کے ذریعے پوچھا جارہا ہے کہ پانی پہنچا یا نہیں۔", resultAlreadyVerified: "اس ترسیل کے کوڈ کی پہلے ہی تصدیق ہوچکی ہے۔", resultWrong: "یہ کوڈ درست نہیں۔ اب تک غلط کوششیں: {n}۔ زیادہ غلط کوششوں پر اس مقام کا کوڈ بند ہوجاتا ہے۔", resultOutside: "آپ مقام سے تقریباً {distance} میٹر دور ہیں۔ کوڈ صرف {radius} میٹر کے اندر جانچا جاسکتا ہے۔ قریب جاکر دوبارہ کوشش کریں؛ یہ کوشش شمار نہیں ہوئی۔", resultNoLocation: "کوئی مقام نہیں بھیجا گیا، اس لیے سرور یہ نہیں جانچ سکا کہ آپ مقام پر ہیں۔ یہ کوشش شمار نہیں ہوئی۔", resultInvalidLocation: "یہ مقام استعمال نہیں ہوسکا۔ دوبارہ کوشش کریں؛ یہ کوشش شمار نہیں ہوئی۔", resultLocked: "زیادہ غلط کوششوں کی وجہ سے اس مقام کا کوڈ بند ہوگیا ہے۔ اپنے ڈسپیچر سے رابطہ کریں۔", resultExpired: "کوڈ کی مدت ختم ہوگئی۔ نیا کوڈ بھیجیں۔", resultNoOtp: "اس ترسیل کے لیے ابھی کوئی کوڈ نہیں بھیجا گیا۔ پہلے کوڈ بھیجیں۔",
    outcomeHeading: "ترسیل کا نتیجہ", replies: "رہائشیوں کے جوابات: {sampled} میں سے {replies}", countsDebt: "پانی کے بقایا میں شمار: {value}", yes: "ہاں", no: "نہیں", notDecided: "ابھی فیصلہ نہیں ہوا", refreshOutcome: "نتیجہ تازہ کریں",
    errorSignIn: "ترسیل درج کرنے کے لیے ڈرائیور ٹوکن سے سائن ان کریں۔", errorNotDriver: "یہ ڈرائیور ٹوکن نہیں ہے۔ ترسیل درج کرنے کے لیے ڈرائیور کے طور پر سائن ان کریں۔", errorUnreachable: "سرور سے رابطہ نہیں ہوسکا۔ کچھ درج نہیں ہوا؛ دوبارہ کوشش کریں۔", errorRefused: "سرور نے یہ مرحلہ قبول نہیں کیا: {message}",
  },
  hi: {
    liveIntro: "JalLekha सर्वर पर पंजीकृत पड़ाव। डिलीवरी की पुष्टि दर्ज करने के लिए कोई पड़ाव खोलें।", driverLabel: "ड्राइवर", deliveriesRecorded: "दर्ज डिलीवरी", awaitingOutcome: "नतीजे का इंतज़ार", stopCounts: "{reps} प्रतिनिधि · {residents} निवासी", syntheticStop: "सिंथेटिक परीक्षण पड़ाव", yourDeliveries: "आपकी डिलीवरी", noDeliveries: "अभी कोई डिलीवरी दर्ज नहीं है।", deliveriesUnavailable: "आपकी डिलीवरी अभी लोड नहीं हो सकीं।", codeVerified: "कोड की पुष्टि हुई", codeNotVerified: "कोड की पुष्टि नहीं हुई", pending: "निवासियों के जवाब का इंतज़ार",
    reasonSignIn: "अपने पंजीकृत पड़ाव देखने और डिलीवरी दर्ज करने के लिए ड्राइवर टोकन से साइन इन करें। नमूना मार्ग दिखाया जा रहा है।", reasonNotDriver: "यह ड्राइवर टोकन नहीं है। डिलीवरी दर्ज करने के लिए ड्राइवर के रूप में साइन इन करें। नमूना मार्ग दिखाया जा रहा है।", reasonUnreachable: "सर्वर से संपर्क नहीं हो सका। नमूना मार्ग दिखाया जा रहा है।", reasonServer: "सर्वर आपके पड़ाव लोड नहीं कर सका। नमूना मार्ग दिखाया जा रहा है।", loadingStops: "आपके पड़ाव लोड हो रहे हैं…",
    liveNote: "लाइव · पड़ाव और डिलीवरी JalLekha सर्वर से आते हैं। कोड सिर्फ पड़ाव के पंजीकृत प्रतिनिधि को जाता है, और सर्वर जांचता है कि आप पड़ाव पर हैं।",
    stopLabel: "पड़ाव", chooseStopLive: "पड़ाव चुनें", stepStart: "1. डिलीवरी शुरू करें", startDelivery: "डिलीवरी शुरू करें", started: "डिलीवरी {id} पड़ाव {stop} पर शुरू हुई।", stepCode: "2. पंजीकृत प्रतिनिधि को कोड भेजें", whoGetsCode: "कोड किसे मिलना चाहिए?", numberEnding: "{digits} पर खत्म होने वाला नंबर", sendCode: "कोड भेजें", sendNewCode: "नया कोड भेजें", codeSent: "कोड {rep} को भेजा गया। उनसे कोड पूछें; यह {time} तक मान्य है।",
    stepVerify: "3. पड़ाव पर कोड डालें", checkAtLocation: "मेरे स्थान पर कोड जांचें", checking: "जांच हो रही है…", geoProblem: "आपका स्थान पढ़ा नहीं जा सका, इसलिए कोड बिना स्थान के जांचा गया। इस साइट के लिए लोकेशन चालू करें और फिर कोशिश करें।", retryLocation: "मेरे स्थान के साथ फिर कोशिश करें",
    resultVerified: "पड़ाव पर कोड की पुष्टि हुई। अब इस पड़ाव के निवासियों से SMS पर पूछा जा रहा है कि पानी पहुंचा या नहीं।", resultAlreadyVerified: "इस डिलीवरी के कोड की पहले ही पुष्टि हो चुकी है।", resultWrong: "यह कोड सही नहीं है। अब तक गलत कोशिशें: {n}। ज़्यादा गलत कोशिशों पर इस पड़ाव का कोड बंद हो जाता है।", resultOutside: "आप पड़ाव से लगभग {distance} मीटर दूर हैं। कोड सिर्फ {radius} मीटर के अंदर जांचा जा सकता है। पास जाकर फिर कोशिश करें; यह कोशिश गिनी नहीं गई।", resultNoLocation: "कोई स्थान नहीं भेजा गया, इसलिए सर्वर जांच नहीं सका कि आप पड़ाव पर हैं। यह कोशिश गिनी नहीं गई।", resultInvalidLocation: "यह स्थान इस्तेमाल नहीं हो सका। फिर कोशिश करें; यह कोशिश गिनी नहीं गई।", resultLocked: "ज़्यादा गलत कोशिशों के कारण इस पड़ाव का कोड बंद हो गया है। अपने डिस्पैचर से संपर्क करें।", resultExpired: "कोड की अवधि खत्म हो गई। नया कोड भेजें।", resultNoOtp: "इस डिलीवरी के लिए अभी कोई कोड नहीं भेजा गया। पहले कोड भेजें।",
    outcomeHeading: "डिलीवरी का नतीजा", replies: "निवासियों के जवाब: पूछे गए {sampled} में से {replies}", countsDebt: "पानी के बकाये में गिना जाएगा: {value}", yes: "हां", no: "नहीं", notDecided: "अभी तय नहीं", refreshOutcome: "नतीजा ताज़ा करें",
    errorSignIn: "डिलीवरी दर्ज करने के लिए ड्राइवर टोकन से साइन इन करें।", errorNotDriver: "यह ड्राइवर टोकन नहीं है। डिलीवरी दर्ज करने के लिए ड्राइवर के रूप में साइन इन करें।", errorUnreachable: "सर्वर से संपर्क नहीं हो सका। कुछ दर्ज नहीं हुआ; फिर कोशिश करें।", errorRefused: "सर्वर ने यह चरण स्वीकार नहीं किया: {message}",
  },
};

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in values ? String(values[name]) : match));
}

/** The device position for the server's geofence check, or null when it is denied or unavailable. */
function readPosition(): Promise<{ lat: number; lon: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ lat: coords.latitude, lon: coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  });
}

type Verify = { result: VerifyResult; location: LocationCheck; wrongAttempts: number };
// Kept by the screen (not the proof panel) so a delivery in progress survives going back to the route.
type LiveProofState = { delivery: DeliveryView | null; representativeId: string; sentTo: string | null; code: string; verify: Verify | null; outcome: DeliveryView | null; geoProblem: boolean; error: string | null };
const emptyProof: LiveProofState = { delivery: null, representativeId: "", sentTo: null, code: "", verify: null, outcome: null, geoProblem: false, error: null };
type OutcomeRow = { id: Outcome; color: string; rule: string };

function LiveProof({ words, lw, locale, stops, driverId, stopId, onStopChange, proof, setProof, outcomes, onRecorded }: {
  words: Record<string, string>; lw: Record<LiveKey, string>; locale: Locale; stops: StopView[]; driverId: string; stopId: string | null;
  onStopChange: (stopId: string | null) => void; proof: LiveProofState; setProof: Dispatch<SetStateAction<LiveProofState>>; outcomes: OutcomeRow[]; onRecorded: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const delivery = proof.delivery;
  const stop = stops.find((item) => item.stop_id === (delivery?.stop_id ?? stopId)) ?? null;
  const digits = delivery?.otp_digits ?? 6;
  const canStart = stop !== null && (delivery === null || delivery.otp_verified);
  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  const update = (patch: Partial<LiveProofState>) => setProof((current) => ({ ...current, ...patch }));

  function errorText(cause: unknown): string {
    if (!(cause instanceof ApiError) || cause.status === 0) return lw.errorUnreachable;
    if (cause.status === 401) return lw.errorSignIn;
    if (cause.status === 403) return lw.errorNotDriver;
    return fill(lw.errorRefused, { message: cause.message });
  }

  // One step at a time; a failed step shows why and changes nothing on screen.
  async function run(action: () => Promise<void>) {
    setBusy(true);
    update({ error: null });
    try {
      await action();
    } catch (cause) {
      update({ error: errorText(cause) });
    } finally {
      setBusy(false);
    }
  }

  const path = (id: string, rest = "") => `/deliveries/${encodeURIComponent(id)}${rest}`;
  const loadOutcome = async (id: string) => update({ outcome: await apiFetch<DeliveryView>(path(id)) });

  const start = (event: FormEvent) => {
    event.preventDefault();
    if (!stop) return;
    void run(async () => {
      const started = await apiFetch<DeliveryView>("/deliveries", { method: "POST", body: { delivery_id: newDeliveryId(), stop_id: stop.stop_id, driver_id: driverId } });
      setProof({ ...emptyProof, delivery: started });
      onRecorded();
    });
  };

  const sendCode = (event: FormEvent) => {
    event.preventDefault();
    if (!delivery || !proof.representativeId) return;
    const representativeId = proof.representativeId;
    void run(async () => {
      const issued = await apiFetch<DeliveryView>(path(delivery.delivery_id, "/otp"), { method: "POST", body: { representative_id: representativeId } });
      update({ delivery: issued, sentTo: representativeId, verify: null });
    });
  };

  // No position (denied or unavailable) sends no coordinates, so the server itself reports it.
  const checkCode = () => {
    if (!delivery) return;
    const code = proof.code;
    void run(async () => {
      const position = await readPosition();
      update({ geoProblem: position === null });
      const response = await apiFetch<VerifyResponse>(path(delivery.delivery_id, "/otp/verify"), { method: "POST", body: position ? { code, ...position } : { code } });
      const retrySameCode = response.result === "outside_geofence" || response.result === "invalid_location";
      update({ delivery: response.delivery, verify: { result: response.result, location: response.location, wrongAttempts: response.delivery.wrong_attempts }, ...(retrySameCode ? {} : { code: "" }) });
      onRecorded();
      await loadOutcome(response.delivery.delivery_id);
    });
  };

  function resultText(verify: Verify): string {
    const { location } = verify;
    switch (verify.result) {
      case "verified": return lw.resultVerified;
      case "already_verified": return lw.resultAlreadyVerified;
      case "wrong_code": return fill(lw.resultWrong, { n: number(verify.wrongAttempts) });
      case "locked": return lw.resultLocked;
      case "expired": return lw.resultExpired;
      case "no_otp": return lw.resultNoOtp;
      case "invalid_location": return lw.resultInvalidLocation;
      case "outside_geofence":
        if (location.status === "no_location") return lw.resultNoLocation;
        if (location.status === "outside" && location.distance_m !== null && location.radius_m !== null) {
          return fill(lw.resultOutside, { distance: number(Math.round(location.distance_m)), radius: number(location.radius_m) });
        }
        return lw.resultInvalidLocation;
    }
  }

  const outcome = proof.outcome;
  const decided: Outcome | null = outcome ? outcomeKey(outcome.outcome_status) : null;
  const debt = outcome?.counts_toward_debt;
  const time = delivery?.otp_expires_at ? new Date(delivery.otp_expires_at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }) : "";
  const fieldStyle = { minHeight: 48, fontSize: 16 };

  return (
    <section className="driver-proof-panel">
      <h2>{lw.stepStart}</h2>
      <form onSubmit={start}>
        <label htmlFor="driver-live-stop">{lw.stopLabel}</label>
        <select id="driver-live-stop" style={fieldStyle} value={stop?.stop_id ?? ""} disabled={!canStart || busy} onChange={(event) => { onStopChange(event.target.value || null); setProof(emptyProof); }}>
          <option value="">{lw.chooseStopLive}</option>
          {stops.map((item) => <option key={item.stop_id} value={item.stop_id}>{item.stop_id}</option>)}
        </select>
        <button className="button button-dark" type="submit" disabled={!canStart || busy}>{lw.startDelivery}</button>
      </form>
      {delivery && stop && <>
        <p role="status" className="driver-feedback">{fill(lw.started, { id: delivery.delivery_id, stop: delivery.stop_id })}</p>
        <h2>{lw.stepCode}</h2>
        <form onSubmit={sendCode}>
          <fieldset className="driver-feedback-options">
            <legend>{lw.whoGetsCode}</legend>
            {stop.representatives.map((rep) => <label key={rep.id} style={{ minHeight: 48 }}><input type="radio" name="driver-representative" value={rep.id} checked={proof.representativeId === rep.id} disabled={delivery.otp_verified} onChange={() => update({ representativeId: rep.id })} /> {rep.id} · {rep.language.toUpperCase()} · {fill(lw.numberEnding, { digits: rep.phone_last2 })}</label>)}
          </fieldset>
          <button className="button button-dark" type="submit" disabled={!proof.representativeId || busy || delivery.otp_verified}>{delivery.otp_issued ? lw.sendNewCode : lw.sendCode}</button>
        </form>
        {proof.sentTo && delivery.otp_issued && <p role="status" className="driver-feedback">{fill(lw.codeSent, { rep: proof.sentTo, time })}</p>}
        {delivery.otp_issued && <>
          <h2>{lw.stepVerify}</h2>
          <form onSubmit={(event) => { event.preventDefault(); checkCode(); }}>
            <label htmlFor="driver-live-otp">{words.otpLabel}</label>
            <input id="driver-live-otp" inputMode="numeric" autoComplete="one-time-code" maxLength={digits} value={proof.code} onChange={(event) => update({ code: event.target.value.replace(/\D/g, "") })} required />
            <button className="button button-dark" type="submit" disabled={proof.code.length !== digits || busy || delivery.otp_verified}>{busy ? lw.checking : lw.checkAtLocation}</button>
          </form>
          {proof.geoProblem && <div role="alert" className="driver-feedback"><p>{lw.geoProblem}</p><button className="button button-secondary" type="button" disabled={busy || proof.code.length !== digits} onClick={checkCode}>{lw.retryLocation}</button></div>}
          {proof.verify && <p role="status" className="driver-feedback">{resultText(proof.verify)}</p>}
        </>}
      </>}
      {proof.error && <p role="alert" className="driver-feedback">{proof.error}</p>}
      {outcome && <section className={`driver-preview-outcome ${decided ?? ""}`} aria-label={lw.outcomeHeading}>
        <span>{lw.outcomeHeading}</span>
        <strong>{decided ? words[decided] : lw.pending}</strong>
        {decided && <span>{outcomes.find((row) => row.id === decided)?.rule}</span>}
        <span>{fill(lw.replies, { replies: number(outcome.replies), sampled: number(outcome.sampled_residents) })}</span>
        <span>{fill(lw.countsDebt, { value: debt === true ? lw.yes : debt === false ? lw.no : lw.notDecided })}</span>
        <button className="text-button" type="button" disabled={busy} onClick={() => void run(() => loadOutcome(outcome.delivery_id))}>{lw.refreshOutcome}</button>
      </section>}
      <h2>{words.outcomesTitle}</h2>
      <div className="driver-outcome-list">{outcomes.map((row) => <article className={`driver-outcome ${row.color}`} key={row.id}><strong>{words[row.id]}</strong><span>{row.rule}</span></article>)}</div>
      <p className="driver-silence-note">{words.silence}</p>
    </section>
  );
}

export default function DriverExperience({ page, onNavigate }: { page: DriverPage; onNavigate: (item: "driverRoute" | "driverProof" | "help") => void }) {
  const { locale, t } = useLocale();
  const words = copy[locale];
  const lw = liveCopy[locale];
  // Live only for a signed-in driver; a token with no bound user id (the dev token) records under its role name.
  const { status, role, userId } = useAuth();
  const mode = driverMode(status, role);
  const driverId = mode === "live" ? userId ?? role : null;
  const stopsState = useApi<Paged<StopView>>(driverId ? "/stops?limit=200" : null);
  const deliveriesState = useApi<Paged<DeliveryView>>(driverId ? `/deliveries?driver_id=${encodeURIComponent(driverId)}&limit=200` : null);
  const liveStops = stopsState.live ? stopsState.data?.items ?? null : null;
  const liveDeliveries = deliveriesState.data?.items ?? null;
  const reason: DriverFallback | null = liveStops ? null : mode === "live" ? (stopsState.error ? fallbackForError(stopsState.error) : null) : mode === "loading" ? null : mode;
  const reasonText: Record<DriverFallback, string> = { signIn: lw.reasonSignIn, notDriver: lw.reasonNotDriver, unreachable: lw.reasonUnreachable, serverError: lw.reasonServer };
  const [proof, setProof] = useState<LiveProofState>(emptyProof);
  const [liveStop, setLiveStop] = useState<string | null>(null);
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

  function openLiveStop(stopId: string) {
    if (proof.delivery && proof.delivery.stop_id !== stopId) setProof(emptyProof);
    setLiveStop(stopId);
    onNavigate("driverProof");
  }

  const outcomeLabel = (outcome: OutcomeStatus) => {
    const key = outcomeKey(outcome);
    return key ? words[key] : lw.pending;
  };

  const outcomes: OutcomeRow[] = [
    { id: "confirmed", color: "confirmed", rule: words.confirmedRule },
    { id: "disputed", color: "disputed", rule: words.disputedRule },
    { id: "unconfirmed", color: "unconfirmed", rule: words.unconfirmedRule },
    { id: "failed", color: "failed", rule: words.failedRule },
  ];

  return (
    <div className="driver-page driver-experience">
      <div className="driver-heading"><div><p className="eyebrow">{t("driverWorkspace")}</p><h1>{page === "help" ? words.helpTitle : page === "proof" ? words.deliveryProof : words.routeTitle}</h1><p className="muted">{page === "help" ? words.helpText : liveStops ? lw.liveIntro : words.routeIntro}</p></div>{!liveStops && <span className="driver-demo-badge">{words.demo}</span>}</div>
      <div className="driver-source-row" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, margin: "0 0 16px" }}>
        <DataSourceChip state={{ live: liveStops !== null, loading: !liveStops && reason === null, error: reason === "unreachable" ? stopsState.error : null }} />
        {!liveStops && <span className="muted">{reason ? reasonText[reason] : lw.loadingStops}</span>}
      </div>
      {page === "route" && liveStops && <>
        <section className="driver-route-card"><div className="route-card-top"><div><span className="route-label">{words.routeTitle}</span><h2>{lw.driverLabel} {driverId}</h2></div><span className="route-icon" aria-hidden="true">↗</span></div><p>{lw.liveIntro}</p><div className="route-summary"><div><small>{words.stops}</small><strong>{liveStops.length}</strong></div><div><small>{lw.deliveriesRecorded}</small><strong>{liveDeliveries?.length ?? "–"}</strong></div><div><small>{lw.awaitingOutcome}</small><strong>{liveDeliveries?.filter((item) => item.outcome_status === "pending").length ?? "–"}</strong></div></div></section>
        <div className="driver-section-title"><h2>{t("atEachStop")}</h2><p className="muted">{t("stopIntro")}</p></div>
        <div className="driver-stop-list">{liveStops.map((stop, index) => <article className="driver-stop-card" key={stop.stop_id}><span className="driver-stop-number">{String(index + 1).padStart(2, "0")}</span><div className="driver-stop-info"><strong>{stop.stop_id}</strong><small>{fill(lw.stopCounts, { reps: stop.representatives_count, residents: stop.residents_count })}</small>{stop.basis === "SYNTHETIC" && <small>{lw.syntheticStop}</small>}</div><button className="button button-secondary" onClick={() => openLiveStop(stop.stop_id)}>{words.openProof}</button></article>)}</div>
        <div className="driver-section-title"><h2>{lw.yourDeliveries}</h2></div>
        {deliveriesState.error ? <p className="driver-arrival-state">{lw.deliveriesUnavailable}</p> : liveDeliveries === null ? null :liveDeliveries.length === 0 ? <p className="driver-arrival-state">{lw.noDeliveries}</p> : <div className="driver-stop-list driver-delivery-list">{liveDeliveries.map((item) => <article className="driver-stop-card" key={item.delivery_id}><div className="driver-stop-info"><strong>{item.delivery_id}</strong><small>{item.stop_id} · {item.otp_verified ? lw.codeVerified : lw.codeNotVerified}</small></div><span className="driver-status">{outcomeLabel(item.outcome_status)}</span></article>)}</div>}
      </>}
      {page === "route" && !liveStops && <>
        <section className="driver-route-card"><div className="route-card-top"><div><span className="route-label">{words.routeTitle}</span><h2>{words.notAssigned}</h2></div><span className="route-icon" aria-hidden="true">↗</span></div><p>{words.routeIntro}</p><div className="route-summary"><div><small>{words.stops}</small><strong>{stops.length}</strong></div><div><small>{words.firstStop}</small><strong>01</strong></div><div><small>{words.routeStatus}</small><strong>{words.waiting}</strong></div></div></section>
        <div className="driver-section-title"><h2>{t("atEachStop")}</h2><p className="muted">{t("stopIntro")}</p></div>
        <div className="driver-stop-list">{stops.map((stop, index) => <article className="driver-stop-card" key={stop.id}><span className="driver-stop-number">{String(index + 1).padStart(2, "0")}</span><div className="driver-stop-info"><strong>{stop.name}</strong><small>{stop.id} · {words.demo}</small></div><button className="button button-secondary" onClick={() => { setSelectedStop(stop.id); setArrivalRecorded(true); setFeedback(words.arrivalWarning); }}>{words.markArrived}</button></article>)}</div>
        {selectedStop && <div className="driver-arrival-state" role="status"><strong>{words.arrivalSaved}</strong><span>{selectedStop}</span><p>{words.arrivalWarning}</p><button className="button button-dark" onClick={() => onNavigate("driverProof")}>{words.openProof}</button></div>}
      </>}
      {page === "proof" && <>
        <button className="text-button" onClick={() => onNavigate("driverRoute")}>← {words.backRoute}</button>
        {liveStops ? <LiveProof words={words} lw={lw} locale={locale} stops={liveStops} driverId={driverId ?? ""} stopId={liveStop} onStopChange={setLiveStop} proof={proof} setProof={setProof} outcomes={outcomes} onRecorded={deliveriesState.reload} /> : !selectedStop ? <p className="driver-arrival-state">{words.chooseStop}</p> : <section className="driver-proof-panel"><span className="route-label">{selectedStop}</span><h2>{words.enterOtp}</h2><div className="driver-arrival-state compact"><strong>{arrivalRecorded ? words.arrivalSaved : words.arrivalWarning}</strong><p>{words.arrivalWarning}</p></div><form onSubmit={submitCode}><label htmlFor="driver-otp">{words.otpLabel}</label><input id="driver-otp" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))} required /><p className="driver-demo-code">{words.demoOtp}</p><fieldset className="driver-feedback-options"><legend>{words.residentFeedback}</legend><label><input type="radio" name="resident-feedback" checked={residentFeedback === "confirm"} onChange={() => setResidentFeedback("confirm")} /> {words.residentsConfirm}</label><label><input type="radio" name="resident-feedback" checked={residentFeedback === "dispute"} onChange={() => setResidentFeedback("dispute")} /> {words.residentsDispute}</label></fieldset><button className="button button-dark" type="submit" disabled={otp.length !== 6}>{words.checkCode}</button></form>{feedback && <p role="status" className="driver-feedback">{feedback}</p>}{previewOutcome && <div className={`driver-preview-outcome ${previewOutcome}`} role="status"><small>{words.previewResult}</small><strong>{words[previewOutcome]}</strong><span>{outcomes.find((outcome) => outcome.id === previewOutcome)?.rule}</span></div>}<h2>{words.outcomesTitle}</h2><div className="driver-outcome-list">{outcomes.map((outcome) => <article className={`driver-outcome ${outcome.color}`} key={outcome.id}><strong>{words[outcome.id]}</strong><span>{outcome.rule}</span></article>)}</div><p className="driver-silence-note">{words.silence}</p><p className="prototype-note">{words.noCodeTitle}</p></section>}
      </>}
      {page === "help" && <section className="driver-help-panel"><h2>{words.helpTitle}</h2><p>{words.helpText}</p><button className="button button-secondary" onClick={() => onNavigate("driverRoute")}>{words.route}</button></section>}
      <p className="driver-honesty-note">{liveStops ? lw.liveNote : words.demoWarning}</p>
    </div>
  );
}
