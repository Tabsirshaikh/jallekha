import { useMemo, useRef, useState } from "react";
import { useLocale, type Locale } from "./i18n";
import { useAuth } from "./auth";
import { useApi } from "./useApi";
import { adaptLiveEvidence, adaptLiveNeed, type Clue, type EvidenceDataset, type Feature, type LiveWard, type Ward } from "./evidenceAdapter";
import evidence from "./data/u5Evidence.json";
import geometry from "./data/u5Geometry.json";
import "./EvidenceExperience.css";

type Tab = "need" | "bookings" | "checks";
type Layer = "rising" | "wad" | "cad" | "growth";
type Position = [number, number];
// The committed snapshot (scripts/frontend/build_u5_snapshot.py) is shown whenever live data is not available.
const snapshot = evidence as EvidenceDataset;
const snapshotFeatures = (geometry as { features: Feature[] }).features;
const PAGE = "?limit=200"; // all 145 wards in one page (API maximum is 200)
const SCALE = ["#e3f1ea", "#b9dccb", "#86c2a8", "#4f9e83", "#1f7560"];
const NO_DATA = "#eceeeb";

const copy = {
  en: { owedUnknown: "Water owed: no day closed with deliveries yet", bgTitle: "Background", checkMore: "Booked more than expected: not a low-booking case.", zoomIn: "Zoom in", zoomOut: "Zoom out", zoomReset: "Fit map", risingHelp: "Signs: water owed, bookings jump, \"no water\" complaints, supply cuts.", title: "Water need map", intro: "Where people lack water, where need may be rising, and where bookings look too low. Click a ward for details.", tabNeed: "Need", tabBookings: "Bookings", tabChecks: "Low bookings", layerRising: "Warning signs today", layerWad: "Fetch water from outside", layerCad: "No phone to book", layerGrowth: "Building growth", signIn: "Sign in as an officer to see today's live signs. Showing saved data.", rising: "2 or more warning signs", oneSign: "1 warning sign", calm: "No warning signs", noLive: "No live data yet", wardsRising: "wards with 2 or more warning signs", wardsChecked: "wards with low bookings to check", search: "Find a ward", close: "Close", needTitle: "Need (Census 2011)", wad: "Homes fetching water from outside the premises", cad: "Homes with no phone (cannot book a tanker)", hardship: "Homes in hardship", households: "Households", nowTitle: "Warning signs today", nowNote: "Red on the map when {n} or more of these 4 signs are bad. Signs with no data entered yet are grey.", growthTitle: "Growth", growth: "Buildings grew {p} since 2016", noGrowth: "Building growth unknown", facilities: "Hospitals, clinics and schools mapped", owedBad: "Owed {v} tanker loads", owedOk: "No water owed", bookBad: "{v} bookings in {d} days (usual month: {r})", bookOk: "{v} bookings in {d} days (usual month: {r})", bookUnknown: "Bookings: none entered yet", compBad: "{v} \"no water\" complaints this week", compOk: "{v} \"no water\" complaints this week", cutsBad: "{v} supply cuts this week", cutsOk: "No supply cuts this week", gwBad: "Groundwater {v} m lower than usual: borewells may run dry", gwOk: "Groundwater near its usual level ({v} m)", gwUnknown: "No groundwater wells nearby", checkTitle: "Booking check", checkBooked: "Booked {v} tankers in 2025", checkPeer: "5 similar wards booked about {v}", checkModel: "Statistical model (homes and need) expected about {v}", checkFlag: "Much lower than expected: send someone to check if people can book.", checkOk: "A bit lower than expected, but not low enough to flag.", checkNone: "Not enough data to check this ward.", topShare: "Top {n} areas take {p} of all tankers", gini: "Booking concentration", giniHigh: "very uneven", giniMid: "uneven", giniLow: "fairly even", sourceLive: "Last {d} days, {n} live bookings", sourceHistory: "2022–24 bookings (no live bookings yet)", topList: "Busiest areas", bookingsLayer: "Bookings per month", checksIntro: "These wards booked far fewer tankers than similar wards and than our model expected. Low bookings can mean people cannot book (no phone, no account), not that they have water. Check on the ground before changing anything.", openWard: "Open on map", more: "more", less: "less", unknownLegend: "no data", searchEmpty: "No ward found" },
  te: { owedUnknown: "బాకీ నీరు: డెలివరీలతో ఇంకా ఏ రోజూ ముగించలేదు", bgTitle: "నేపథ్యం", checkMore: "అంచనా కంటే ఎక్కువ బుక్ చేశారు: తక్కువ బుకింగ్ కేసు కాదు.", zoomIn: "దగ్గరగా", zoomOut: "దూరంగా", zoomReset: "మ్యాప్ సరిపెట్టు", risingHelp: "సూచనలు: బాకీ నీరు, బుకింగ్‌ల పెరుగుదల, \"నీరు రాలేదు\" ఫిర్యాదులు, సరఫరా నిలిపివేతలు.", title: "నీటి అవసర పటం", intro: "ఎక్కడ నీరు లేదు, ఎక్కడ అవసరం పెరుగుతోంది, ఎక్కడ బుకింగ్‌లు తక్కువగా ఉన్నాయి. వివరాలకు వార్డుపై నొక్కండి.", tabNeed: "అవసరం", tabBookings: "బుకింగ్‌లు", tabChecks: "తక్కువ బుకింగ్‌లు", layerRising: "ఈరోజు హెచ్చరిక సూచనలు", layerWad: "బయటి నుంచి నీరు తెచ్చుకునేవారు", layerCad: "బుక్ చేయడానికి ఫోన్ లేదు", layerGrowth: "భవనాల పెరుగుదల", signIn: "ఈరోజు ప్రత్యక్ష సూచనల కోసం అధికారిగా సైన్ ఇన్ చేయండి. సేవ్ చేసిన డేటా చూపిస్తున్నాం.", rising: "2 లేదా ఎక్కువ హెచ్చరిక సూచనలు", oneSign: "1 హెచ్చరిక సూచన", calm: "హెచ్చరిక సూచనలు లేవు", noLive: "ఇంకా ప్రత్యక్ష డేటా లేదు", wardsRising: "2 లేదా ఎక్కువ హెచ్చరిక సూచనలు ఉన్న వార్డులు", wardsChecked: "తక్కువ బుకింగ్‌లు ఉన్న, పరిశీలించాల్సిన వార్డులు", search: "వార్డును వెతకండి", close: "మూసివేయి", needTitle: "అవసరం (2011 జనగణన)", wad: "ఆవరణ బయటి నుంచి నీరు తెచ్చుకునే కుటుంబాలు", cad: "ఫోన్ లేని కుటుంబాలు (ట్యాంకర్ బుక్ చేయలేరు)", hardship: "కష్టాల్లో ఉన్న కుటుంబాలు", households: "కుటుంబాలు", nowTitle: "ఈరోజు హెచ్చరిక సూచనలు", nowNote: "ఈ 4 సూచనల్లో {n} లేదా ఎక్కువ చెడుగా ఉంటే మ్యాప్‌లో ఎరుపు. డేటా ఇంకా నమోదు కాని సూచనలు బూడిద రంగులో.", growthTitle: "పెరుగుదల", growth: "2016 నుంచి భవనాలు {p} పెరిగాయి", noGrowth: "భవనాల పెరుగుదల తెలియదు", facilities: "మ్యాప్‌లో ఉన్న ఆసుపత్రులు, క్లినిక్‌లు, పాఠశాలలు", owedBad: "{v} ట్యాంకర్ లోడ్లు బాకీ", owedOk: "నీటి బాకీ లేదు", bookBad: "{d} రోజుల్లో {v} బుకింగ్‌లు (సాధారణ నెల: {r})", bookOk: "{d} రోజుల్లో {v} బుకింగ్‌లు (సాధారణ నెల: {r})", bookUnknown: "బుకింగ్‌లు: ఇంకా నమోదు కాలేదు", compBad: "ఈ వారం {v} \"నీరు రాలేదు\" ఫిర్యాదులు", compOk: "ఈ వారం {v} \"నీరు రాలేదు\" ఫిర్యాదులు", cutsBad: "ఈ వారం {v} సరఫరా నిలిపివేతలు", cutsOk: "ఈ వారం సరఫరా నిలిపివేతలు లేవు", gwBad: "భూగర్భ జలం సాధారణం కంటే {v} మీ. తక్కువ: బోర్లు ఎండిపోవచ్చు", gwOk: "భూగర్భ జలం దాదాపు సాధారణ స్థాయిలో ({v} మీ.)", gwUnknown: "సమీపంలో భూగర్భ జల బావులు లేవు", checkTitle: "బుకింగ్ పరిశీలన", checkBooked: "2025లో {v} ట్యాంకర్లు బుక్ చేశారు", checkPeer: "5 ఇలాంటి వార్డులు సుమారు {v} బుక్ చేశాయి", checkModel: "గణాంక నమూనా (కుటుంబాలు, అవసరం) సుమారు {v} అంచనా వేసింది", checkFlag: "అంచనా కంటే చాలా తక్కువ: ప్రజలు బుక్ చేయగలరా అని పరిశీలనకు ఒకరిని పంపండి.", checkOk: "అంచనా కంటే కొంచెం తక్కువ, కానీ గుర్తించేంత తక్కువ కాదు.", checkNone: "ఈ వార్డును పరిశీలించేందుకు తగిన డేటా లేదు.", topShare: "పై {n} ప్రాంతాలు మొత్తం ట్యాంకర్లలో {p} తీసుకుంటున్నాయి", gini: "బుకింగ్ కేంద్రీకరణ", giniHigh: "చాలా అసమానం", giniMid: "అసమానం", giniLow: "దాదాపు సమానం", sourceLive: "గత {d} రోజులు, {n} ప్రత్యక్ష బుకింగ్‌లు", sourceHistory: "2022–24 బుకింగ్‌లు (ఇంకా ప్రత్యక్ష బుకింగ్‌లు లేవు)", topList: "అత్యధిక బుకింగ్ ప్రాంతాలు", bookingsLayer: "నెలకు బుకింగ్‌లు", checksIntro: "ఈ వార్డులు ఇలాంటి వార్డుల కంటే, మా నమూనా అంచనా కంటే చాలా తక్కువ ట్యాంకర్లు బుక్ చేశాయి. తక్కువ బుకింగ్ అంటే నీరు ఉందని కాదు; ప్రజలు బుక్ చేయలేకపోవచ్చు (ఫోన్, ఖాతా లేకపోవడం). ఏదైనా మార్చే ముందు క్షేత్రస్థాయిలో పరిశీలించండి.", openWard: "మ్యాప్‌లో తెరవండి", more: "ఎక్కువ", less: "తక్కువ", unknownLegend: "డేటా లేదు", searchEmpty: "వార్డు దొరకలేదు" },
  ur: { owedUnknown: "واجب الادا پانی: ابھی کوئی دن ترسیل کے ساتھ بند نہیں ہوا", bgTitle: "پس منظر", checkMore: "اندازے سے زیادہ بک کیے: کم بکنگ کا معاملہ نہیں۔", zoomIn: "قریب کریں", zoomOut: "دور کریں", zoomReset: "نقشہ فٹ کریں", risingHelp: "اشارے: واجب الادا پانی، بکنگ میں اچانک اضافہ، \"پانی نہیں\" شکایات، سپلائی بندش۔", title: "پانی کی ضرورت کا نقشہ", intro: "کہاں پانی نہیں، کہاں ضرورت بڑھ رہی ہے، اور کہاں بکنگ بہت کم ہے۔ تفصیل کے لیے وارڈ پر کلک کریں۔", tabNeed: "ضرورت", tabBookings: "بکنگ", tabChecks: "کم بکنگ", layerRising: "آج کے انتباہی اشارے", layerWad: "باہر سے پانی لانے والے", layerCad: "بکنگ کے لیے فون نہیں", layerGrowth: "عمارتوں میں اضافہ", signIn: "آج کے براہِ راست اشارے دیکھنے کے لیے افسر کے طور پر سائن ان کریں۔ محفوظ ڈیٹا دکھایا جا رہا ہے۔", rising: "2 یا زیادہ انتباہی اشارے", oneSign: "1 انتباہی اشارہ", calm: "کوئی انتباہی اشارہ نہیں", noLive: "ابھی براہِ راست ڈیٹا نہیں", wardsRising: "2 یا زیادہ انتباہی اشاروں والے وارڈ", wardsChecked: "کم بکنگ والے وارڈ جن کی جانچ ہونی ہے", search: "وارڈ تلاش کریں", close: "بند کریں", needTitle: "ضرورت (مردم شماری 2011)", wad: "گھر جو احاطے کے باہر سے پانی لاتے ہیں", cad: "گھر جن کے پاس فون نہیں (ٹینکر بک نہیں کر سکتے)", hardship: "مشکل حالات والے گھر", households: "گھرانے", nowTitle: "آج کے انتباہی اشارے", nowNote: "جب ان 4 میں سے {n} یا زیادہ اشارے خراب ہوں تو نقشے پر سرخ۔ جن اشاروں کا ڈیٹا ابھی درج نہیں وہ سرمئی ہیں۔", growthTitle: "اضافہ", growth: "2016 سے عمارتوں میں {p} اضافہ", noGrowth: "عمارتوں کا اضافہ معلوم نہیں", facilities: "نقشے پر ہسپتال، کلینک اور اسکول", owedBad: "{v} ٹینکر لوڈ واجب الادا", owedOk: "کوئی پانی واجب الادا نہیں", bookBad: "{d} دن میں {v} بکنگ (عام مہینہ: {r})", bookOk: "{d} دن میں {v} بکنگ (عام مہینہ: {r})", bookUnknown: "بکنگ: ابھی درج نہیں", compBad: "اس ہفتے {v} \"پانی نہیں\" شکایات", compOk: "اس ہفتے {v} \"پانی نہیں\" شکایات", cutsBad: "اس ہفتے {v} سپلائی بندش", cutsOk: "اس ہفتے کوئی سپلائی بندش نہیں", gwBad: "زیرِ زمین پانی معمول سے {v} میٹر کم: بورویل سوکھ سکتے ہیں", gwOk: "زیرِ زمین پانی تقریباً معمول پر ({v} میٹر)", gwUnknown: "قریب کوئی زیرِ زمین پانی کا کنواں نہیں", checkTitle: "بکنگ کی جانچ", checkBooked: "2025 میں {v} ٹینکر بک کیے", checkPeer: "5 ملتے جلتے وارڈوں نے تقریباً {v} بک کیے", checkModel: "شماریاتی ماڈل (گھر اور ضرورت) کا اندازہ تقریباً {v}", checkFlag: "اندازے سے بہت کم: کسی کو بھیج کر دیکھیں کہ لوگ بک کر سکتے ہیں یا نہیں۔", checkOk: "اندازے سے کچھ کم، مگر نشان زد کرنے جتنا کم نہیں۔", checkNone: "اس وارڈ کی جانچ کے لیے کافی ڈیٹا نہیں۔", topShare: "سب سے اوپر کے {n} علاقے کل ٹینکروں کا {p} لیتے ہیں", gini: "بکنگ کا ارتکاز", giniHigh: "بہت غیر مساوی", giniMid: "غیر مساوی", giniLow: "تقریباً مساوی", sourceLive: "پچھلے {d} دن، {n} براہِ راست بکنگ", sourceHistory: "2022–24 کی بکنگ (ابھی کوئی براہِ راست بکنگ نہیں)", topList: "سب سے مصروف علاقے", bookingsLayer: "ماہانہ بکنگ", checksIntro: "ان وارڈوں نے ملتے جلتے وارڈوں اور ہمارے ماڈل کے اندازے سے بہت کم ٹینکر بک کیے۔ کم بکنگ کا مطلب یہ ہو سکتا ہے کہ لوگ بک نہیں کر پاتے (فون یا اکاؤنٹ نہیں)، یہ نہیں کہ ان کے پاس پانی ہے۔ کچھ بدلنے سے پہلے موقع پر جانچ کریں۔", openWard: "نقشے پر کھولیں", more: "زیادہ", less: "کم", unknownLegend: "ڈیٹا نہیں", searchEmpty: "کوئی وارڈ نہیں ملا" },
  hi: { owedUnknown: "बकाया पानी: अभी कोई दिन डिलीवरी के साथ बंद नहीं हुआ", bgTitle: "पृष्ठभूमि", checkMore: "अनुमान से ज़्यादा बुक किए: कम बुकिंग का मामला नहीं।", zoomIn: "पास करें", zoomOut: "दूर करें", zoomReset: "नक्शा फ़िट करें", risingHelp: "संकेत: बकाया पानी, बुकिंग में उछाल, \"पानी नहीं\" शिकायतें, आपूर्ति बंद।", title: "पानी की ज़रूरत का नक्शा", intro: "कहाँ पानी नहीं है, कहाँ ज़रूरत बढ़ रही है, और कहाँ बुकिंग बहुत कम है। विवरण के लिए वार्ड पर क्लिक करें।", tabNeed: "ज़रूरत", tabBookings: "बुकिंग", tabChecks: "कम बुकिंग", layerRising: "आज के चेतावनी संकेत", layerWad: "बाहर से पानी लाने वाले", layerCad: "बुकिंग के लिए फ़ोन नहीं", layerGrowth: "इमारतों में बढ़ोतरी", signIn: "आज के लाइव संकेत देखने के लिए अधिकारी के रूप में साइन इन करें। सहेजा हुआ डेटा दिखाया जा रहा है।", rising: "2 या अधिक चेतावनी संकेत", oneSign: "1 चेतावनी संकेत", calm: "कोई चेतावनी संकेत नहीं", noLive: "अभी लाइव डेटा नहीं", wardsRising: "2 या अधिक चेतावनी संकेत वाले वार्ड", wardsChecked: "कम बुकिंग वाले वार्ड जिनकी जाँच करनी है", search: "वार्ड खोजें", close: "बंद करें", needTitle: "ज़रूरत (जनगणना 2011)", wad: "घर जो परिसर के बाहर से पानी लाते हैं", cad: "घर जिनके पास फ़ोन नहीं (टैंकर बुक नहीं कर सकते)", hardship: "कठिनाई वाले घर", households: "परिवार", nowTitle: "आज के चेतावनी संकेत", nowNote: "इन 4 में से {n} या अधिक संकेत खराब हों तो नक्शे पर लाल। जिन संकेतों का डेटा अभी दर्ज नहीं, वे धूसर हैं।", growthTitle: "बढ़ोतरी", growth: "2016 से इमारतें {p} बढ़ीं", noGrowth: "इमारतों की बढ़ोतरी अज्ञात", facilities: "नक्शे पर अस्पताल, क्लिनिक और स्कूल", owedBad: "{v} टैंकर लोड बकाया", owedOk: "कोई पानी बकाया नहीं", bookBad: "{d} दिनों में {v} बुकिंग (सामान्य महीना: {r})", bookOk: "{d} दिनों में {v} बुकिंग (सामान्य महीना: {r})", bookUnknown: "बुकिंग: अभी दर्ज नहीं", compBad: "इस हफ़्ते {v} \"पानी नहीं\" शिकायतें", compOk: "इस हफ़्ते {v} \"पानी नहीं\" शिकायतें", cutsBad: "इस हफ़्ते {v} आपूर्ति बंद", cutsOk: "इस हफ़्ते कोई आपूर्ति बंद नहीं", gwBad: "भूजल सामान्य से {v} मी. नीचे: बोरवेल सूख सकते हैं", gwOk: "भूजल लगभग सामान्य स्तर पर ({v} मी.)", gwUnknown: "पास में भूजल कुआँ नहीं", checkTitle: "बुकिंग जाँच", checkBooked: "2025 में {v} टैंकर बुक किए", checkPeer: "5 मिलते-जुलते वार्डों ने लगभग {v} बुक किए", checkModel: "सांख्यिकीय मॉडल (घर और ज़रूरत) का अनुमान लगभग {v}", checkFlag: "अनुमान से बहुत कम: किसी को भेजकर देखें कि लोग बुक कर पाते हैं या नहीं।", checkOk: "अनुमान से थोड़ा कम, पर चिह्नित करने जितना कम नहीं।", checkNone: "इस वार्ड की जाँच के लिए पर्याप्त डेटा नहीं।", topShare: "शीर्ष {n} इलाके कुल टैंकरों का {p} लेते हैं", gini: "बुकिंग संकेंद्रण", giniHigh: "बहुत असमान", giniMid: "असमान", giniLow: "लगभग समान", sourceLive: "पिछले {d} दिन, {n} लाइव बुकिंग", sourceHistory: "2022–24 की बुकिंग (अभी कोई लाइव बुकिंग नहीं)", topList: "सबसे व्यस्त इलाके", bookingsLayer: "प्रति माह बुकिंग", checksIntro: "इन वार्डों ने मिलते-जुलते वार्डों और हमारे मॉडल के अनुमान से बहुत कम टैंकर बुक किए। कम बुकिंग का मतलब हो सकता है कि लोग बुक नहीं कर पाते (फ़ोन या खाता नहीं), यह नहीं कि उनके पास पानी है। कुछ बदलने से पहले मौके पर जाँच करें।", openWard: "नक्शे पर खोलें", more: "अधिक", less: "कम", unknownLegend: "डेटा नहीं", searchEmpty: "कोई वार्ड नहीं मिला" },
} satisfies Record<Locale, Record<string, string>>;
type Words = (typeof copy)["en"];

const fill = (s: string, v: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k: string) => String(v[k] ?? ""));
function points(v: unknown): Position[] {
  if (!Array.isArray(v)) return [];
  if (typeof v[0] === "number" && typeof v[1] === "number") return [[v[0], v[1]]];
  return v.flatMap(points);
}
function rings(f: Feature): Position[][] {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : (f.geometry.coordinates as unknown[]);
  return polys.flatMap((poly) => (Array.isArray(poly) ? poly.map(points) : [])).filter((ring) => ring.length > 2);
}
/** Five equal-count classes; returns the class (0-4) of a value, or null when it is missing. */
function classes(values: (number | null)[]) {
  const sorted = values.filter((v): v is number => v !== null).sort((a, b) => a - b);
  const cuts = [1, 2, 3, 4].map((k) => sorted[Math.floor((sorted.length * k) / 5)] ?? Infinity);
  return { cuts, of: (v: number | null) => (v === null ? null : cuts.filter((c) => v >= c).length) };
}

function clueText(c: Clue, w: Words, days: number, fmt: (n: number) => string) {
  const v = c.value ?? 0;
  if (c.code === "owed") return !c.known ? w.owedUnknown : c.bad ? fill(w.owedBad, { v: fmt(v) }) : w.owedOk;
  if (c.code === "bookings") return c.known ? fill(c.bad ? w.bookBad : w.bookOk, { v: fmt(v), d: days, r: fmt(c.reference / 1.5) }) : w.bookUnknown;
  if (c.code === "complaints") return fill(c.bad ? w.compBad : w.compOk, { v: fmt(v) });
  if (c.code === "cuts") return c.bad ? fill(w.cutsBad, { v: fmt(v) }) : w.cutsOk;
  return c.known ? fill(c.bad ? w.gwBad : w.gwOk, { v: v.toFixed(1) }) : w.gwUnknown;
}

export default function EvidenceExperience() {
  const { locale } = useLocale();
  const w = copy[locale];
  const nf = useMemo(() => new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { maximumFractionDigits: 1 }), [locale]);
  const pf = useMemo(() => new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { style: "percent", maximumFractionDigits: 0 }), [locale]);
  const fmt = (n: number) => nf.format(n);
  const pct = (n: number | null | undefined) => (n === null || n === undefined ? "—" : pf.format(n));
  const [tab, setTab] = useState<Tab>("need");
  const [layer, setLayer] = useState<Layer>("rising");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  // Live data needs an officer token; signed out the screen shows the saved snapshot.
  const { status } = useAuth();
  const enabled = status !== "anonymous" && status !== "rejected";
  const atlas = useApi<unknown>(enabled ? "/atlas/wards" + PAGE : null);
  const equityWards = useApi<unknown>(enabled ? "/equity/wards" + PAGE : null);
  const equitySummary = useApi<unknown>(enabled ? "/equity/summary" : null);
  const fieldChecks = useApi<unknown>(enabled ? "/underserved/field-checks" + PAGE : null);
  const layerGeo = useApi<unknown>(enabled ? "/coverage/layers/water_access_evidence" : null);
  const liveNeedApi = useApi<unknown>(enabled ? "/atlas/live" : null);
  const sources = [atlas, equityWards, equitySummary, fieldChecks, layerGeo];
  const allLive = sources.every((s) => s.live);
  const live = useMemo(() => (allLive ? adaptLiveEvidence({ atlas: atlas.data, equityWards: equityWards.data, equitySummary: equitySummary.data, fieldChecks: fieldChecks.data, layer: layerGeo.data }) : null), [allLive, atlas.data, equityWards.data, equitySummary.data, fieldChecks.data, layerGeo.data]);
  const need = useMemo(() => (liveNeedApi.live ? adaptLiveNeed(liveNeedApi.data) : null), [liveNeedApi.live, liveNeedApi.data]);

  const dataset = live?.dataset ?? snapshot;
  const features = live?.features ?? snapshotFeatures;
  const rows = dataset.wards;
  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const liveOf = (id: string): LiveWard | undefined => need?.wards.get(id);
  const conc = need?.concentration ?? null;
  // Without live data the live layer has nothing to show: fall back to the Census layer.
  const shown: Layer = layer === "rising" && !need ? "wad" : layer;
  const usualMonth = (r: Ward) => (r.bookings === null ? null : r.bookings / 25);
  const bookingsOf = (r: Ward) => (conc?.source === "live" ? liveOf(r.id)?.bookingsWindow ?? 0 : usualMonth(r));

  // Map: equirectangular projection corrected for latitude, so wards keep their shape.
  const shapes = useMemo(() => features.flatMap((f) => (byId.has(f.properties.ward_id) ? [{ id: f.properties.ward_id, rings: rings(f) }] : [])), [features, byId]);
  const view = useMemo(() => {
    const all = shapes.flatMap((s) => s.rings.flat());
    const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
    const width = 1000, height = Math.round((width * (maxY - minY)) / ((maxX - minX) * k));
    const project = ([x, y]: Position) => `${(((x - minX) / (maxX - minX)) * width).toFixed(1)},${(((maxY - y) / (maxY - minY)) * height).toFixed(1)}`;
    return { width, height, paths: new Map(shapes.map((s) => [s.id, s.rings.map((r) => "M" + r.map(project).join("L") + "Z").join("")])) };
  }, [shapes]);

  // Zoom and drag: the view box moves over the fitted map; a drag never counts as a click.
  const [zoom, setZoom] = useState<{ x: number; y: number; w: number } | null>(null);
  const box = zoom ?? { x: -10, y: -10, w: view.width + 20 };
  const boxH = (box.w * (view.height + 20)) / (view.width + 20);
  const drag = useRef<{ px: number; py: number; x: number; y: number; moved: boolean } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomBy = (factor: number, cx = 0.5, cy = 0.5) => {
    const w2 = Math.min(view.width + 20, Math.max(80, box.w * factor));
    const h2 = (w2 * (view.height + 20)) / (view.width + 20);
    setZoom({ x: box.x + (box.w - w2) * cx, y: box.y + (boxH - h2) * cy, w: w2 });
  };
  const onWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return;
    zoomBy(e.deltaY < 0 ? 0.8 : 1.25, (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
  };
  const onDown = (e: React.PointerEvent<SVGSVGElement>) => { drag.current = { px: e.clientX, py: e.clientY, x: box.x, y: box.y, moved: false }; };
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current, r = svgRef.current?.getBoundingClientRect();
    if (!d || !r) return;
    const dx = e.clientX - d.px, dy = e.clientY - d.py;
    if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
    if (d.moved) setZoom({ x: d.x - (dx * box.w) / r.width, y: d.y - (dy * boxH) / r.height, w: box.w });
  };
  const pick = (id: string) => { if (!drag.current?.moved) setSelectedId(id); };

  const metric = (r: Ward): number | null =>
    tab === "bookings" ? bookingsOf(r) : shown === "wad" ? r.waterAccessDeficitShare : shown === "cad" ? r.constrainedAccessShare ?? null : shown === "growth" ? (r.growthRatio === null ? null : r.growthRatio - 1) : null;
  const scale = useMemo(() => classes(rows.map(metric)), [rows, tab, shown, conc]); // eslint-disable-line react-hooks/exhaustive-deps
  function colour(r: Ward) {
    if (tab === "checks") return r.fieldCandidate === true ? "#c9783f" : NO_DATA;
    if (tab === "need" && shown === "rising") {
      const l = liveOf(r.id);
      if (!l || l.knownCount === 0) return NO_DATA;
      return l.rising ? "#c4473a" : l.badCount === 1 ? "#e3a64a" : "#9fd0b8";
    }
    const c = scale.of(metric(r));
    return c === null ? NO_DATA : SCALE[c];
  }

  const rising = rows.filter((r) => liveOf(r.id)?.rising).length;
  const checks = rows.filter((r) => r.fieldCandidate === true).sort((a, b) => (a.observedBookings ?? 0) / (a.peerExpected || 1) - (b.observedBookings ?? 0) / (b.peerExpected || 1));
  const found = query.trim() ? rows.filter((r) => r.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];
  const legendScale = tab === "bookings" || shown !== "rising";

  return (
    <div className="atlas-page">
      <header className="atlas-head">
        <div><h1>{w.title}</h1><p className="muted">{need ? w.intro : w.signIn}</p></div>
        <div className="atlas-search">
          <input aria-label={w.search} placeholder={w.search} value={query} onChange={(e) => setQuery(e.target.value)} />
          {query.trim() && <ul>{found.length ? found.map((r) => <li key={r.id}><button onClick={() => { setSelectedId(r.id); setQuery(""); }}>{r.name}</button></li>) : <li className="muted">{w.searchEmpty}</li>}</ul>}
        </div>
      </header>

      <div className="atlas-tabs" role="tablist">
        {(["need", "bookings", "checks"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t === "need" ? w.tabNeed : t === "bookings" ? w.tabBookings : w.tabChecks}</button>)}
      </div>

      <section className="atlas-stage">
        <div className="atlas-overlay atlas-overlay-top">
          {tab === "need" && <div className="atlas-chips" role="radiogroup">{(["rising", "wad", "cad", "growth"] as const).map((l) => <button key={l} role="radio" aria-checked={shown === l} className={shown === l ? "active" : ""} disabled={l === "rising" && !need} title={l === "rising" && !need ? w.signIn : undefined} onClick={() => setLayer(l)}>{l === "rising" ? w.layerRising : l === "wad" ? w.layerWad : l === "cad" ? w.layerCad : w.layerGrowth}</button>)}</div>}
          {tab === "need" && shown === "rising" && <p className="atlas-help">{w.risingHelp}</p>}
          {tab === "need" && shown === "rising" && need && <p className="atlas-stat"><strong>{fmt(rising)}</strong> {w.wardsRising}</p>}
          {tab === "bookings" && conc && <div className="atlas-stat-card">
            <p className="atlas-big">{fill(w.topShare, { n: fmt(conc.topSections), p: pct(conc.topShare) })}</p>
            <p>{w.gini}: <strong>{conc.gini === null ? "—" : conc.gini >= 0.6 ? w.giniHigh : conc.gini >= 0.35 ? w.giniMid : w.giniLow}</strong> ({conc.gini?.toFixed(2) ?? "—"})</p>
            <p className="muted">{conc.source === "live" ? fill(w.sourceLive, { d: need?.windowDays ?? 30, n: fmt(conc.liveBookings) }) : w.sourceHistory}</p>
          </div>}
          {tab === "bookings" && !conc && <div className="atlas-stat-card"><p className="atlas-big">{fill(w.topShare, { n: fmt(dataset.summary.equity.top_section_count), p: pct(dataset.summary.equity.top_booking_share) })}</p><p className="muted">{w.sourceHistory}</p></div>}
          {tab === "checks" && <p className="atlas-stat"><strong>{fmt(checks.length)}</strong> {w.wardsChecked}</p>}
        </div>
        <svg ref={svgRef} className="atlas-map" viewBox={`${box.x} ${box.y} ${box.w} ${boxH}`} role="group" aria-label={w.title}
          onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => setTimeout(() => { drag.current = null; }, 0)} onPointerLeave={() => { drag.current = null; }}>
          {rows.map((r) => {
            const d = view.paths.get(r.id);
            if (!d) return null;
            return <path key={r.id} d={d} fill={colour(r)} className={(selectedId === r.id ? "selected " : "") + (hover === r.id ? "hover" : "")} tabIndex={0} role="button" aria-label={r.name}
              onClick={() => pick(r.id)} onMouseEnter={() => setHover(r.id)} onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedId(r.id); } }}><title>{r.name}</title></path>;
          })}
        </svg>
        <div className="atlas-overlay atlas-zoom"><button aria-label={w.zoomIn} title={w.zoomIn} onClick={() => zoomBy(0.7)}>+</button><button aria-label={w.zoomOut} title={w.zoomOut} onClick={() => zoomBy(1.4)}>−</button><button aria-label={w.zoomReset} title={w.zoomReset} onClick={() => setZoom(null)}>⤢</button></div>
        {hover && byId.get(hover) && <div className="atlas-tooltip">{byId.get(hover)!.name}</div>}
        <div className="atlas-overlay atlas-legend">
          {legendScale ? <><span>{w.less}</span>{SCALE.map((c) => <i key={c} style={{ background: c }} />)}<span>{w.more}</span><i style={{ background: NO_DATA }} /><span>{w.unknownLegend}</span></>
            : tab === "checks" ? <><i style={{ background: "#c9783f" }} /><span>{w.tabChecks}</span></>
            : <><i style={{ background: "#c4473a" }} /><span>{w.rising}</span><i style={{ background: "#e3a64a" }} /><span>{w.oneSign}</span><i style={{ background: "#9fd0b8" }} /><span>{w.calm}</span><i style={{ background: NO_DATA }} /><span>{w.noLive}</span></>}
        </div>
        {tab === "bookings" && conc && conc.top.length > 0 && <aside className="atlas-overlay atlas-top-list"><h3>{w.topList}</h3><ol>{conc.top.map((t) => <li key={t.section}><span>{t.section}</span><strong>{pct(t.share)}</strong></li>)}</ol></aside>}
      </section>

      {tab === "checks" && <section className="atlas-checks">
        <p className="atlas-explain">{w.checksIntro}</p>
        <div className="atlas-check-grid">{checks.map((r) => <article key={r.id} className="atlas-check-card">
          <h3>{r.name}</h3>
          <CheckBars ward={r} w={w} fmt={fmt} />
          <button className="text-button" onClick={() => setSelectedId(r.id)}>{w.openWard}</button>
        </article>)}</div>
      </section>}

      {selected && <WardSheet ward={selected} live={liveOf(selected.id)} days={need?.windowDays ?? 30} minBad={need?.minBad ?? 2} w={w} fmt={fmt} pct={pct} onClose={() => setSelectedId(null)} />}
    </div>
  );
}

function CheckBars({ ward, w, fmt }: { ward: Ward; w: Words; fmt: (n: number) => string }) {
  const values = [ward.observedBookings, ward.peerExpected, ward.modelExpected];
  if (values.some((v) => v === null || v === undefined)) return <p className="muted">{w.checkNone}</p>;
  const [seen, peer, model] = values as number[];
  const max = Math.max(seen, peer, model, 1);
  const bar = (label: string, v: number, kind: string) => <div className="atlas-bar"><span>{fill(label, { v: fmt(Math.round(v)) })}</span><i className={kind} style={{ width: `${Math.max(1.5, (v / max) * 100)}%` }} /></div>;
  return <div className="atlas-bars">
    {bar(w.checkBooked, seen, "seen")}{bar(w.checkPeer, peer, "peer")}{bar(w.checkModel, model, "model")}
    <p className={ward.fieldCandidate ? "atlas-verdict flag" : "atlas-verdict"}>{ward.fieldCandidate ? w.checkFlag : seen >= Math.min(peer, model) ? w.checkMore : w.checkOk}</p>
  </div>;
}

function WardSheet({ ward, live, days, minBad, w, fmt, pct, onClose }: { ward: Ward; live: LiveWard | undefined; days: number; minBad: number; w: Words; fmt: (n: number) => string; pct: (n: number | null | undefined) => string; onClose: () => void }) {
  const status = !live || live.knownCount === 0 ? w.noLive : live.rising ? w.rising : live.badCount === 1 ? w.oneSign : w.calm;
  return (
    <section className="atlas-sheet" role="dialog" aria-label={ward.name}>
      <header><div><h2>{ward.name}</h2><span className={"atlas-pill " + (!live || live.knownCount === 0 ? "none" : live.rising ? "bad" : live.badCount === 1 ? "warn" : "ok")}>{status}</span></div><button className="atlas-close" onClick={onClose} aria-label={w.close}>×</button></header>
      <div className="atlas-sheet-grid">
        <div><h3>{w.nowTitle}</h3>
          {live ? <><ul className="atlas-clues">{live.clues.filter((c) => c.counts).map((c) => <li key={c.code} className={c.bad ? "bad" : c.known ? "ok" : "unknown"}>{clueText(c, w, days, fmt)}</li>)}</ul><p className="muted small">{fill(w.nowNote, { n: minBad })}</p>
            <h3 className="atlas-bg-title">{w.bgTitle}</h3><ul className="atlas-clues">{live.clues.filter((c) => !c.counts).map((c) => <li key={c.code} className="info">{clueText(c, w, days, fmt)}</li>)}</ul></> : <p className="muted">{w.signIn}</p>}
        </div>
        <div><h3>{w.needTitle}</h3>
          <dl className="atlas-facts">
            <div><dt>{w.wad}</dt><dd>{pct(ward.waterAccessDeficitShare)}</dd></div>
            <div><dt>{w.cad}</dt><dd>{pct(ward.constrainedAccessShare)}</dd></div>
            <div><dt>{w.hardship}</dt><dd>{pct(ward.hardshipShare)}</dd></div>
            <div><dt>{w.households}</dt><dd>{ward.households2011 === null ? "—" : fmt(ward.households2011)}</dd></div>
            {ward.criticalFacilities !== null && ward.criticalFacilities !== undefined && <div><dt>{w.facilities}</dt><dd>{fmt(ward.criticalFacilities)}</dd></div>}
          </dl>
          <p className="small">{ward.growthRatio === null ? w.noGrowth : fill(w.growth, { p: pct(ward.growthRatio - 1) })}</p>
        </div>
        <div><h3>{w.checkTitle}</h3><CheckBars ward={ward} w={w} fmt={fmt} /></div>
      </div>
    </section>
  );
}
