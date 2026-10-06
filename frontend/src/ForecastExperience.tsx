import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { ApiError, apiFetch } from "./api";
import DataSourceChip from "./DataSource";
import { useLocale, type Locale } from "./i18n";
import data from "./data/u6Forecast.json";
import { outlookFromApi, sectionsFromForecast, shortageFromApi, sortByRisk, RISK_ORDER,
  type ApiForecastRow, type ApiHistoryRow, type ApiAccuracyRow, type ApiPage,
  type ApiShortageRow, type OutlookMonth, type Risk } from "./forecastAdapter";
import { canFetchOfficerData, liveReason, liveReasonCopy } from "./liveReason";
import "./ForecastExperience.css";
import { currentWarnings, warningWindow } from "./forecastDates";

const warningCopy = {
  en: {estimatedCapacity: "Estimated trips", dataThrough: "Booking data through {month}", capacityHelp: "Section capacity is an estimated share of a filling station's trips, based on earlier bookings. Officers can reassign tankers; it is not a verified limit on service.", warningDates: "Warnings for {start}–{end}. Months ahead are counted from today.", unknownHelp: "Each card is one section in one month. Unknown means booking history or capacity is missing; it does not mean there is no risk.", olderInputs: "The latest booking records are older than the current month. These warnings are forecasts, not a live measure of today's supply."},
  te: {estimatedCapacity: "అంచనా ట్యాంకర్ ప్రయాణాలు", dataThrough: "{month} వరకు బుకింగ్ సమాచారం", capacityHelp: "గత బుకింగ్‌ల ఆధారంగా ఫిల్లింగ్ స్టేషన్ ప్రయాణాల్లో సెక్షన్ వాటాను అంచనా వేశాం. అధికారులు ట్యాంకర్లను వేరే ప్రాంతాలకు కేటాయించవచ్చు; ఇది సేవలకు నిర్ధారిత పరిమితి కాదు.", warningDates: "{start}–{end} కోసం హెచ్చరికలు. ముందున్న నెలలను ఈ రోజు నుంచి లెక్కిస్తాం.", unknownHelp: "ప్రతి కార్డు ఒక నెలలో ఒక సెక్షన్‌ను చూపుతుంది. తెలియదు అంటే బుకింగ్ చరిత్ర లేదా సామర్థ్య సమాచారం లేదు; ప్రమాదం లేదని కాదు.", olderInputs: "తాజా బుకింగ్ రికార్డులు ప్రస్తుత నెల కంటే పాతవి. ఈ హెచ్చరికలు అంచనాలు; ఈ రోజు సరఫరా స్థితిని ప్రత్యక్షంగా కొలిచినవి కావు."},
  ur: {estimatedCapacity: "اندازے کے مطابق ٹینکر کے چکر", dataThrough: "{month} تک بکنگ کا ریکارڈ", capacityHelp: "پچھلی بکنگ کی بنیاد پر بھرائی اسٹیشن کے چکروں میں سیکشن کا حصہ اندازہ کیا گیا ہے۔ افسر ٹینکر دوسری جگہ بھیج سکتے ہیں؛ یہ خدمت کی تصدیق شدہ حد نہیں ہے۔", warningDates: "{start}–{end} کے لیے انتباہات۔ آنے والے مہینے آج سے گنے جاتے ہیں۔", unknownHelp: "ہر کارڈ ایک مہینے کے ایک سیکشن کو دکھاتا ہے۔ نامعلوم کا مطلب بکنگ کی تاریخ یا گنجائش کا ریکارڈ موجود نہیں؛ اس کا مطلب خطرہ نہ ہونا نہیں۔", olderInputs: "تازہ ترین بکنگ ریکارڈ موجودہ مہینے سے پرانے ہیں۔ یہ انتباہات پیش گوئیاں ہیں، آج کی فراہمی کی براہ راست پیمائش نہیں۔"},
  hi: {estimatedCapacity: "अनुमानित टैंकर चक्कर", dataThrough: "{month} तक बुकिंग के रिकॉर्ड", capacityHelp: "पिछली बुकिंग के आधार पर भराई स्टेशन के चक्करों में सेक्शन का हिस्सा अनुमानित है। अधिकारी टैंकर दूसरी जगह भेज सकते हैं; यह सेवा की सत्यापित सीमा नहीं है।", warningDates: "{start}–{end} के लिए चेतावनियाँ। आगे के महीने आज से गिने जाते हैं।", unknownHelp: "हर कार्ड एक महीने में एक सेक्शन दिखाता है। अज्ञात का मतलब बुकिंग इतिहास या क्षमता का रिकॉर्ड नहीं है; इसका मतलब जोखिम न होना नहीं है।", olderInputs: "नवीनतम बुकिंग रिकॉर्ड वर्तमान महीने से पुराने हैं। ये चेतावनियाँ अनुमान हैं, आज की आपूर्ति का सीधा माप नहीं।"},
};

const reasonCopy = {
  en: {missingHistory: "Earlier bookings are missing for this forecast month.", missingMatch: "Earlier section records could not be matched reliably.", riskSummary: "Expected bookings: {expected}; estimated trips: {capacity}; upper estimate: {upper}. Warning: {risk}.", groundwaterReading: "Nearby groundwater is {value} m {direction} than usual ({month}).", deeper: "deeper", shallower: "shallower", storageReading: "Reservoir storage ({month}): {values}. These figures are background only."},
  te: {missingHistory: "ఈ నెల అంచనాకు అవసరమైన గత బుకింగ్‌లు లేవు.", missingMatch: "గత సెక్షన్ రికార్డులను నమ్మదగిన విధంగా సరిపోల్చలేకపోయాం.", riskSummary: "అంచనా బుకింగ్‌లు: {expected}; అంచనా ప్రయాణాలు: {capacity}; ఎగువ అంచనా: {upper}. హెచ్చరిక: {risk}.", groundwaterReading: "సమీప భూగర్భజలం సాధారణం కంటే {value} మీటర్లు {direction} ఉంది ({month}).", deeper: "లోతుగా", shallower: "పైకి", storageReading: "రిజర్వాయర్ నిల్వ ({month}): {values}. ఈ గణాంకాలు నేపథ్య సమాచారం మాత్రమే."},
  ur: {missingHistory: "اس مہینے کی پیش گوئی کے لیے پچھلی بکنگ دستیاب نہیں۔", missingMatch: "پچھلے سیکشن ریکارڈ کا قابل اعتماد ملاپ نہیں ہو سکا۔", riskSummary: "متوقع بکنگ: {expected}؛ اندازے کے چکر: {capacity}؛ بالائی اندازہ: {upper}۔ انتباہ: {risk}۔", groundwaterReading: "قریبی زیر زمین پانی معمول سے {value} میٹر {direction} ہے ({month})۔", deeper: "گہرا", shallower: "اوپر", storageReading: "آبی ذخائر میں پانی ({month}): {values}۔ یہ اعداد صرف پس منظر ہیں۔"},
  hi: {missingHistory: "इस महीने का अनुमान बनाने के लिए पिछली बुकिंग उपलब्ध नहीं है।", missingMatch: "पुराने सेक्शन रिकॉर्ड का भरोसेमंद मिलान नहीं हो पाया।", riskSummary: "अपेक्षित बुकिंग: {expected}; अनुमानित चक्कर: {capacity}; ऊपरी अनुमान: {upper}। चेतावनी: {risk}।", groundwaterReading: "पास का भूजल सामान्य से {value} मीटर {direction} है ({month})।", deeper: "गहरा", shallower: "ऊपर", storageReading: "जलाशयों में पानी ({month}): {values}। ये आँकड़े केवल संदर्भ हैं।"},
};

const rangeCopy = {
  en: {rangeReliability: "In past city checks, the {level}% range contained actual bookings {coverage}% of the time across {months} months. Future demand can fall outside the range."},
  te: {rangeReliability: "గత నగర పరిశీలనల్లో {months} నెలల్లో, {level}% పరిధిలో నిజమైన బుకింగ్‌లు {coverage}% సార్లు ఉన్నాయి. భవిష్యత్ డిమాండ్ ఈ పరిధి బయట కూడా ఉండవచ్చు."},
  ur: {rangeReliability: "شہر کے پچھلے {months} مہینوں کی جانچ میں، {level}% کی حد کے اندر اصل بکنگ {coverage}% بار آئی۔ آئندہ طلب اس حد سے باہر بھی ہو سکتی ہے۔"},
  hi: {rangeReliability: "शहर के पिछले {months} महीनों की जाँच में, {level}% दायरे के अंदर वास्तविक बुकिंग {coverage}% बार रही। भविष्य की माँग इस दायरे से बाहर भी हो सकती है।"},
};

const detailsCopy = {
  en: {warningHelp: "How to read these warnings"},
  te: {warningHelp: "ఈ హెచ్చరికలను ఎలా అర్థం చేసుకోవాలి"},
  ur: {warningHelp: "ان انتباہات کو کیسے سمجھیں"},
  hi: {warningHelp: "इन चेतावनियों को कैसे समझें"},
};

type View = "outlook" | "accuracy" | "shortage";
type Month = {month: string; bookings: number | null};
type Snapshot = {snapshotDate: string; historyEnd: string; history: Month[];
  cityCoverage?: {interval: number; coverage: number | null; months: number}[];
  forecastRows?: ApiForecastRow[]; historyRows?: ApiHistoryRow[];
  accuracyRows?: ApiAccuracyRow[]; shortageRows?: ApiShortageRow[]};
const snapshot = data as Snapshot;
const PAGE = 200;
const SHOW_STEP = 20;
const labels = {
en: {title:"Demand forecast & shortage", intro:"See expected bookings, available trips and how earlier forecasts compared with actual bookings.", outlook:"Next 12 months", accuracy:"How good was our forecast?", shortage:"Shortage warnings", area:"Area", cityTotal:"City total", updated:"Updated {month}", expectedTitle:"Tankers expected per month, {start} – {end}", observed:"Actual bookings", median:"Expected bookings", p80:"80% range", p90:"90% range", capacity:"Available trips", shortBy:"Short by {count}", selectedMonthLabel:"Selected forecast month", noForecast:"No forecast is available for this section: earlier records could not be matched reliably.", loading:"Loading this area…", loadFailed:"This area could not be loaded. Try another area.", noAccuracy:"No earlier forecast can be checked against actual bookings for this area yet.", average:"On average, forecasts were {error}% away from actual bookings across {count} checked months.", past:"{month}: we expected {expected}, actual {actual} — {error}% {direction}.", low:"too low", high:"too high", exact:"matched", shortageNote:"Warnings cover the next 1–3 months. Water levels help explain the situation; they do not set the warning level.", riskListLabel:"Shortage risk list", filterLabel:"Filter by risk", riskAll:"All", riskHigh:"High", riskMedium:"Medium", riskLow:"Low", riskUnknown:"Unknown", ahead:"{count} months ahead", showing:"Showing {shown} of {total}", showMore:"Show more", noRisk:"No warnings for this selection.", rangeUnavailable:"Range unavailable", historyNote:"Solid line: last 12 months of actual bookings. Dashed line: next 12 months. Shading shows the range; the purple line shows available trips.", approximate:"Earlier records were joined using an approximate section match.", waterUnavailable:"Groundwater data unavailable for some sections.", context:"Water levels are context only and are not used to set the risk.", accuracyNote:"These are forecasts made using only earlier records, compared with the actual bookings that followed."},
  te: {title:"డిమాండ్ అంచనా మరియు కొరత", intro:"అంచనా బుకింగ్‌లు, అందుబాటులో ప్రయాణాలు, గత అంచనాలు నిజమైన బుకింగ్‌లతో ఎలా పోలాయో చూడండి.", outlook:"తదుపరి 12 నెలలు", accuracy:"మన అంచనా ఎంత బాగుంది?", shortage:"కొరత హెచ్చరికలు", area:"ప్రాంతం", cityTotal:"నగర మొత్తం", updated:"నవీకరణ {month}", expectedTitle:"నెలకు అంచనా ట్యాంకర్లు, {start} – {end}", observed:"నిజమైన బుకింగ్‌లు", median:"అంచనా బుకింగ్‌లు", p80:"80% పరిధి", p90:"90% పరిధి", capacity:"అందుబాటులో ప్రయాణాలు", shortBy:"{count} తక్కువ", selectedMonthLabel:"ఎంచుకున్న అంచనా నెల", noForecast:"ఈ సెక్షన్‌కు అంచనా లేదు: పాత రికార్డులను నమ్మకంగా జతచేయలేకపోయాం.", loading:"ఈ ప్రాంతం లోడ్ అవుతోంది…", loadFailed:"ఈ ప్రాంతం లోడ్ కాలేదు. మరో ప్రాంతాన్ని ప్రయత్నించండి.", noAccuracy:"ఈ ప్రాంతంలో గత అంచనాలను నిజమైన బుకింగ్‌లతో ఇంకా పోల్చలేం.", average:"{count} పరిశీలించిన నెలల్లో అంచనాలు నిజమైన బుకింగ్‌లకు సగటున {error}% దూరంగా ఉన్నాయి.", past:"{month}: అంచనా {expected}, నిజమైనవి {actual} — {error}% {direction}.", low:"తక్కువ", high:"ఎక్కువ", exact:"సరిపోయింది", shortageNote:"హెచ్చరికలు తదుపరి 1–3 నెలలకు. నీటి స్థాయులు పరిస్థితిని వివరిస్తాయి; హెచ్చరిక స్థాయిని నిర్ణయించవు.", riskListLabel:"కొరత ప్రమాద జాబితా", filterLabel:"ప్రమాదం ప్రకారం వడపోత", riskAll:"అన్నీ", riskHigh:"అధికం", riskMedium:"మధ్యస్థం", riskLow:"తక్కువ", riskUnknown:"తెలియదు", ahead:"{count} నెలలు ముందుగా", showing:"{total}లో {shown} చూపిస్తున్నాం", showMore:"మరిన్ని చూపించు", noRisk:"ఈ ఎంపికకు హెచ్చరికలు లేవు.", rangeUnavailable:"పరిధి అందుబాటులో లేదు", historyNote:"గట్టి గీత: గత 12 నెలల నిజమైన బుకింగ్‌లు. చుక్కల గీత: తదుపరి 12 నెలలు. నీడ పరిధిని, ఊదా గీత అందుబాటులో ప్రయాణాలను చూపుతుంది.", approximate:"పాత రికార్డులను సుమారు సెక్షన్ సరిపోలికతో జతచేశాం.", waterUnavailable:"కొన్ని సెక్షన్‌లకు భూగర్భజల సమాచారం లేదు.", context:"నీటి స్థాయులు సందర్భం మాత్రమే; ప్రమాద స్థాయిని నిర్ణయించవు.", accuracyNote:"అంతకు ముందున్న రికార్డులతో చేసిన అంచనాలను తరువాత వచ్చిన నిజమైన బుకింగ్‌లతో పోల్చాం."},
  ur: {title:"طلب کی پیش گوئی اور قلت", intro:"متوقع بکنگ، دستیاب چکر اور پچھلی پیش گوئیوں کا اصل بکنگ سے موازنہ دیکھیں۔", outlook:"اگلے 12 مہینے", accuracy:"ہماری پیش گوئی کتنی اچھی تھی؟", shortage:"قلت کی تنبیہ", area:"علاقہ", cityTotal:"شہر کا مجموعہ", updated:"تازہ کاری {month}", expectedTitle:"ہر ماہ متوقع ٹینکر، {start} – {end}", observed:"اصل بکنگ", median:"متوقع بکنگ", p80:"80% حد", p90:"90% حد", capacity:"دستیاب چکر", shortBy:"{count} کی کمی", selectedMonthLabel:"منتخب پیش گوئی کا مہینہ", noForecast:"اس سیکشن کی پیش گوئی دستیاب نہیں: پرانے ریکارڈ قابل اعتماد طور پر نہیں مل سکے۔", loading:"علاقہ لوڈ ہو رہا ہے…", loadFailed:"علاقہ لوڈ نہیں ہو سکا۔ دوسرا علاقہ آزمائیں۔", noAccuracy:"اس علاقے کی پرانی پیش گوئی کا اصل بکنگ سے موازنہ ابھی دستیاب نہیں۔", average:"{count} جانچے گئے مہینوں میں پیش گوئیاں اصل بکنگ سے اوسطاً {error}% دور تھیں۔", past:"{month}: متوقع {expected}، اصل {actual} — {error}% {direction}۔", low:"کم", high:"زیادہ", exact:"برابر", shortageNote:"تنبیہ اگلے 1–3 مہینوں کے لیے ہے۔ پانی کی سطح صورت حال سمجھاتی ہے؛ خطرے کی سطح طے نہیں کرتی۔", riskListLabel:"قلت کے خطرات کی فہرست", filterLabel:"خطرے کے مطابق چھانٹیں", riskAll:"سب", riskHigh:"زیادہ", riskMedium:"درمیانہ", riskLow:"کم", riskUnknown:"نامعلوم", ahead:"{count} مہینے آگے", showing:"{total} میں سے {shown} دکھائے گئے", showMore:"مزید دکھائیں", noRisk:"اس انتخاب کے لیے کوئی تنبیہ نہیں۔", rangeUnavailable:"حد دستیاب نہیں", historyNote:"ٹھوس لکیر: گزشتہ 12 مہینوں کی اصل بکنگ۔ ٹوٹی لکیر: اگلے 12 مہینے۔ سایہ حد اور جامنی لکیر دستیاب چکر دکھاتی ہے۔", approximate:"پرانے ریکارڈ سیکشن کے اندازاً ملاپ سے جوڑے گئے۔", waterUnavailable:"کچھ سیکشنوں کے لیے زیر زمین پانی کا ڈیٹا دستیاب نہیں۔", context:"پانی کی سطح صرف وضاحت ہے اور خطرہ طے کرنے میں استعمال نہیں ہوتی۔", accuracyNote:"صرف پہلے کے ریکارڈ سے بنائی گئی پیش گوئیوں کا بعد میں آنے والی اصل بکنگ سے موازنہ کیا گیا ہے۔"},
  hi: {title:"माँग का पूर्वानुमान और कमी", intro:"अपेक्षित बुकिंग, उपलब्ध चक्कर और पिछले पूर्वानुमानों की वास्तविक बुकिंग से तुलना देखें।", outlook:"अगले 12 महीने", accuracy:"हमारा पूर्वानुमान कितना अच्छा था?", shortage:"कमी की चेतावनी", area:"क्षेत्र", cityTotal:"शहर का योग", updated:"अद्यतन {month}", expectedTitle:"हर महीने अपेक्षित टैंकर, {start} – {end}", observed:"वास्तविक बुकिंग", median:"अपेक्षित बुकिंग", p80:"80% दायरा", p90:"90% दायरा", capacity:"उपलब्ध चक्कर", shortBy:"{count} की कमी", selectedMonthLabel:"चुना गया पूर्वानुमान महीना", noForecast:"इस सेक्शन का पूर्वानुमान उपलब्ध नहीं: पुराने रिकॉर्ड भरोसेमंद ढंग से नहीं जुड़ सके।", loading:"क्षेत्र लोड हो रहा है…", loadFailed:"क्षेत्र लोड नहीं हो सका। दूसरा क्षेत्र आजमाएँ।", noAccuracy:"इस क्षेत्र के पुराने पूर्वानुमान की वास्तविक बुकिंग से तुलना अभी उपलब्ध नहीं।", average:"जाँचे गए {count} महीनों में पूर्वानुमान वास्तविक बुकिंग से औसतन {error}% दूर थे।", past:"{month}: हमने {expected} अपेक्षित किए, वास्तविक {actual} — {error}% {direction}।", low:"कम", high:"अधिक", exact:"बराबर", shortageNote:"चेतावनी अगले 1–3 महीनों के लिए है। जल स्तर स्थिति समझाते हैं; जोखिम का स्तर तय नहीं करते।", riskListLabel:"कमी जोखिम सूची", filterLabel:"जोखिम के अनुसार छाँटें", riskAll:"सभी", riskHigh:"उच्च", riskMedium:"मध्यम", riskLow:"कम", riskUnknown:"अज्ञात", ahead:"{count} महीने आगे", showing:"{total} में से {shown} दिखाए गए", showMore:"और दिखाएँ", noRisk:"इस चयन के लिए कोई चेतावनी नहीं।", rangeUnavailable:"दायरा उपलब्ध नहीं", historyNote:"ठोस रेखा: पिछले 12 महीनों की वास्तविक बुकिंग। टूटी रेखा: अगले 12 महीने। छाया दायरा और बैंगनी रेखा उपलब्ध चक्कर दिखाती है।", approximate:"पुराने रिकॉर्ड सेक्शन के अनुमानित मिलान से जोड़े गए।", waterUnavailable:"कुछ सेक्शनों के लिए भूजल डेटा उपलब्ध नहीं।", context:"जल स्तर केवल संदर्भ हैं और जोखिम तय करने में उपयोग नहीं होते।", accuracyNote:"केवल पुराने रिकॉर्ड से बने पूर्वानुमानों की बाद की वास्तविक बुकिंग से तुलना की गई है।"}
} satisfies Record<Locale, Record<string,string>>;

function fill(text: string, values: Record<string,string>) {
  return text.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? "");
}

/** Read all pages with the API's 200-row limit, including long section and warning lists. */
function usePagedApi<T>(path: string | null) {
  const [settled, setSettled] = useState<{path:string; data:ApiPage<T> | null; error:ApiError | null} | null>(null);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    (async () => {
      const items:T[] = [];
      let total: number;
      do {
        const page = await apiFetch<ApiPage<T>>(path + "&limit=" + PAGE + "&offset=" + items.length, {signal:controller.signal});
        total = page.total;
        items.push(...page.items);
        if (!page.items.length) break;
      } while (items.length < total);
      if (!controller.signal.aborted) setSettled({path,data:{items,total},error:null});
    })().catch((cause:unknown) => {
      if (!controller.signal.aborted) setSettled({path,data:null,error:cause instanceof ApiError ? cause : new ApiError(0,"network_error","")});
    });
    return () => controller.abort();
  }, [path]);
  const current = settled?.path === path ? settled : null;
  return {data:current?.data ?? null, error:current?.error ?? null, loading:path !== null && current === null, live:current?.data !== null && current !== null};
}

// Section numbers can be below 10 (0.3 trips); one decimal there keeps a small real value from reading as zero.
function number(value: number | null, locale: Locale) { return value === null ? "—" : new Intl.NumberFormat(locale, { maximumFractionDigits: Math.abs(value) < 10 ? 1 : 0 }).format(value); }
function monthName(key: string, locale: Locale) { const [year,month] = key.split("-").map(Number); return new Intl.DateTimeFormat(locale, { month:"short", year:"numeric", timeZone:"UTC" }).format(new Date(Date.UTC(year,month-1,1))); }
function monthSpan(first: string, last: string) {
  const out: string[] = [];
  let [year, month] = first.split("-").map(Number);
  const [endYear, endMonth] = last.split("-").map(Number);
  while (year < endYear || (year === endYear && month <= endMonth)) { out.push(`${year}-${String(month).padStart(2,"0")}`); month += 1; if (month > 12) { month = 1; year += 1; } }
  return out;
}
function niceMax(value: number) { const step = 10 ** Math.floor(Math.log10(Math.max(value, 1))); return Math.ceil(value * 1.05 / step) * step; }

type ChartProps = { history: Month[]; outlook: OutlookMonth[]; selected: string | null; onSelect: (month: string) => void; locale: Locale; title: string; text: { median: string; p80: string; p90: string; capacity: string; observed: string; shortBy: string } };

/** History (REAL) and forecast on one month axis, so a live forecast that overlaps observed months sits over them. */
function OutlookChart({ history, outlook, selected, onSelect, locale, title, text }: ChartProps) {
  const fmt = (v: number | null) => number(v, locale);
  const [hoverMonth, setHoverMonth] = useState<string | null>(null);
  const shown = history.filter((row) => row.month < (outlook[0]?.month ?? "9999")).slice(-12);
  const allMonths = [...shown.map((row) => row.month), ...outlook.map((row) => row.month)].sort();
  if (allMonths.length === 0) return null;
  const months = monthSpan(allMonths[0], allMonths[allMonths.length - 1]);
  const at = new Map(months.map((month, index) => [month, index]));
  const width=900,height=350,left=62,right=24,top=22,bottom=48;
  const x = (month: string) => left + (at.get(month) ?? 0) * (width-left-right) / Math.max(months.length-1, 1);
  const values = [...shown.map((row) => row.bookings), ...outlook.flatMap((row) => [row.median, row.high80, row.high90, row.capacity])].filter((v): v is number => v !== null);
  const maxValue = niceMax(Math.max(...values, 1));
  const y = (value: number) => top + (maxValue-value)/maxValue*(height-top-bottom);
  const ticks = [0, 0.25, 0.5, 0.75].map((f) => f * maxValue);
  const line = (points: { month: string; value: number | null }[]) => { let path = "", open = false; points.forEach((p) => { if (p.value === null) { open = false; return; } path += (open?" L":" M")+x(p.month)+","+y(p.value); open = true; }); return path; };
  const lastObserved = [...shown].reverse().find((row) => row.bookings !== null);
  // The demo fixture continues after the observed months, so its line starts at the last observed point (as before).
  const anchor = lastObserved && outlook.length > 0 && outlook[0].month > lastObserved.month ? { month: lastObserved.month, value: lastObserved.bookings } : null;
  const band = (lower: "low80"|"low90", upper: "high80"|"high90") => {
    const rows = outlook.filter((row) => row[lower] !== null && row[upper] !== null);
    if (rows.length === 0) return null;
    const start = anchor ? [x(anchor.month)+","+y(anchor.value ?? 0)] : [];
    return [...start, ...rows.map((row) => x(row.month)+","+y(row[upper] ?? 0)), ...[...rows].reverse().map((row) => x(row.month)+","+y(row[lower] ?? 0))].join(" ");
  };
  const band80 = band("low80","high80"), band90 = band("low90","high90");
  const forecastPath = line([...(anchor ? [anchor] : []), ...outlook.map((row) => ({ month: row.month, value: row.median }))]);
  const hasCapacity = outlook.some((row) => row.capacity !== null);
  const historyEnd = shown.length ? shown[shown.length-1].month : "";
  const labels = shown.length
    ? [...months.filter((m,i) => i % 3 === 0 && m <= historyEnd).map((m) => ({ month: m, label: monthName(m,locale) })), ...outlook.filter((row) => row.month > historyEnd).map((row) => ({ month: row.month, label: monthName(row.month, locale).split(" ")[0] }))]
    : outlook.map((row) => ({ month: row.month, label: monthName(row.month, locale).split(" ")[0] }));
  return <>
    <div className="forecast-chart-scroll forecast-chart-hover" onMouseLeave={() => setHoverMonth(null)}><svg viewBox={"0 0 "+width+" "+height} className="forecast-chart" role="img" aria-label={title}>
      <line x1={left} x2={width-right} y1={y(0)} y2={y(0)} className="chart-axis"/>
      {ticks.map((v)=><g key={v}><line x1={left} x2={width-right} y1={y(v)} y2={y(v)} className="chart-grid"/><text x={left-8} y={y(v)+4} textAnchor="end">{fmt(v)}</text></g>)}
      {band90&&<polygon points={band90} className="range-90"/>}
      {band80&&<polygon points={band80} className="range-80"/>}
      {shown.length>0&&<path d={line(shown.map((row)=>({ month: row.month, value: row.bookings })))} className="history-line"/>}
      {hasCapacity&&<path d={line(outlook.map((row)=>({ month: row.month, value: row.capacity })))} className="capacity-line"/>}
      <path d={forecastPath} className="forecast-line"/>
      {months.map((m)=><rect key={"h"+m} x={x(m)-(width-left-right)/Math.max(months.length-1,1)/2} y={top} width={(width-left-right)/Math.max(months.length-1,1)} height={y(0)-top} fill="transparent" onMouseEnter={()=>setHoverMonth(m)}/>)}
      {outlook.filter((row)=>row.median!==null).map((row)=><g key={row.month} className="forecast-point" tabIndex={0} role="button" aria-label={monthName(row.month,locale)+": "+text.median+" "+fmt(row.median)} onClick={()=>onSelect(row.month)} onKeyDown={(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();onSelect(row.month);}}}><circle cx={x(row.month)} cy={y(row.median ?? 0)} r={selected===row.month?7:5}/><title>{monthName(row.month,locale)} · {fmt(row.median)}</title></g>)}
      {labels.map((item)=><text key={item.month+item.label} x={x(item.month)} y={height-12} textAnchor="middle">{item.label}</text>)}
      {outlook[0]&&<line x1={x(outlook[0].month)} x2={x(outlook[0].month)} y1={top} y2={y(0)} className="forecast-boundary"/>}{hoverMonth&&<line x1={x(hoverMonth)} x2={x(hoverMonth)} y1={top} y2={y(0)} className="chart-hover-line"/>}

    </svg>
    {hoverMonth&&(()=>{ const h = shown.find((row)=>row.month===hoverMonth); const o = outlook.find((row)=>row.month===hoverMonth); const pos = x(hoverMonth)/width*100;
      return <div className="chart-tooltip" style={{ left: `${pos}%`, transform: pos > 60 ? "translateX(-105%)" : "translateX(5%)" }}><strong>{monthName(hoverMonth, locale)}</strong>
        {h&&h.bookings!==null&&<span><i className="history-key"/>{text.observed}: {fmt(h.bookings)}</span>}
        {o&&o.median!==null&&<span><i className="median-key"/>{text.median}: {fmt(o.median)}</span>}
        {o&&o.low80!==null&&o.high80!==null&&<span>{text.p80}: {fmt(o.low80)}?{fmt(o.high80)}</span>}{o&&o.low90!==null&&o.high90!==null&&<span>{text.p90}: {fmt(o.low90)}?{fmt(o.high90)}</span>}{o&&o.capacity!==null&&o.median!==null&&o.median>o.capacity&&<span>{text.shortBy.replace("{count}",fmt(o.median-o.capacity))}</span>}{o&&o.capacity!==null&&<span><i className="capacity-key"/>{text.capacity}: {fmt(o.capacity)}</span>}
        {!(h&&h.bookings!==null)&&!(o&&o.median!==null)&&<span>—</span>}</div>; })()}
    </div>
    <div className="forecast-legend">
      {shown.length>0&&<span><i className="history-key"/>{text.observed}</span>}
      {band80&&<span><i className="range-key range-key-80"/>{text.p80}</span>}
      {band90&&<span><i className="range-key range-key-90"/>{text.p90}</span>}
      <span><i className="median-key"/>{text.median}</span>
      {hasCapacity&&<span><i className="capacity-key"/>{text.capacity}</span>}
    </div>
  </>;
}

export default function ForecastExperience() {
  const {locale} = useLocale();
  const {status,role} = useAuth();
  const w = {...labels[locale], ...warningCopy[locale], capacity: warningCopy[locale].estimatedCapacity, updated: warningCopy[locale].dataThrough};
  const [view,setView] = useState<View>("outlook");
  const [section,setSection] = useState("");
  const [selected,setSelected] = useState<string | null>(null);
  const [riskFilter,setRiskFilter] = useState<Risk | "all">("all");
  const [shownCount,setShownCount] = useState(SHOW_STEP);
  const enabled = canFetchOfficerData(status,role);
  const filter = section ? "level=section&section="+encodeURIComponent(section) : "level=city";
  const city = usePagedApi<ApiForecastRow>(enabled ? "/forecast?level=city" : null);
  const firstMonth = city.data?.items[0]?.month;
  const names = usePagedApi<ApiForecastRow>(enabled && firstMonth ? "/forecast?level=section&month="+firstMonth : null);
  const forecasts = usePagedApi<ApiForecastRow>(enabled && section ? "/forecast?"+filter : null);
  const historyApi = usePagedApi<ApiHistoryRow>(enabled ? "/forecast/history?"+filter : null);
  const accuracyApi = usePagedApi<ApiAccuracyRow>(enabled ? "/forecast/accuracy?"+filter : null);
  const coverageApi = usePagedApi<{interval:number;coverage:number|null;months:number}>(enabled && !section ? "/forecast/backtest?row_type=city_coverage" : null);
  const window = warningWindow();
  const shortageApi = usePagedApi<ApiShortageRow>(enabled ? `/shortage?from_month=${window.from}&through_month=${window.through}` : null);
  const core = [city,names,shortageApi];
  const live = enabled && core.every(state => state.live);
  const error = core.find(state=>state.error)?.error ?? null;
  const reason = live ? null : liveReason(status,role,error);
  const savedForecast = (snapshot.forecastRows ?? []).filter(row=>section ? row.section===section : row.level==="city");
  const forecastRows = live ? (section ? forecasts.data?.items ?? [] : city.data?.items ?? []) : savedForecast;
  const historyRows = live ? historyApi.data?.items ?? [] : (snapshot.historyRows ?? []).filter(row=>section ? row.section===section : row.level==="city");
  const history:Month[] = historyRows.length ? historyRows.map(row=>({month:row.month,bookings:row.actual})) : section || live ? [] : snapshot.history;
  const accuracy = (live ? accuracyApi.data?.items ?? [] : snapshot.accuracyRows ?? []).filter(row=>(section ? row.section===section : row.level==="city") && row.point !== null && row.actual !== null).sort((a,b)=>b.month.localeCompare(a.month));
  const shortage = sortByRisk(currentWarnings(shortageFromApi(live ? shortageApi.data?.items ?? [] : snapshot.shortageRows ?? []), window));
  const outlook = outlookFromApi(forecastRows,shortage);
  const month = outlook.find(row=>row.month===selected) ?? outlook[0];
  const sections = sectionsFromForecast(live ? names.data?.items ?? [] : snapshot.forecastRows ?? []);
  const fmt = (v:number | null)=>number(v,locale);
  const updated = city.data?.items[0]?.updated_through ?? snapshot.historyEnd;
  const title = outlook.length ? fill(w.expectedTitle,{start:monthName(outlook[0].month,locale),end:monthName(outlook[outlook.length-1].month,locale)}) : w.noForecast;
  const areaState = section ? forecasts : city;
  const areaError = live ? areaState.error ?? historyApi.error : null;
  const unavailable = outlook.length===0 || outlook.every(row=>row.median===null);
  const riskNames = {all:w.riskAll,high:w.riskHigh,medium:w.riskMedium,low:w.riskLow,unknown:w.riskUnknown};
  const reasonText = (row: ReturnType<typeof shortageFromApi>[number]) => {
    if (locale === "en") return row.reason.replace(/\(A8 fleet split, ASSUMED\)/g,"(estimated capacity)");
    const copy = reasonCopy[locale];
    const parts = [row.forecast === null
      ? row.reason.includes("insufficient seasonal history") ? copy.missingHistory : copy.missingMatch
      : fill(copy.riskSummary,{expected:fmt(row.forecast),capacity:fmt(row.capacity),upper:fmt(row.upper80),risk:riskNames[row.risk]})];
    if (row.groundwater != null) {
      const sourceMonth = row.reason.slice(row.reason.indexOf("groundwater")).match(/\d{4}-\d{2}/)?.[0];
      parts.push(fill(copy.groundwaterReading,{value:fmt(Math.abs(row.groundwater)),direction:row.groundwater>=0?copy.deeper:copy.shallower,month:sourceMonth?monthName(sourceMonth,locale):"—"}));
    }
    const storage = row.reason.match(/reservoir storage \((\d{4}-\d{2})\): (.*?) \(context only\)/);
    if (storage) parts.push(fill(copy.storageReading,{month:monthName(storage[1],locale),values:storage[2].replace(/ full/g,"")}));
    return parts.join(" ");
  };
  const filtered = shortage.filter(row=>(!section || row.section===section) && (riskFilter==="all" || row.risk===riskFilter));
  const visible = filtered.slice(0,shownCount);
  const errors = accuracy.filter(row=>row.actual !== 0).map(row=>Math.abs(((row.point ?? 0)-(row.actual ?? 0))/(row.actual ?? 1))*100);
  const meanError = errors.length ? errors.reduce((a,b)=>a+b,0)/errors.length : null;
  return <div className="forecast-page">
    <header className="forecast-heading"><div><h1>{w.title}</h1><p className="muted">{w.intro}</p></div><div className="forecast-heading-tags"><DataSourceChip state={{live,loading:status==="checking" || core.some(state=>state.loading),error}}/><span>{fill(w.updated,{month:monthName(updated,locale)})}</span></div></header>
    {reason&&<p className="forecast-live-reason" role="note">{liveReasonCopy[locale][reason]}</p>}
    <label className="forecast-area">{w.area}<select value={section} onChange={event=>{setSection(event.target.value);setSelected(null);setShownCount(SHOW_STEP);}}><option value="">{w.cityTotal}</option>{sections.map(name=><option key={name} value={name}>{name}</option>)}</select></label>
    <div className="forecast-tabs" role="tablist">{(["outlook","accuracy","shortage"] as const).map(tab=><button key={tab} role="tab" aria-selected={view===tab} className={view===tab?"active":""} onClick={()=>setView(tab)}>{w[tab]}</button>)}</div>
    {view==="outlook"&&<>
      <section className="forecast-chart-panel"><h2>{title}</h2>{section&&<p>{section}</p>}<p>{w.historyNote}</p>
        {!section && (live ? coverageApi.data?.items ?? [] : snapshot.cityCoverage ?? []).filter(row=>row.coverage!==null).map(row=><p key={row.interval} className="forecast-footnote">{fill(rangeCopy[locale].rangeReliability,{level:fmt(Number(row.interval)*100),coverage:fmt(Number(row.coverage)*100),months:fmt(row.months)})}</p>)}
        {live&&areaState.loading ? <p role="status">{w.loading}</p> : areaError ? <p role="alert">{w.loadFailed}</p> : unavailable ? <p>{w.noForecast}</p> : <OutlookChart history={history} outlook={outlook} selected={month?.month ?? null} onSelect={setSelected} locale={locale} title={title} text={w}/>}
        {forecastRows.some(row=>row.match_status==="approximate")&&<p className="forecast-footnote">{w.approximate}</p>}
      </section>
      <section className="forecast-detail" aria-label={w.selectedMonthLabel}>{month&&month.median!==null ? <>
        <div><h2>{monthName(month.month,locale)}</h2>{month.capacity!==null&&month.median>month.capacity&&<p className="forecast-shortfall">{fill(w.shortBy,{count:fmt(month.median-month.capacity)})}</p>}</div>
        <div className="forecast-detail-metrics"><span>{w.median}<strong>{fmt(month.median)}</strong></span><span>{w.p80}<strong>{month.low80===null||month.high80===null ? w.rangeUnavailable : fmt(month.low80)+"–"+fmt(month.high80)}</strong></span><span>{w.p90}<strong>{month.low90===null||month.high90===null ? w.rangeUnavailable : fmt(month.low90)+"–"+fmt(month.high90)}</strong></span><span>{w.capacity}<strong>{fmt(month.capacity)}</strong></span></div>
      </> : <p>{w.noForecast}</p>}</section>
    </>}
    {view==="accuracy"&&<section className="forecast-accuracy-panel"><p>{w.accuracyNote}</p>
      {live&&accuracyApi.loading ? <p role="status">{w.loading}</p> : live&&accuracyApi.error ? <p role="alert">{w.loadFailed}</p> : accuracy.length===0 ? <p>{w.noAccuracy}</p> : <>
        {meanError!==null&&<p className="forecast-overall">{fill(w.average,{error:fmt(meanError),count:fmt(errors.length)})}</p>}
        <ol className="forecast-past-list">{accuracy.map(row=>{
          const signed = row.actual ? ((row.point ?? 0)-row.actual)/row.actual*100 : null;
          return <li key={row.month}>{signed===null ? monthName(row.month,locale)+": "+w.median+" "+fmt(row.point)+", "+w.observed+" "+fmt(row.actual) : fill(w.past,{month:monthName(row.month,locale),expected:fmt(row.point),actual:fmt(row.actual),error:fmt(Math.abs(signed)),direction:signed<0?w.low:signed>0?w.high:w.exact})}</li>;
        })}</ol>
      </>}
    </section>}
    {view==="shortage"&&<>
      <div className="forecast-notice"><p>{fill(w.warningDates,{start:monthName(window.from,locale),end:monthName(window.through,locale)})}</p><p>{w.context}</p></div>
      {updated < window.origin && <p role="note">{w.olderInputs}</p>}
      <details><summary>{detailsCopy[locale].warningHelp}</summary><p>{w.capacityHelp}</p><p>{w.unknownHelp}</p></details>
      {shortage.some(row=>row.groundwaterUnavailable)&&<p>{w.waterUnavailable}</p>}
      <div className="risk-filter" role="group" aria-label={w.filterLabel}>{(["all",...RISK_ORDER] as const).map(value=><button key={value} type="button" aria-pressed={riskFilter===value} onClick={()=>{setRiskFilter(value);setShownCount(SHOW_STEP);}}>{riskNames[value]} ({shortage.filter(row=>(!section||row.section===section)&&(value==="all"||row.risk===value)).length})</button>)}</div>
      {visible.length===0 ? <p>{w.noRisk}</p> : <ol className="shortage-list" aria-label={w.riskListLabel}>{visible.map(row=><li key={row.key} className={"shortage-item risk-"+row.risk}>
        <div className="shortage-item-head"><span className={"risk-pill risk-"+row.risk}>{riskNames[row.risk]}</span><h3>{row.section}</h3><span>{monthName(row.month,locale)} · {fill(w.ahead,{count:fmt(row.monthsAhead)})}</span></div>
        <dl className="shortage-figures"><div><dt>{w.median}</dt><dd>{fmt(row.forecast)}</dd></div><div><dt>{w.p80}</dt><dd>{fmt(row.upper80)}</dd></div><div><dt>{w.capacity}</dt><dd>{fmt(row.capacity)}</dd></div></dl>
        <p className="shortage-reason">{reasonText(row)}</p>
      </li>)}</ol>}
      <div className="shortage-more"><span>{fill(w.showing,{shown:fmt(visible.length),total:fmt(filtered.length)})}</span>{visible.length<filtered.length&&<button onClick={()=>setShownCount(n=>n+SHOW_STEP)}>{w.showMore}</button>}</div>
      <p className="forecast-footnote">{w.context}</p>
    </>}
  </div>;
}
