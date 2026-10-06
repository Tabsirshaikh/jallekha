import { useState } from "react";
import { useAuth } from "./auth";
import DataSourceChip from "./DataSource";
import { useLocale, type Locale } from "./i18n";
import data from "./data/u6Forecast.json";
import {
  outlookFromApi,
  outlookFromFixture,
  RISK_ORDER,
  sectionsFromForecast,
  shortageFromApi,
  sortByRisk,
  summarizeBacktest,
  type ApiBacktestRow,
  type ApiForecastRow,
  type ApiPage,
  type ApiShortageRow,
  type FixtureMonth,
  type OutlookMonth,
  type Risk,
} from "./forecastAdapter";
import { canFetchOfficerData, liveReason, liveReasonCopy } from "./liveReason";
import { useApi } from "./useApi";
import "./ForecastExperience.css";

type View = "outlook" | "accuracy" | "shortage";
type Month = { month: string; bookings: number | null; delivered: number | null; basis: "REAL" | "UNAVAILABLE" };
type ForecastMonth = FixtureMonth & { basis: "SIMULATION" };
const snapshot = data as {
  snapshotDate: string; historyStart: string; historyEnd: string; history: Month[]; forecast: ForecastMonth[];
  baseline: { cityMapePct: number; sectionWapePct: number; basis: string; protocolStatus: string };
  summary: { observedMonthCount: number; missingMonths: string[]; latest: Month; peak: Month };
  groundwater: { basis: string; reason: string };
};
const labels = {
  en: { title:"Demand forecast & shortage", intro:"Compare observed tanker-booking demand with an illustrative outlook and capacity scenarios.", outlook:"Demand outlook", accuracy:"Accuracy vs baseline", shortage:"Shortage warnings", latest:"Latest observed month", peak:"Peak observed month", bookings:"Bookings", delivered:"Delivered", deliveryRate:"Delivered / booked", observed:"Observed", forecast:"Illustrative forecast", dateRange:"Monthly bookings · HMWSSB records", sim:"SIMULATION", real:"REAL", derived:"DERIVED", historyGap:"December 2022 has no source rows; it is shown as missing, not zero.", fixtureNote:"Forecast values and ranges are demonstration fixtures. They are not T2 model output or operational advice.", p80:"80% demo range", p90:"90% demo range", median:"Demo median", capacity:"Assumed demo capacity", available:"Available", benchmark:"Published seasonal-naive benchmark", cityMape:"City MAPE", sectionWape:"Section WAPE", noCandidate:"No candidate forecast is available for a verified comparison yet.", protocol:"Backtest protocol", undocumented:"Not documented in this repository", status:"Model status", pending:"T2 implementation pending", notLive:"No live forecast API connected", range:"Forecast range", riskList:"Months to watch", risk:"Watch", gap:"Median above demo capacity", overlap:"Intervals still overlap capacity; this is a watch signal only.", groundwater:"Groundwater signal", unavailable:"Unavailable", groundwaterNote:"Live data gives groundwater near each section; this saved sample has none.", reservoir:"Reservoir levels", reservoirNote:"Not included; no verified machine-readable source is available.", capacityNote:"Capacity is a synthetic illustration. Trips per tanker per day and current fleet capacity are unverified.", rationale:"Why this appears", dataPeriod:"Observed data", source:"HMWSSB monthly section records summed to city totals", sourceEnd:"Latest available source month", basis:"Basis", noRecords:"No records", noRisk:"No fixture month exceeds the assumed demo capacity.", compareTitle:"Baseline benchmark only", from:"From", to:"to", months:"months", generated:"Snapshot generated", labelLimit:"REAL history · DERIVED benchmark · SIMULATION outlook", },
  te: { title:"డిమాండ్ అంచనా మరియు కొరత", intro:"గమనించిన ట్యాంకర్ బుకింగ్‌లను ఉదాహరణ అంచనా మరియు సామర్థ్య దృశ్యాలతో పోల్చండి.", outlook:"డిమాండ్ అంచనా", accuracy:"ప్రమాణంతో ఖచ్చితత్వం", shortage:"కొరత హెచ్చరికలు", latest:"తాజా గమనించిన నెల", peak:"గరిష్ఠ గమనించిన నెల", bookings:"బుకింగ్‌లు", delivered:"పంపిణీ", deliveryRate:"పంపిణీ / బుకింగ్‌లు", observed:"గమనించినవి", forecast:"ఉదాహరణ అంచనా", dateRange:"నెలవారీ బుకింగ్‌లు · HMWSSB రికార్డులు", sim:"అనుకరణ", real:"నిజమైనవి", derived:"ఉత్పన్నం", historyGap:"డిసెంబర్ 2022లో మూల రికార్డులు లేవు; సున్నాగా కాకుండా అందుబాటులో లేనిదిగా చూపించాం.", fixtureNote:"అంచనా విలువలు, పరిధులు ప్రదర్శన కోసం మాత్రమే. ఇవి T2 నమూనా ఫలితాలు లేదా కార్యాచరణ సలహా కావు.", p80:"80% ఉదాహరణ పరిధి", p90:"90% ఉదాహరణ పరిధి", median:"ఉదాహరణ మధ్యకం", capacity:"అనుకున్న ఉదాహరణ సామర్థ్యం", available:"అందుబాటులో", benchmark:"ప్రచురిత seasonal-naive ప్రమాణం", cityMape:"నగర MAPE", sectionWape:"సెక్షన్ WAPE", noCandidate:"ధృవీకరించిన పోలికకు నమూనా అంచనా ఇంకా లేదు.", protocol:"బ్యాక్‌టెస్ట్ విధానం", undocumented:"ఈ రిపాజిటరీలో నమోదు కాలేదు", status:"నమూనా స్థితి", pending:"T2 అమలు పెండింగ్‌లో ఉంది", notLive:"ప్రత్యక్ష అంచనా API లేదు", range:"అంచనా పరిధి", riskList:"గమనించాల్సిన నెలలు", risk:"గమనించండి", gap:"మధ్యకం ఉదాహరణ సామర్థ్యాన్ని మించింది", overlap:"పరిధులు సామర్థ్యంతో ఇంకా అతివ్యాప్తి చెందుతున్నాయి; ఇది గమనిక మాత్రమే.", groundwater:"భూగర్భజల సూచిక", unavailable:"అందుబాటులో లేదు", groundwaterNote:"ప్రత్యక్ష డేటాలో ప్రతి సెక్షన్ సమీపంలోని భూగర్భజలం ఉంటుంది; ఈ సేవ్ చేసిన నమూనాలో లేదు.", reservoir:"జలాశయ స్థాయిలు", reservoirNote:"ధృవీకరించిన యంత్ర-చదవగల మూలం లేక చేర్చలేదు.", capacityNote:"సామర్థ్యం సింథటిక్ ఉదాహరణ మాత్రమే. ట్యాంకర్ రోజువారీ ప్రయాణాలు, ప్రస్తుత వాహన సామర్థ్యం నిర్ధారించలేదు.", rationale:"ఈ సూచనకు కారణం", dataPeriod:"గమనించిన డేటా", source:"HMWSSB నెలవారీ సెక్షన్ రికార్డుల నగర మొత్తం", sourceEnd:"తాజా అందుబాటు మూల నెల", basis:"ఆధారం", noRecords:"రికార్డులు లేవు", noRisk:"ఈ ఉదాహరణ నెలల్లో ఏదీ అనుకున్న సామర్థ్యాన్ని మించలేదు.", compareTitle:"ప్రమాణ బెంచ్‌మార్క్ మాత్రమే", from:"నుంచి", to:"వరకు", months:"నెలలు", generated:"నమూనా రూపొందిన తేదీ", labelLimit:"నిజమైన చరిత్ర · ఉత్పన్న ప్రమాణం · అనుకరణ అంచనా" },
  ur: { title:"طلب کی پیش گوئی اور قلت", intro:"درج شدہ ٹینکر بکنگ کا تقابل ایک نمائشی پیش گوئی اور گنجائش کے منظرناموں سے کریں۔", outlook:"طلب کا رجحان", accuracy:"بنیادی معیار سے موازنہ", shortage:"قلت کی تنبیہ", latest:"تازہ درج شدہ مہینہ", peak:"سب سے زیادہ درج مہینہ", bookings:"بکنگ", delivered:"پہنچایا گیا", deliveryRate:"پہنچایا / بک کیا", observed:"درج شدہ", forecast:"نمائشی پیش گوئی", dateRange:"ماہانہ بکنگ · HMWSSB ریکارڈ", sim:"تخمینی", real:"اصل", derived:"اخذ شدہ", historyGap:"دسمبر 2022 کا ریکارڈ نہیں؛ اسے صفر کے بجائے غیر دستیاب دکھایا گیا ہے۔", fixtureNote:"پیش گوئی اور حدود صرف مظاہرے کے لیے ہیں۔ یہ T2 ماڈل کا نتیجہ یا عملی مشورہ نہیں۔", p80:"80% نمائشی حد", p90:"90% نمائشی حد", median:"نمائشی درمیانی قدر", capacity:"فرضی نمائشی گنجائش", available:"دستیاب", benchmark:"شائع شدہ موسمی بنیادی معیار", cityMape:"شہر MAPE", sectionWape:"سیکشن WAPE", noCandidate:"تصدیق شدہ موازنے کے لیے ابھی کوئی متبادل پیش گوئی موجود نہیں۔", protocol:"بیک ٹیسٹ طریقہ", undocumented:"اس ریپوزٹری میں درج نہیں", status:"ماڈل کی حالت", pending:"T2 کی تکمیل باقی ہے", notLive:"براہ راست پیش گوئی API منسلک نہیں", range:"پیش گوئی کی حد", riskList:"جن مہینوں پر نظر رکھیں", risk:"نظر رکھیں", gap:"درمیانی قدر نمائشی گنجائش سے زیادہ", overlap:"حدود گنجائش سے متداخل ہیں؛ یہ صرف نگرانی کا اشارہ ہے۔", groundwater:"زیرِ زمین پانی کا اشارہ", unavailable:"دستیاب نہیں", groundwaterNote:"براہِ راست ڈیٹا میں ہر سیکشن کے قریب زیرِ زمین پانی موجود ہے؛ اس محفوظ نمونے میں نہیں۔", reservoir:"ذخیرے کی سطح", reservoirNote:"تصدیق شدہ مشینی ماخذ موجود نہ ہونے کے باعث شامل نہیں۔", capacityNote:"گنجائش صرف مصنوعی مثال ہے۔ روزانہ ٹینکر چکر اور موجودہ بیڑے کی صلاحیت غیر مصدقہ ہے۔", rationale:"اس اشارے کی وجہ", dataPeriod:"درج شدہ ڈیٹا", source:"HMWSSB کے ماہانہ سیکشن ریکارڈ کا مجموعہ", sourceEnd:"تازہ دستیاب ماخذ کا مہینہ", basis:"بنیاد", noRecords:"کوئی ریکارڈ نہیں", noRisk:"نمائشی گنجائش سے زیادہ کوئی مثال والا مہینہ نہیں۔", compareTitle:"صرف بنیادی معیار", from:"سے", to:"تک", months:"مہینے", generated:"جھلک کی تاریخ", labelLimit:"اصل تاریخ · اخذ شدہ معیار · تخمینی پیش گوئی" },
  hi: { title:"माँग का पूर्वानुमान और कमी", intro:"दर्ज टैंकर बुकिंग की तुलना उदाहरण पूर्वानुमान और क्षमता परिदृश्यों से करें।", outlook:"माँग का रुझान", accuracy:"आधार से सटीकता", shortage:"कमी की चेतावनी", latest:"नवीनतम दर्ज महीना", peak:"सबसे अधिक दर्ज महीना", bookings:"बुकिंग", delivered:"पहुंचाया", deliveryRate:"पहुंचाया / बुकिंग", observed:"दर्ज", forecast:"उदाहरण पूर्वानुमान", dateRange:"मासिक बुकिंग · HMWSSB रिकॉर्ड", sim:"सिमुलेशन", real:"वास्तविक", derived:"व्युत्पन्न", historyGap:"दिसंबर 2022 के स्रोत रिकॉर्ड नहीं हैं; इसे शून्य के बजाय अनुपलब्ध दिखाया गया है।", fixtureNote:"पूर्वानुमान और रेंज केवल प्रदर्शन के लिए हैं। ये T2 मॉडल आउटपुट या संचालन सलाह नहीं हैं।", p80:"80% उदाहरण रेंज", p90:"90% उदाहरण रेंज", median:"उदाहरण मध्य मान", capacity:"मानी गई उदाहरण क्षमता", available:"उपलब्ध", benchmark:"प्रकाशित seasonal-naive आधार", cityMape:"शहर MAPE", sectionWape:"सेक्शन WAPE", noCandidate:"सत्यापित तुलना के लिए अभी कोई वैकल्पिक पूर्वानुमान उपलब्ध नहीं।", protocol:"बैकटेस्ट विधि", undocumented:"इस रिपॉज़िटरी में दर्ज नहीं", status:"मॉडल स्थिति", pending:"T2 कार्य लंबित है", notLive:"लाइव पूर्वानुमान API नहीं जुड़ी", range:"पूर्वानुमान रेंज", riskList:"नज़र रखने वाले महीने", risk:"नज़र रखें", gap:"मध्य मान उदाहरण क्षमता से अधिक", overlap:"रेंज क्षमता के साथ ओवरलैप करती है; यह सिर्फ निगरानी संकेत है।", groundwater:"भूजल संकेत", unavailable:"उपलब्ध नहीं", groundwaterNote:"लाइव डेटा में हर सेक्शन के पास भूजल है; इस सहेजे नमूने में नहीं।", reservoir:"जलाशय स्तर", reservoirNote:"सत्यापित मशीन-पठनीय स्रोत न होने से शामिल नहीं।", capacityNote:"क्षमता सिर्फ सिंथेटिक उदाहरण है। प्रति टैंकर दैनिक चक्कर और मौजूदा बेड़ा क्षमता सत्यापित नहीं।", rationale:"यह संकेत क्यों है", dataPeriod:"दर्ज डेटा", source:"HMWSSB मासिक सेक्शन रिकॉर्ड का शहर योग", sourceEnd:"नवीनतम उपलब्ध स्रोत महीना", basis:"आधार", noRecords:"रिकॉर्ड नहीं", noRisk:"कोई उदाहरण महीना मानी क्षमता से अधिक नहीं।", compareTitle:"सिर्फ आधार बेंचमार्क", from:"से", to:"तक", months:"महीने", generated:"स्नैपशॉट बनाया", labelLimit:"वास्तविक इतिहास · व्युत्पन्न आधार · सिमुलेशन पूर्वानुमान" },
} satisfies Record<Locale, Record<string,string>>;

// Words for the live T2 / T8 view (and a corrected fallback status); merged over `labels` above.
const liveLabels = {
  en: { pending:"Live T2 forecast not loaded", area:"Area", cityTotal:"City total", selectedMonthLabel:"Selected forecast month", labelLimitLive:"REAL history · DERIVED forecast · ASSUMED capacity", liveForecast:"T2 forecast", medianLive:"Forecast (point)", p80Live:"80% interval", p90Live:"90% interval", capacityLive:"Assumed capacity", liveStatus:"Seasonal-naive baseline", liveStatusNote:"No tested model beats this baseline", liveNotice:"Forecast from the live T2 API: a seasonal-naive baseline, because no tested model beats it. Observed history is the committed HMWSSB snapshot.", sectionNote:"Section history is not in this screen; the chart shows this section's forecast only.", sectionsRecut:"Sections are named as before the Feb/Mar 2026 re-cut, so they do not match current HMWSSB sections one to one.", rangeUnavailable:"Range unavailable", loadingSection:"Loading this section's forecast…", sectionLoadFailed:"This section's forecast could not be loaded.", noSectionRows:"No forecast rows for this section.", liveAccuracyTitle:"Backtest: models against the seasonal-naive baseline", comparedOn:"Compared on the forecast origins every model shares", runLabel:"Backtest run", modelLabel:"Model", selectedModel:"Selected model", notRun:"Not run", baselineTag:"baseline", protocolLive:"Rolling-origin backtest; each model is trained only on months before its origin.", shortageLiveTitle:"Shortage risk, 1–3 months ahead", shortageLiveNote:"DERIVED forecast against ASSUMED capacity (A8 fleet split). These are watch signals, not orders.", groundwaterLive:"Groundwater data unavailable: warnings compare the forecast with assumed capacity only.", groundwaterLiveDerived:"Groundwater (Telangana Ground Water Department wells): each reason gives the level near the section against the same month in earlier years. It is shown, not used to set the risk.", groundwaterDerivedNote:"Well levels near each section, against the same month in earlier years (DERIVED from REAL readings); not part of the risk rule.", riskListLabel:"Shortage risk list", filterLabel:"Filter by risk", riskAll:"All", riskHigh:"High", riskMedium:"Medium", riskLow:"Low", riskUnknown:"Unknown", aheadOne:"month ahead", aheadMany:"months ahead", forecastBookings:"Forecast bookings", upper80:"80% upper bound", capacityTrips:"Assumed capacity (trips)", ofCapacity:"of capacity", showingCount:"Showing {shown} of {total}", showMore:"Show more", partial:"Only part of the list could be loaded:", shortageEmpty:"No rows at this risk level.", capacityLiveNote:"Capacity is ASSUMED: the A8 fleet scenario split across sections by their share of station bookings; trips per tanker per day are not verified." },
  te: { pending:"ప్రత్యక్ష T2 అంచనా లోడ్ కాలేదు", area:"ప్రాంతం", cityTotal:"నగర మొత్తం", selectedMonthLabel:"ఎంచుకున్న అంచనా నెల", labelLimitLive:"నిజమైన చరిత్ర · ఉత్పన్న అంచనా · అనుకున్న సామర్థ్యం", liveForecast:"T2 అంచనా", medianLive:"అంచనా (బిందువు)", p80Live:"80% పరిధి", p90Live:"90% పరిధి", capacityLive:"అనుకున్న సామర్థ్యం", liveStatus:"Seasonal-naive ప్రమాణం", liveStatusNote:"పరీక్షించిన ఏ నమూనా ఈ ప్రమాణాన్ని మించలేదు", liveNotice:"ప్రత్యక్ష T2 API నుంచి అంచనా: పరీక్షించిన ఏ నమూనా మించనందున seasonal-naive ప్రమాణం. గమనించిన చరిత్ర సేవ్ చేసిన HMWSSB నమూనా.", sectionNote:"సెక్షన్ చరిత్ర ఈ స్క్రీన్‌లో లేదు; చార్ట్ ఈ సెక్షన్ అంచనాను మాత్రమే చూపిస్తుంది.", sectionsRecut:"సెక్షన్ పేర్లు ఫిబ్రవరి/మార్చి 2026 పునర్విభజనకు ముందువి; ప్రస్తుత HMWSSB సెక్షన్లతో ఒకటికొకటి సరిపోలవు.", rangeUnavailable:"పరిధి అందుబాటులో లేదు", loadingSection:"ఈ సెక్షన్ అంచనా లోడ్ అవుతోంది…", sectionLoadFailed:"ఈ సెక్షన్ అంచనాను లోడ్ చేయలేకపోయాం.", noSectionRows:"ఈ సెక్షన్‌కు అంచనా వరుసలు లేవు.", liveAccuracyTitle:"బ్యాక్‌టెస్ట్: seasonal-naive ప్రమాణంతో నమూనాలు", comparedOn:"అన్ని నమూనాలకు ఉమ్మడి ప్రారంభ నెలలపై పోలిక", runLabel:"బ్యాక్‌టెస్ట్ రన్", modelLabel:"నమూనా", selectedModel:"ఎంచుకున్న నమూనా", notRun:"అమలు చేయలేదు", baselineTag:"ప్రమాణం", protocolLive:"రోలింగ్-ఆరిజిన్ బ్యాక్‌టెస్ట్; ప్రతి నమూనా తన ప్రారంభ నెలకు ముందు నెలలపై మాత్రమే శిక్షణ పొందుతుంది.", shortageLiveTitle:"రాబోయే 1–3 నెలల కొరత ప్రమాదం", shortageLiveNote:"ఉత్పన్న అంచనాను అనుకున్న సామర్థ్యంతో (A8 వాహన విభజన) పోల్చాం. ఇవి గమనిక సూచనలు, ఆదేశాలు కావు.", groundwaterLive:"భూగర్భజల డేటా అందుబాటులో లేదు: హెచ్చరికలు అంచనాను అనుకున్న సామర్థ్యంతో మాత్రమే పోలుస్తాయి.", groundwaterLiveDerived:"భూగర్భజలం (తెలంగాణ భూగర్భజల శాఖ బావులు): ప్రతి కారణం ఆ సెక్షన్ సమీపంలోని నీటి మట్టాన్ని గత సంవత్సరాల అదే నెలతో పోలుస్తుంది. ఇది చూపించడానికి మాత్రమే, ప్రమాద స్థాయిని నిర్ణయించదు.", groundwaterDerivedNote:"ప్రతి సెక్షన్ సమీపంలోని బావుల నీటి మట్టం, గత సంవత్సరాల అదే నెలతో పోలిక (నిజమైన కొలతల నుంచి ఉత్పన్నం); ప్రమాద నియమంలో భాగం కాదు.", riskListLabel:"కొరత ప్రమాద జాబితా", filterLabel:"ప్రమాదం ప్రకారం వడపోత", riskAll:"అన్నీ", riskHigh:"ఎక్కువ", riskMedium:"మధ్యస్థం", riskLow:"తక్కువ", riskUnknown:"తెలియదు", aheadOne:"నెల ముందు", aheadMany:"నెలలు ముందు", forecastBookings:"అంచనా బుకింగ్‌లు", upper80:"80% గరిష్ఠ పరిమితి", capacityTrips:"అనుకున్న సామర్థ్యం (ప్రయాణాలు)", ofCapacity:"సామర్థ్యంలో", showingCount:"{total}లో {shown} చూపిస్తున్నాం", showMore:"మరిన్ని చూపించు", partial:"జాబితాలో కొంత భాగం మాత్రమే లోడ్ అయింది:", shortageEmpty:"ఈ ప్రమాద స్థాయిలో వరుసలు లేవు.", capacityLiveNote:"సామర్థ్యం అనుకున్నది: A8 వాహన దృశ్యాన్ని స్టేషన్ బుకింగ్ వాటా ప్రకారం సెక్షన్లకు విభజించాం; ట్యాంకర్ రోజువారీ ప్రయాణాలు నిర్ధారించలేదు." },
  ur: { pending:"براہِ راست T2 پیش گوئی لوڈ نہیں ہوئی", area:"علاقہ", cityTotal:"شہر کا مجموعہ", selectedMonthLabel:"منتخب پیش گوئی کا مہینہ", labelLimitLive:"اصل تاریخ · اخذ شدہ پیش گوئی · فرضی گنجائش", liveForecast:"T2 پیش گوئی", medianLive:"پیش گوئی (نقطہ)", p80Live:"80% حد", p90Live:"90% حد", capacityLive:"فرضی گنجائش", liveStatus:"موسمی بنیادی معیار (seasonal-naive)", liveStatusNote:"کوئی آزمودہ ماڈل اس معیار سے بہتر نہیں", liveNotice:"براہِ راست T2 API سے پیش گوئی: موسمی بنیادی معیار، کیونکہ کوئی آزمودہ ماڈل اس سے بہتر نہیں۔ درج شدہ تاریخ محفوظ شدہ HMWSSB نمونہ ہے۔", sectionNote:"سیکشن کی تاریخ اس صفحے پر نہیں؛ چارٹ صرف اس سیکشن کی پیش گوئی دکھاتا ہے۔", sectionsRecut:"سیکشن کے نام فروری/مارچ 2026 کی نئی تقسیم سے پہلے کے ہیں، اس لیے موجودہ HMWSSB سیکشنز سے ایک ایک کر کے نہیں ملتے۔", rangeUnavailable:"حد دستیاب نہیں", loadingSection:"اس سیکشن کی پیش گوئی لوڈ ہو رہی ہے…", sectionLoadFailed:"اس سیکشن کی پیش گوئی لوڈ نہیں ہو سکی۔", noSectionRows:"اس سیکشن کے لیے پیش گوئی کی قطاریں نہیں۔", liveAccuracyTitle:"بیک ٹیسٹ: ماڈل بمقابلہ موسمی بنیادی معیار", comparedOn:"ان آغازی مہینوں پر موازنہ جو ہر ماڈل میں مشترک ہیں", runLabel:"بیک ٹیسٹ رن", modelLabel:"ماڈل", selectedModel:"منتخب ماڈل", notRun:"نہیں چلایا گیا", baselineTag:"بنیادی معیار", protocolLive:"رولنگ اوریجن بیک ٹیسٹ؛ ہر ماڈل صرف اپنے آغاز سے پہلے کے مہینوں پر تربیت پاتا ہے۔", shortageLiveTitle:"آئندہ 1–3 مہینوں میں قلت کا خطرہ", shortageLiveNote:"اخذ شدہ پیش گوئی کا فرضی گنجائش (A8 بیڑے کی تقسیم) سے موازنہ۔ یہ نگرانی کے اشارے ہیں، احکامات نہیں۔", groundwaterLive:"زیرِ زمین پانی کا ڈیٹا دستیاب نہیں: تنبیہات صرف پیش گوئی کا فرضی گنجائش سے موازنہ کرتی ہیں۔", groundwaterLiveDerived:"زیرِ زمین پانی (تلنگانہ محکمۂ زیرِ زمین آب کے کنویں): ہر وجہ سیکشن کے قریب پانی کی سطح کا گزشتہ برسوں کے اسی مہینے سے موازنہ دیتی ہے۔ یہ صرف دکھایا جاتا ہے، خطرے کی سطح طے نہیں کرتا۔", groundwaterDerivedNote:"ہر سیکشن کے قریب کنوؤں میں پانی کی سطح، گزشتہ برسوں کے اسی مہینے کے مقابلے میں (حقیقی پیمائش سے اخذ شدہ)؛ خطرے کے اصول کا حصہ نہیں۔", riskListLabel:"قلت کے خطرے کی فہرست", filterLabel:"خطرے کے لحاظ سے چھانٹیں", riskAll:"سب", riskHigh:"زیادہ", riskMedium:"درمیانہ", riskLow:"کم", riskUnknown:"نامعلوم", aheadOne:"مہینہ آگے", aheadMany:"مہینے آگے", forecastBookings:"متوقع بکنگ", upper80:"80% بالائی حد", capacityTrips:"فرضی گنجائش (چکر)", ofCapacity:"گنجائش کا", showingCount:"{total} میں سے {shown} دکھائے گئے", showMore:"مزید دکھائیں", partial:"فہرست کا صرف کچھ حصہ لوڈ ہو سکا:", shortageEmpty:"اس خطرے کی سطح پر کوئی قطار نہیں۔", capacityLiveNote:"گنجائش فرضی ہے: A8 بیڑے کا منظرنامہ اسٹیشن بکنگ کے حصے کے مطابق سیکشنز میں تقسیم؛ روزانہ ٹینکر چکر غیر مصدقہ ہیں۔" },
  hi: { pending:"लाइव T2 पूर्वानुमान लोड नहीं हुआ", area:"क्षेत्र", cityTotal:"शहर का योग", selectedMonthLabel:"चुना गया पूर्वानुमान महीना", labelLimitLive:"वास्तविक इतिहास · व्युत्पन्न पूर्वानुमान · मानी गई क्षमता", liveForecast:"T2 पूर्वानुमान", medianLive:"पूर्वानुमान (बिंदु)", p80Live:"80% अंतराल", p90Live:"90% अंतराल", capacityLive:"मानी गई क्षमता", liveStatus:"Seasonal-naive आधार", liveStatusNote:"कोई परखा गया मॉडल इस आधार से बेहतर नहीं", liveNotice:"लाइव T2 API से पूर्वानुमान: seasonal-naive आधार, क्योंकि कोई परखा गया मॉडल इससे बेहतर नहीं। दर्ज इतिहास सहेजा हुआ HMWSSB स्नैपशॉट है।", sectionNote:"सेक्शन का इतिहास इस स्क्रीन में नहीं है; चार्ट सिर्फ इस सेक्शन का पूर्वानुमान दिखाता है।", sectionsRecut:"सेक्शन के नाम फ़रवरी/मार्च 2026 के पुनर्विभाजन से पहले के हैं, इसलिए वे मौजूदा HMWSSB सेक्शन से एक-एक करके मेल नहीं खाते।", rangeUnavailable:"रेंज उपलब्ध नहीं", loadingSection:"इस सेक्शन का पूर्वानुमान लोड हो रहा है…", sectionLoadFailed:"इस सेक्शन का पूर्वानुमान लोड नहीं हो सका।", noSectionRows:"इस सेक्शन के लिए पूर्वानुमान पंक्तियाँ नहीं हैं।", liveAccuracyTitle:"बैकटेस्ट: seasonal-naive आधार के मुकाबले मॉडल", comparedOn:"उन शुरुआती महीनों पर तुलना जो हर मॉडल में साझा हैं", runLabel:"बैकटेस्ट रन", modelLabel:"मॉडल", selectedModel:"चुना गया मॉडल", notRun:"नहीं चलाया गया", baselineTag:"आधार", protocolLive:"रोलिंग-ओरिजिन बैकटेस्ट; हर मॉडल सिर्फ अपने शुरुआती महीने से पहले के महीनों पर प्रशिक्षित होता है।", shortageLiveTitle:"अगले 1–3 महीनों में कमी का जोखिम", shortageLiveNote:"व्युत्पन्न पूर्वानुमान की तुलना मानी गई क्षमता (A8 बेड़ा विभाजन) से। ये निगरानी संकेत हैं, आदेश नहीं।", groundwaterLive:"भूजल डेटा उपलब्ध नहीं: चेतावनियाँ सिर्फ पूर्वानुमान की तुलना मानी गई क्षमता से करती हैं।", groundwaterLiveDerived:"भूजल (तेलंगाना भूजल विभाग के कुएँ): हर कारण सेक्शन के पास जल स्तर की तुलना पिछले वर्षों के उसी महीने से देता है। यह सिर्फ दिखाया जाता है, जोखिम स्तर तय नहीं करता।", groundwaterDerivedNote:"हर सेक्शन के पास कुओं का जल स्तर, पिछले वर्षों के उसी महीने की तुलना में (असली माप से व्युत्पन्न); जोखिम नियम का हिस्सा नहीं।", riskListLabel:"कमी जोखिम सूची", filterLabel:"जोखिम के अनुसार छाँटें", riskAll:"सभी", riskHigh:"उच्च", riskMedium:"मध्यम", riskLow:"कम", riskUnknown:"अज्ञात", aheadOne:"महीना आगे", aheadMany:"महीने आगे", forecastBookings:"अनुमानित बुकिंग", upper80:"80% ऊपरी सीमा", capacityTrips:"मानी गई क्षमता (चक्कर)", ofCapacity:"क्षमता का", showingCount:"{total} में से {shown} दिखाए गए", showMore:"और दिखाएँ", partial:"सूची का केवल कुछ हिस्सा लोड हो सका:", shortageEmpty:"इस जोखिम स्तर पर कोई पंक्ति नहीं।", capacityLiveNote:"क्षमता मानी गई है: A8 बेड़ा परिदृश्य को स्टेशन बुकिंग हिस्से के अनुसार सेक्शनों में बाँटा; प्रति टैंकर दैनिक चक्कर सत्यापित नहीं।" },
} satisfies Record<Locale, Record<string,string>>;

type Words = (typeof labels)[Locale] & (typeof liveLabels)[Locale];

/** T10 lists page at 200 rows; T8's list (551 rows today) is read in up to three pages and then sorted. */
const PAGE = 200;
const SHOW_STEP = 20;
const riskWord: Record<Risk, "riskHigh"|"riskMedium"|"riskLow"|"riskUnknown"> = { high:"riskHigh", medium:"riskMedium", low:"riskLow", unknown:"riskUnknown" };

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

type ChartProps = { history: Month[]; outlook: OutlookMonth[]; selected: string | null; onSelect: (month: string) => void; locale: Locale; title: string; text: { median: string; p80: string; p90: string; capacity: string; observed: string } };

/** History (REAL) and forecast on one month axis, so a live forecast that overlaps observed months sits over them. */
function OutlookChart({ history, outlook, selected, onSelect, locale, title, text }: ChartProps) {
  const fmt = (v: number | null) => number(v, locale);
  const [hoverMonth, setHoverMonth] = useState<string | null>(null);
  const shown = history.filter((row) => row.month);
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
    ? [...months.filter((m) => m.endsWith("-01")).map((m) => ({ month: m, label: m.slice(0,4) })), ...outlook.filter((row) => row.month > historyEnd).map((row) => ({ month: row.month, label: monthName(row.month, locale).split(" ")[0] }))]
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
      {outlook.filter((row)=>row.median!==null).map((row)=><g key={row.month} className="forecast-point" tabIndex={0} role="button" aria-label={monthName(row.month,locale)+": "+text.median+" "+fmt(row.median)} onClick={()=>onSelect(row.month)} onKeyDown={(event)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();onSelect(row.month);}}}><circle cx={x(row.month)} cy={y(row.median ?? 0)} r={selected===row.month?7:5}/><title>{monthName(row.month,locale)} · {fmt(row.median)}</title></g>)}
      {labels.map((item)=><text key={item.month+item.label} x={x(item.month)} y={height-12} textAnchor="middle">{item.label}</text>)}
      {hoverMonth&&<line x1={x(hoverMonth)} x2={x(hoverMonth)} y1={top} y2={y(0)} className="chart-hover-line"/>}
      {months.map((m)=><rect key={"h"+m} x={x(m)-(width-left-right)/Math.max(months.length-1,1)/2} y={top} width={(width-left-right)/Math.max(months.length-1,1)} height={y(0)-top} fill="transparent" onMouseEnter={()=>setHoverMonth(m)}/>)}
    </svg>
    {hoverMonth&&(()=>{ const h = shown.find((row)=>row.month===hoverMonth); const o = outlook.find((row)=>row.month===hoverMonth); const pos = x(hoverMonth)/width*100;
      return <div className="chart-tooltip" style={{ left: `${pos}%`, transform: pos > 60 ? "translateX(-105%)" : "translateX(5%)" }}><strong>{monthName(hoverMonth, locale)}</strong>
        {h&&h.bookings!==null&&<span><i className="history-key"/>{text.observed}: {fmt(h.bookings)}</span>}
        {o&&o.median!==null&&<span><i className="median-key"/>{text.median}: {fmt(o.median)}</span>}
        {o&&o.capacity!==null&&<span><i className="capacity-key"/>{text.capacity}: {fmt(o.capacity)}</span>}
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
  const { locale } = useLocale();
  const { status, role } = useAuth();
  const w: Words = { ...labels[locale], ...liveLabels[locale] };
  const [view,setView] = useState<View>("outlook");
  const [selected,setSelected] = useState<string | null>(null);
  const [section,setSection] = useState("");
  const [riskFilter,setRiskFilter] = useState<Risk | "all">("all");
  const [shownCount,setShownCount] = useState(SHOW_STEP);

  // Live: T2 city forecast, backtest, section names and T8's shortage list, asked only for a signed-in officer.
  const enabled = canFetchOfficerData(status, role);
  const city = useApi<ApiPage<ApiForecastRow>>(enabled ? `/forecast?level=city&limit=${PAGE}` : null);
  const backtest = useApi<ApiPage<ApiBacktestRow>>(enabled ? `/forecast/backtest?limit=${PAGE}` : null);
  const firstMonth = city.data?.items.map((row)=>row.month).sort()[0];
  const sectionNames = useApi<ApiPage<ApiForecastRow>>(enabled && city.live ? `/forecast?level=section&limit=${PAGE}${firstMonth ? `&month=${firstMonth}` : ""}` : null);
  const shortage1 = useApi<ApiPage<ApiShortageRow>>(enabled ? `/shortage?limit=${PAGE}` : null);
  const shortageTotal = shortage1.data?.total ?? 0;
  const shortage2 = useApi<ApiPage<ApiShortageRow>>(enabled && shortageTotal > PAGE ? `/shortage?offset=${PAGE}&limit=${PAGE}` : null);
  const shortage3 = useApi<ApiPage<ApiShortageRow>>(enabled && shortageTotal > 2*PAGE ? `/shortage?offset=${2*PAGE}&limit=${PAGE}` : null);
  const shortagePages = [shortage1, ...(shortageTotal > PAGE ? [shortage2] : []), ...(shortageTotal > 2*PAGE ? [shortage3] : [])];
  const core = [city, backtest, sectionNames, ...shortagePages];
  // The screen is live only when every part is; otherwise every panel shows the labelled snapshot.
  const live = enabled && core.every((state) => state.live);
  const error = core.find((state) => state.error)?.error ?? null;
  const reason = live ? null : liveReason(status, role, error);
  const loading = status === "checking" || core.some((state) => state.loading);

  const sectionForecast = useApi<ApiPage<ApiForecastRow>>(live && section ? `/forecast?level=section&section=${encodeURIComponent(section)}&limit=${PAGE}` : null);
  const shortageItems = live ? shortagePages.flatMap((page) => page.data?.items ?? []) : null;
  const shortageRows = shortageItems ? sortByRisk(shortageFromApi(shortageItems)) : [];
  // D7 (item 17): the API gives groundwater near a section in its reason; not used for the risk.
  const groundwaterLive = shortageRows.some((row) => !row.groundwaterUnavailable);
  const sections = live && sectionNames.data ? sectionsFromForecast(sectionNames.data.items) : [];
  const summary = live && backtest.data ? summarizeBacktest(backtest.data.items) : null;
  const outlook: OutlookMonth[] = !live ? outlookFromFixture(snapshot.forecast) : !section ? outlookFromApi(city.data?.items ?? [], []) : sectionForecast.live && sectionForecast.data ? outlookFromApi(sectionForecast.data.items, shortageRows) : [];
  const selectedMonth = outlook.find((row)=>row.month===selected) ?? outlook[0] ?? null;
  const history = snapshot.history as Month[];
  const fixtures = snapshot.forecast as ForecastMonth[];
  const fixtureRisks = fixtures.filter((row)=>row.median>row.capacity);
  const fmt=(v:number|null)=>number(v,locale);
  const pct=(v:number|null)=>v===null?"—":new Intl.NumberFormat(locale,{style:"percent",maximumFractionDigits:0}).format(v);
  const monthText=(v:string)=>monthName(v,locale);
  const deliveryPct=snapshot.summary.latest.bookings ? (snapshot.summary.latest.delivered ?? 0)/snapshot.summary.latest.bookings : null;
  const words = live ? { median: w.medianLive, p80: w.p80Live, p90: w.p90Live, capacity: w.capacityLive, forecast: w.liveForecast } : { median: w.median, p80: w.p80, p90: w.p90, capacity: w.capacity, forecast: w.forecast };
  const filtered = riskFilter === "all" ? shortageRows : shortageRows.filter((row)=>row.risk===riskFilter);
  const visible = filtered.slice(0, shownCount);
  const loadedShortage = shortageItems?.length ?? 0;
  const shortageUnavailable = live && shortage1.data?.basis === "UNAVAILABLE";
  const chooseRisk = (value: Risk | "all") => { setRiskFilter(value); setShownCount(SHOW_STEP); };
  const ahead = (n: number | null) => n === null ? "" : `${n} ${n===1?w.aheadOne:w.aheadMany}`;
  const sectionStatus = live && section ? (sectionForecast.loading ? w.loadingSection : sectionForecast.error ? w.sectionLoadFailed : outlook.length === 0 ? w.noSectionRows : null) : null;

  return <div className="forecast-page">
    <header className="forecast-heading"><div><h1>{w.title}</h1><p className="muted">{w.intro}</p></div><div className="forecast-heading-tags"><DataSourceChip state={{ live, loading, error }} /><span className="forecast-demo-badge">{live ? w.derived : w.sim}</span></div></header>
    {reason&&<p className="forecast-live-reason" role="note">{liveReasonCopy[locale][reason]}</p>}
    <div className="forecast-tabs" role="tablist">{(["outlook","accuracy","shortage"] as const).map((tab)=><button key={tab} role="tab" aria-selected={view===tab} className={view===tab?"active":""} onClick={()=>setView(tab)}>{w[tab]}</button>)}</div>
    {view==="outlook"&&<>
      <div className="forecast-metrics"><article><span>{w.latest} · {monthText(snapshot.summary.latest.month)}</span><strong>{fmt(snapshot.summary.latest.bookings)}</strong><small>{w.bookings} · <b className="basis-real">{w.real}</b></small></article><article><span>{w.delivered}</span><strong>{fmt(snapshot.summary.latest.delivered)}</strong><small>{w.deliveryRate}: {deliveryPct===null?"—":new Intl.NumberFormat(locale,{style:"percent",maximumFractionDigits:1}).format(deliveryPct)}</small></article><article><span>{w.peak} · {monthText(snapshot.summary.peak.month)}</span><strong>{fmt(snapshot.summary.peak.bookings)}</strong><small>{w.bookings} · <b className="basis-real">{w.real}</b></small></article><article><span>{w.status}</span><strong>{live ? w.liveStatus : w.pending}</strong><small>{live ? w.liveStatusNote : w.notLive}</small></article></div>
      {live&&<label className="forecast-area">{w.area}<select value={section} onChange={(event)=>{setSection(event.target.value);setSelected(null);}}><option value="">{w.cityTotal}</option>{sections.map((name)=><option key={name} value={name}>{name}</option>)}</select></label>}
      <section className="forecast-chart-panel"><div className="forecast-panel-head"><div><h2>{section ? `${section} · ${words.forecast}` : w.dateRange}</h2><p>{section ? `${w.sectionNote} ${w.sectionsRecut}` : w.historyGap}</p></div><span className={section ? "source-tag derived" : "source-tag real"}>{section ? (outlook[0]?.basis ?? "DERIVED") : `REAL · ${w.observed}`}</span></div>
        {sectionStatus ? <p className="forecast-panel-status" role="status">{sectionStatus}</p> : <OutlookChart history={section ? [] : history} outlook={outlook} selected={selectedMonth?.month ?? null} onSelect={setSelected} locale={locale} title={section || w.dateRange} text={{ ...words, observed: w.observed }} />}
      </section>
      <section className="forecast-detail" aria-label={w.selectedMonthLabel}>{selectedMonth ? <>
        <div><p className="eyebrow">{words.forecast}</p><h2>{monthText(selectedMonth.month)}</h2>{selectedMonth.low90!==null&&selectedMonth.high90!==null ? <p>{w.range}: {fmt(selectedMonth.low90)}–{fmt(selectedMonth.high90)}</p> : <p>{w.rangeUnavailable}{selectedMonth.rangeNote ? `: ${selectedMonth.rangeNote}` : ""}</p>}</div>
        <div className="forecast-detail-metrics"><span>{words.median}<strong>{fmt(selectedMonth.median)}</strong></span><span>{words.p80}<strong>{selectedMonth.low80===null||selectedMonth.high80===null?"—":`${fmt(selectedMonth.low80)}–${fmt(selectedMonth.high80)}`}</strong></span><span>{words.p90}<strong>{selectedMonth.low90===null||selectedMonth.high90===null?"—":`${fmt(selectedMonth.low90)}–${fmt(selectedMonth.high90)}`}</strong></span><span>{words.capacity}<strong>{fmt(selectedMonth.capacity)}</strong></span></div>
      </> : <p className="muted">—</p>}</section>
      <p className="forecast-footnote">{w.dataPeriod}: {snapshot.summary.observedMonthCount} {w.months}, {w.from} {snapshot.historyStart} {w.to??""} {snapshot.historyEnd}. {w.historyGap}</p>
    </>}
    {view==="accuracy"&&(summary ? <>
      <div className="forecast-notice"><strong>{w.liveAccuracyTitle}</strong>{summary.selected&&<span>{w.selectedModel}: {summary.selected.model} — {summary.selected.note}</span>}</div>
      <div className="forecast-table-scroll"><table className="forecast-backtest-table"><caption>{w.comparedOn}</caption><thead><tr><th scope="col">{w.runLabel}</th><th scope="col">{w.modelLabel}</th><th scope="col">{w.cityMape}</th><th scope="col">{w.sectionWape}</th><th scope="col">{w.basis}</th></tr></thead><tbody>{summary.comparisons.map((row)=><tr key={row.run+row.model}><td>{row.run}{row.origin ? <small>{row.origin}</small> : null}</td><td>{row.model}{row.model===summary.selected?.model ? ` · ${w.baselineTag}` : ""}</td><td>{row.cityMape===null?"—":`${row.cityMape.toFixed(1)}%`}</td><td>{row.sectionWape===null?"—":`${row.sectionWape.toFixed(1)}%`}</td><td><span className="source-tag derived">{row.basis}</span></td></tr>)}</tbody></table></div>
      <section className="forecast-explain-panel"><h2>{w.status}: {w.liveStatus}</h2><dl><div><dt>{w.protocol}</dt><dd>{w.protocolLive}</dd></div>{summary.notRun.map((row)=><div key={row.model}><dt>{w.notRun}: {row.model}</dt><dd>{row.note}</dd></div>)}</dl></section>
    </> : <>
      <div className="forecast-notice"><strong>{w.compareTitle}</strong><span>{w.noCandidate}</span></div>
      <div className="forecast-accuracy-grid"><article className="forecast-score-card"><span className="source-tag derived">DERIVED</span><h2>{w.cityMape}</h2><strong>{snapshot.baseline.cityMapePct.toFixed(1)}%</strong><p>{w.benchmark}</p></article><article className="forecast-score-card"><span className="source-tag derived">DERIVED</span><h2>{w.sectionWape}</h2><strong>{snapshot.baseline.sectionWapePct.toFixed(1)}%</strong><p>{w.benchmark}</p></article></div>
      <section className="forecast-explain-panel"><h2>{w.status}: {w.pending}</h2><dl><div><dt>{w.protocol}</dt><dd>{w.undocumented}</dd></div><div><dt>{w.forecast}</dt><dd>{w.notLive}</dd></div><div><dt>{w.range}</dt><dd>{w.fixtureNote}</dd></div></dl></section>
    </>)}
    {view==="shortage"&&(live ? <>
      <div className="forecast-notice shortage-notice"><strong>{w.shortageLiveTitle} · DERIVED</strong><span>{shortageUnavailable ? shortage1.data?.reason : w.shortageLiveNote}</span><span>{w.sectionsRecut}</span></div>
      {groundwaterLive ? <p className="forecast-groundwater-note" role="note"><span className="source-tag">DERIVED</span>{w.groundwaterLiveDerived}</p> : shortageRows.some((row)=>row.groundwaterUnavailable)&&<p className="forecast-groundwater-note" role="note"><span className="source-tag">UNAVAILABLE</span>{w.groundwaterLive}</p>}
      <div className="risk-filter" role="group" aria-label={w.filterLabel}>{(["all",...RISK_ORDER] as const).map((value)=><button key={value} type="button" aria-pressed={riskFilter===value} className={riskFilter===value?"active":""} onClick={()=>chooseRisk(value)}>{`${value==="all"?w.riskAll:w[riskWord[value]]} (${value==="all"?shortageRows.length:shortageRows.filter((row)=>row.risk===value).length})`}</button>)}</div>
      {filtered.length===0 ? <p className="muted">{w.shortageEmpty}</p> : <ol className="shortage-list" aria-label={w.riskListLabel}>{visible.map((row)=><li key={row.key} className={`shortage-item risk-${row.risk}`}>
        <div className="shortage-item-head"><span className={`risk-pill risk-${row.risk}`}>{w[riskWord[row.risk]]}</span><h3>{row.section}</h3><span className="shortage-when">{monthText(row.month)} · {ahead(row.monthsAhead)}</span></div>
        <dl className="shortage-figures"><div><dt>{w.forecastBookings}</dt><dd>{fmt(row.forecast)}</dd></div><div><dt>{w.upper80} <b>{row.upper80Basis}</b></dt><dd>{fmt(row.upper80)}</dd></div><div><dt>{w.capacityTrips} <b>{row.capacityBasis}</b></dt><dd>{fmt(row.capacity)}{row.ratio!==null&&<small> · {pct(row.ratio)} {w.ofCapacity}</small>}</dd></div></dl>
        <p className="shortage-reason">{row.reason}</p>
      </li>)}</ol>}
      <div className="shortage-more"><span>{w.showingCount.replace("{shown}", String(visible.length)).replace("{total}", String(filtered.length))}</span>{visible.length<filtered.length&&<button type="button" className="button button-secondary" onClick={()=>setShownCount((n)=>n+SHOW_STEP)}>{w.showMore}</button>}</div>
      {loadedShortage<shortageTotal&&<p className="forecast-footnote">{w.partial} {loadedShortage} / {shortageTotal}</p>}
      <div className="forecast-signal-grid"><article><span className="source-tag">{groundwaterLive ? "DERIVED" : "UNAVAILABLE"}</span><h2>{w.groundwater}</h2><p>{groundwaterLive ? w.groundwaterDerivedNote : w.groundwaterNote}</p></article><article><span className="source-tag">UNAVAILABLE</span><h2>{w.reservoir}</h2><p>{w.reservoirNote}</p></article></div>
      <p className="forecast-footnote">{w.capacityLiveNote}</p>
    </> : <>
      <div className="forecast-notice shortage-notice"><strong>{w.riskList} · {w.sim}</strong><span>{w.fixtureNote}</span></div>
      <div className="shortage-cards">{fixtureRisks.length===0?<p className="muted">{w.noRisk}</p>:fixtureRisks.map((row)=><article className="shortage-card" key={row.month}><div className="shortage-card-head"><div><span className="forecast-demo-badge">{w.risk} · SIMULATION</span><h2>{monthText(row.month)}</h2></div><span className="shortage-gap">{w.gap}<strong>+{fmt(row.median-row.capacity)}</strong></span></div><div className="shortage-comparison"><span>{w.median}<strong>{fmt(row.median)}</strong></span><span>{w.capacity}<strong>{fmt(row.capacity)}</strong></span><span>{w.range}<strong>{fmt(row.low90)}–{fmt(row.high90)}</strong></span></div><p>{w.overlap}</p></article>)}</div>
      <div className="forecast-signal-grid"><article><span className="source-tag">UNAVAILABLE</span><h2>{w.groundwater}</h2><p>{w.groundwaterNote}</p></article><article><span className="source-tag">UNAVAILABLE</span><h2>{w.reservoir}</h2><p>{w.reservoirNote}</p></article></div>
      <p className="forecast-footnote">{w.capacityNote}</p>
    </>)}
  </div>;
}
