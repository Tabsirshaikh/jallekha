import { useMemo, useState } from "react";
import { useLocale, type Locale } from "./i18n";
import { useAuth } from "./auth";
import { useApi } from "./useApi";
import { adaptLiveEvidence, adaptLiveNeed, adaptSectionChecks, type SectionCheck, type Clue, type EvidenceDataset, type Feature, type LiveWard, type Ward } from "./evidenceAdapter";
import evidence from "./data/u5Evidence.json";
import geometry from "./data/u5Geometry.json";
import savedSections from "./data/u5SectionChecks.json";
import SectionOutcomeForm from "./SectionOutcomeForm";
import WeeklyPriorityPanel from "./WeeklyPriorityPanel";
import { weeklyCopy, type WeeklyRow } from "./weeklyPriorityCopy";
import sectionEvidence from "./data/u5SectionEvidence.json";
import sectionGeometry from "./data/u5SectionGeometry.json";
import "./EvidenceExperience.css";

type Tab = "need" | "bookings" | "checks";
const outcomeCopy = {
  en: { checkedYes: "Visited: people could not book", checkedNo: "Visited: people could book", checkedUnclear: "Visited: booking access unclear" },
  te: { checkedYes: "సందర్శించారు: ప్రజలు బుక్ చేయలేకపోయారు", checkedNo: "సందర్శించారు: ప్రజలు బుక్ చేయగలిగారు", checkedUnclear: "సందర్శించారు: బుకింగ్ అవకాశం స్పష్టంగా లేదు" },
  ur: { checkedYes: "دورہ ہوا: لوگ بک نہیں کر سکے", checkedNo: "دورہ ہوا: لوگ بک کر سکے", checkedUnclear: "دورہ ہوا: بکنگ کی رسائی واضح نہیں" },
  hi: { checkedYes: "दौरा हुआ: लोग बुक नहीं कर पाए", checkedNo: "दौरा हुआ: लोग बुक कर पाए", checkedUnclear: "दौरा हुआ: बुकिंग की पहुँच स्पष्ट नहीं" },
};
type Layer = "current" | "rising" | "need" | "wad" | "cad" | "growth";
const sectionCopy = {
  en: { tabChecks: "3. Low bookings", stepChecks: "Sections with unusually few bookings per domestic connection: visit to check whether people can book.", wardsChecked: "sections to visit", checksIntro: "These sections booked far fewer tankers per connection than comparable sections in their division. The point locates the section; ward need is background only. Check on the ground before changing anything.", sectionRate: "Bookings per 1,000 domestic connections: {v}", sectionPeer: "Similar sections' rate: {v}", unchecked: "Not yet checked on the ground", emptyChecks: "No sections flagged for a visit", sectionSnapshot: "Saved section checks", sectionLive: "Section checks from the service", checkNone: "Ward booking estimates are unavailable. Section checks are shown separately." },
  te: { tabChecks: "3. తక్కువ బుకింగ్‌లు", stepChecks: "గృహ కనెక్షన్‌కు అసాధారణంగా తక్కువ బుకింగ్‌లు ఉన్న విభాగాలు: ప్రజలు బుక్ చేయగలరా అని వెళ్లి చూడండి.", wardsChecked: "సందర్శించాల్సిన విభాగాలు", checksIntro: "ఈ విభాగాలు తమ డివిజన్‌లోని ఇలాంటి విభాగాల కంటే కనెక్షన్‌కు చాలా తక్కువ ట్యాంకర్లు బుక్ చేశాయి. చుక్క విభాగాన్ని చూపుతుంది; వార్డు అవసరం నేపథ్యం మాత్రమే. ఏదైనా మార్చే ముందు క్షేత్రస్థాయిలో పరిశీలించండి.", sectionRate: "1,000 గృహ కనెక్షన్లకు బుకింగ్‌లు: {v}", sectionPeer: "ఇలాంటి విభాగాల రేటు: {v}", unchecked: "ఇంకా క్షేత్రస్థాయిలో పరిశీలించలేదు", emptyChecks: "సందర్శనకు గుర్తించిన విభాగాలు లేవు", sectionSnapshot: "భద్రపరచిన విభాగ పరిశీలనలు", sectionLive: "సేవ నుంచి విభాగ పరిశీలనలు", checkNone: "వార్డు బుకింగ్ అంచనాలు అందుబాటులో లేవు. విభాగ పరిశీలనలు విడిగా చూపబడతాయి." },
  ur: { tabChecks: "3. کم بکنگ", stepChecks: "گھریلو کنکشن کے لحاظ سے غیر معمولی کم بکنگ والے سیکشن: موقع پر دیکھیں کہ لوگ بک کر سکتے ہیں یا نہیں۔", wardsChecked: "سیکشن جن کا دورہ کرنا ہے", checksIntro: "ان سیکشنوں نے اپنی ڈویژن کے ملتے جلتے سیکشنوں سے فی کنکشن بہت کم ٹینکر بک کیے۔ نقطہ سیکشن کی جگہ دکھاتا ہے؛ وارڈ کی ضرورت صرف پس منظر ہے۔ کچھ بدلنے سے پہلے موقع پر جانچ کریں۔", sectionRate: "ہر 1,000 گھریلو کنکشن پر بکنگ: {v}", sectionPeer: "ملتے جلتے سیکشنوں کی شرح: {v}", unchecked: "ابھی موقع پر جانچ نہیں ہوئی", emptyChecks: "دورے کے لیے کوئی سیکشن نشان زد نہیں", sectionSnapshot: "محفوظ سیکشن جانچ", sectionLive: "سروس سے سیکشن جانچ", checkNone: "وارڈ کی بکنگ کے اندازے دستیاب نہیں۔ سیکشن کی جانچ الگ دکھائی جاتی ہے۔" },
  hi: { tabChecks: "3. कम बुकिंग", stepChecks: "घरेलू कनेक्शन के हिसाब से असामान्य रूप से कम बुकिंग वाले सेक्शन: जाकर देखें कि लोग बुक कर पाते हैं या नहीं।", wardsChecked: "दौरे के लिए सेक्शन", checksIntro: "इन सेक्शन ने अपने डिविज़न के मिलते-जुलते सेक्शन से प्रति कनेक्शन बहुत कम टैंकर बुक किए। बिंदु सेक्शन की जगह दिखाता है; वार्ड की ज़रूरत केवल संदर्भ है। कुछ बदलने से पहले मौके पर जाँच करें।", sectionRate: "हर 1,000 घरेलू कनेक्शन पर बुकिंग: {v}", sectionPeer: "मिलते-जुलते सेक्शन की दर: {v}", unchecked: "अभी मौके पर जाँच नहीं हुई", emptyChecks: "दौरे के लिए कोई सेक्शन चिह्नित नहीं", sectionSnapshot: "सहेजी गई सेक्शन जाँच", sectionLive: "सेवा से सेक्शन जाँच", checkNone: "वार्ड बुकिंग के अनुमान उपलब्ध नहीं हैं। सेक्शन की जाँच अलग दिखाई जाती है।" },
};
type Position = [number, number];
// The committed snapshot (scripts/frontend/build_u5_snapshot.py) is shown whenever live data is not available.
const snapshot = evidence as EvidenceDataset;
const snapshotFeatures = (geometry as { features: Feature[] }).features;
// Sections: the same shapes of data, one row per HMWSSB section (scripts/evidence/build_section_map.py).
const sectionSnapshot = sectionEvidence as unknown as EvidenceDataset;
const sectionFeatures = (sectionGeometry as unknown as { features: Feature[] }).features;
// Need score per ward from the snapshot, used when the live API does not send one.
const savedNeed = new Map(snapshot.wards.map((w) => [w.id, w.needWeight ?? null]));
const PAGE = "?limit=200"; // all 145 wards in one page (API maximum is 200)
const SCALE = ["#e3f1ea", "#b9dccb", "#86c2a8", "#4f9e83", "#1f7560"];
const NO_DATA = "#eceeeb";

const copy = {
  en: { needScore: "Water need score", needHelp: "One score per ward from Census: 1 + 2 x homes fetching water from outside + homes with no phone + hardship. The same score the fair queue uses to share tankers.", layerNeed: "Water need", layerHouseholds: "Households", layerHardship: "Hardship", stepChecks: "Wards that booked far fewer tankers than similar wards with the same need: send someone to check whether people can book.", stepBookings: "Where HMWSSB's tankers actually go: bookings by area, and how concentrated they are.", stepNeed: "Which wards need water most: homes fetching water from outside, homes with no phone, hardship, households (Census 2011).", signs: "{n} of 4 signs", growthNote: "Listed A–Z, not ranked: buildings are not households, so growth must not rank wards.", showLess: "Show top 15", showAll: "Show all wards", rankTitle: "All wards: {layer}", owedUnknown: "Water owed: no day closed with deliveries yet", bgTitle: "Background", checkMore: "Booked more than expected: not a low-booking case.", zoomIn: "Zoom in", zoomOut: "Zoom out", zoomReset: "Fit map", risingHelp: "Signs: water owed, bookings jump, \"no water\" complaints, supply cuts.", title: "Water need map", intro: "Where people lack water, where need may be rising, and where bookings look too low. Click a ward for details.", tabNeed: "1. Need", tabBookings: "2. Bookings", tabChecks: "3. Expected vs actual", layerRising: "Warning signs today", layerWad: "Fetch water from outside", layerCad: "No phone to book", layerGrowth: "Building growth", signIn: "Sign in as an officer to see today's live signs. Showing saved data.", rising: "2 or more warning signs", oneSign: "1 warning sign", calm: "No warning signs", noLive: "No live data yet", wardsRising: "wards with 2 or more warning signs", wardsChecked: "wards with low bookings to check", search: "Find a ward", close: "Close", needTitle: "Need (Census 2011)", wad: "Homes fetching water from outside the premises", cad: "Homes with no phone (cannot book a tanker)", hardship: "Homes in hardship", households: "Households", nowTitle: "Warning signs today", nowNote: "Red on the map when {n} or more of these 4 signs are bad. Signs with no data entered yet are grey.", growthTitle: "Growth", growth: "Buildings grew {p} since 2016", noGrowth: "Building growth unknown", facilities: "Hospitals, clinics and schools mapped", owedBad: "Owed {v} tanker loads", owedOk: "No water owed", bookBad: "{v} bookings in {d} days (usual month: {r})", bookOk: "{v} bookings in {d} days (usual month: {r})", bookUnknown: "Bookings: none entered yet", compBad: "{v} \"no water\" complaints this week", compOk: "{v} \"no water\" complaints this week", cutsBad: "{v} supply cuts this week", cutsOk: "No supply cuts this week", gwBad: "Groundwater {v} m lower than usual: borewells may run dry", gwOk: "Groundwater near its usual level ({v} m)", gwUnknown: "No groundwater wells nearby", checkTitle: "Booking check", checkBooked: "Booked {v} tankers in 2025", checkPeer: "5 similar wards booked about {v}", checkModel: "Statistical model (homes and need) expected about {v}", checkFlag: "Much lower than expected: send someone to check if people can book.", checkOk: "A bit lower than expected, but not low enough to flag.", checkNone: "Not enough data to check this ward.", topShare: "Top {n} areas take {p} of all tankers", gini: "Booking concentration", giniHigh: "very uneven", giniMid: "uneven", giniLow: "fairly even", sourceLive: "Last {d} days, {n} live bookings", sourceHistory: "2022–24 bookings (no live bookings yet)", topList: "Busiest areas", bookingsLayer: "Bookings per month", checksIntro: "These wards booked far fewer tankers than similar wards and than our model expected. Low bookings can mean people cannot book (no phone, no account), not that they have water. Check on the ground before changing anything.", openWard: "Open on map", more: "more", less: "less", unknownLegend: "no data", searchEmpty: "No ward found" },
  te: { needScore: "నీటి అవసర స్కోరు", needHelp: "జనగణన నుంచి ప్రతి వార్డుకు ఒక స్కోరు: 1 + 2 x బయటి నుంచి నీరు తెచ్చుకునే కుటుంబాలు + ఫోన్ లేని కుటుంబాలు + కష్టాలు. ట్యాంకర్లను పంచడానికి న్యాయమైన క్యూ వాడే అదే స్కోరు.", layerNeed: "నీటి అవసరం", layerHouseholds: "కుటుంబాలు", layerHardship: "కష్టాలు", stepChecks: "ఇదే అవసరం ఉన్న ఇలాంటి వార్డుల కంటే చాలా తక్కువ బుక్ చేసిన వార్డులు: ప్రజలు బుక్ చేయగలరా అని పరిశీలనకు ఒకరిని పంపండి.", stepBookings: "HMWSSB ట్యాంకర్లు నిజంగా ఎక్కడికి వెళ్తున్నాయి: ప్రాంతాల వారీ బుకింగ్‌లు, అవి ఎంత కేంద్రీకృతమయ్యాయి.", stepNeed: "ఏ వార్డులకు నీరు ఎక్కువ అవసరం: బయటి నుంచి నీరు తెచ్చుకునే కుటుంబాలు, ఫోన్ లేని కుటుంబాలు, కష్టాలు, కుటుంబాల సంఖ్య (2011 జనగణన).", signs: "4లో {n} సూచనలు", growthNote: "అక్షర క్రమంలో, ర్యాంక్ కాదు: భవనాలు కుటుంబాలు కావు, కాబట్టి పెరుగుదలతో వార్డులకు ర్యాంక్ ఇవ్వకూడదు.", showLess: "మొదటి 15 చూపించు", showAll: "అన్ని వార్డులు చూపించు", rankTitle: "అన్ని వార్డులు: {layer}", owedUnknown: "బాకీ నీరు: డెలివరీలతో ఇంకా ఏ రోజూ ముగించలేదు", bgTitle: "నేపథ్యం", checkMore: "అంచనా కంటే ఎక్కువ బుక్ చేశారు: తక్కువ బుకింగ్ కేసు కాదు.", zoomIn: "దగ్గరగా", zoomOut: "దూరంగా", zoomReset: "మ్యాప్ సరిపెట్టు", risingHelp: "సూచనలు: బాకీ నీరు, బుకింగ్‌ల పెరుగుదల, \"నీరు రాలేదు\" ఫిర్యాదులు, సరఫరా నిలిపివేతలు.", title: "నీటి అవసర పటం", intro: "ఎక్కడ నీరు లేదు, ఎక్కడ అవసరం పెరుగుతోంది, ఎక్కడ బుకింగ్‌లు తక్కువగా ఉన్నాయి. వివరాలకు వార్డుపై నొక్కండి.", tabNeed: "1. అవసరం", tabBookings: "2. బుకింగ్‌లు", tabChecks: "3. అంచనా vs వాస్తవం", layerRising: "ఈరోజు హెచ్చరిక సూచనలు", layerWad: "బయటి నుంచి నీరు తెచ్చుకునేవారు", layerCad: "బుక్ చేయడానికి ఫోన్ లేదు", layerGrowth: "భవనాల పెరుగుదల", signIn: "ఈరోజు ప్రత్యక్ష సూచనల కోసం అధికారిగా సైన్ ఇన్ చేయండి. సేవ్ చేసిన డేటా చూపిస్తున్నాం.", rising: "2 లేదా ఎక్కువ హెచ్చరిక సూచనలు", oneSign: "1 హెచ్చరిక సూచన", calm: "హెచ్చరిక సూచనలు లేవు", noLive: "ఇంకా ప్రత్యక్ష డేటా లేదు", wardsRising: "2 లేదా ఎక్కువ హెచ్చరిక సూచనలు ఉన్న వార్డులు", wardsChecked: "తక్కువ బుకింగ్‌లు ఉన్న, పరిశీలించాల్సిన వార్డులు", search: "వార్డును వెతకండి", close: "మూసివేయి", needTitle: "అవసరం (2011 జనగణన)", wad: "ఆవరణ బయటి నుంచి నీరు తెచ్చుకునే కుటుంబాలు", cad: "ఫోన్ లేని కుటుంబాలు (ట్యాంకర్ బుక్ చేయలేరు)", hardship: "కష్టాల్లో ఉన్న కుటుంబాలు", households: "కుటుంబాలు", nowTitle: "ఈరోజు హెచ్చరిక సూచనలు", nowNote: "ఈ 4 సూచనల్లో {n} లేదా ఎక్కువ చెడుగా ఉంటే మ్యాప్‌లో ఎరుపు. డేటా ఇంకా నమోదు కాని సూచనలు బూడిద రంగులో.", growthTitle: "పెరుగుదల", growth: "2016 నుంచి భవనాలు {p} పెరిగాయి", noGrowth: "భవనాల పెరుగుదల తెలియదు", facilities: "మ్యాప్‌లో ఉన్న ఆసుపత్రులు, క్లినిక్‌లు, పాఠశాలలు", owedBad: "{v} ట్యాంకర్ లోడ్లు బాకీ", owedOk: "నీటి బాకీ లేదు", bookBad: "{d} రోజుల్లో {v} బుకింగ్‌లు (సాధారణ నెల: {r})", bookOk: "{d} రోజుల్లో {v} బుకింగ్‌లు (సాధారణ నెల: {r})", bookUnknown: "బుకింగ్‌లు: ఇంకా నమోదు కాలేదు", compBad: "ఈ వారం {v} \"నీరు రాలేదు\" ఫిర్యాదులు", compOk: "ఈ వారం {v} \"నీరు రాలేదు\" ఫిర్యాదులు", cutsBad: "ఈ వారం {v} సరఫరా నిలిపివేతలు", cutsOk: "ఈ వారం సరఫరా నిలిపివేతలు లేవు", gwBad: "భూగర్భ జలం సాధారణం కంటే {v} మీ. తక్కువ: బోర్లు ఎండిపోవచ్చు", gwOk: "భూగర్భ జలం దాదాపు సాధారణ స్థాయిలో ({v} మీ.)", gwUnknown: "సమీపంలో భూగర్భ జల బావులు లేవు", checkTitle: "బుకింగ్ పరిశీలన", checkBooked: "2025లో {v} ట్యాంకర్లు బుక్ చేశారు", checkPeer: "5 ఇలాంటి వార్డులు సుమారు {v} బుక్ చేశాయి", checkModel: "గణాంక నమూనా (కుటుంబాలు, అవసరం) సుమారు {v} అంచనా వేసింది", checkFlag: "అంచనా కంటే చాలా తక్కువ: ప్రజలు బుక్ చేయగలరా అని పరిశీలనకు ఒకరిని పంపండి.", checkOk: "అంచనా కంటే కొంచెం తక్కువ, కానీ గుర్తించేంత తక్కువ కాదు.", checkNone: "ఈ వార్డును పరిశీలించేందుకు తగిన డేటా లేదు.", topShare: "పై {n} ప్రాంతాలు మొత్తం ట్యాంకర్లలో {p} తీసుకుంటున్నాయి", gini: "బుకింగ్ కేంద్రీకరణ", giniHigh: "చాలా అసమానం", giniMid: "అసమానం", giniLow: "దాదాపు సమానం", sourceLive: "గత {d} రోజులు, {n} ప్రత్యక్ష బుకింగ్‌లు", sourceHistory: "2022–24 బుకింగ్‌లు (ఇంకా ప్రత్యక్ష బుకింగ్‌లు లేవు)", topList: "అత్యధిక బుకింగ్ ప్రాంతాలు", bookingsLayer: "నెలకు బుకింగ్‌లు", checksIntro: "ఈ వార్డులు ఇలాంటి వార్డుల కంటే, మా నమూనా అంచనా కంటే చాలా తక్కువ ట్యాంకర్లు బుక్ చేశాయి. తక్కువ బుకింగ్ అంటే నీరు ఉందని కాదు; ప్రజలు బుక్ చేయలేకపోవచ్చు (ఫోన్, ఖాతా లేకపోవడం). ఏదైనా మార్చే ముందు క్షేత్రస్థాయిలో పరిశీలించండి.", openWard: "మ్యాప్‌లో తెరవండి", more: "ఎక్కువ", less: "తక్కువ", unknownLegend: "డేటా లేదు", searchEmpty: "వార్డు దొరకలేదు" },
  ur: { needScore: "پانی کی ضرورت کا اسکور", needHelp: "مردم شماری سے ہر وارڈ کا ایک اسکور: 1 + 2 x باہر سے پانی لانے والے گھر + بغیر فون کے گھر + مشکل حالات۔ یہی اسکور منصفانہ قطار ٹینکر بانٹنے میں استعمال کرتی ہے۔", layerNeed: "پانی کی ضرورت", layerHouseholds: "گھرانے", layerHardship: "مشکل حالات", stepChecks: "وہ وارڈ جنہوں نے اسی ضرورت والے ملتے جلتے وارڈوں سے بہت کم ٹینکر بک کیے: کسی کو بھیج کر دیکھیں کہ لوگ بک کر سکتے ہیں یا نہیں۔", stepBookings: "HMWSSB کے ٹینکر اصل میں کہاں جاتے ہیں: علاقے کے لحاظ سے بکنگ، اور وہ کتنی مرکوز ہیں۔", stepNeed: "کن وارڈوں کو پانی کی سب سے زیادہ ضرورت ہے: باہر سے پانی لانے والے گھر، بغیر فون کے گھر، مشکل حالات، گھرانوں کی تعداد (مردم شماری 2011)۔", signs: "4 میں سے {n} اشارے", growthNote: "حروفِ تہجی کی ترتیب، درجہ بندی نہیں: عمارتیں گھرانے نہیں، اس لیے اضافے سے وارڈوں کی درجہ بندی نہیں کی جاتی۔", showLess: "پہلے 15 دکھائیں", showAll: "تمام وارڈ دکھائیں", rankTitle: "تمام وارڈ: {layer}", owedUnknown: "واجب الادا پانی: ابھی کوئی دن ترسیل کے ساتھ بند نہیں ہوا", bgTitle: "پس منظر", checkMore: "اندازے سے زیادہ بک کیے: کم بکنگ کا معاملہ نہیں۔", zoomIn: "قریب کریں", zoomOut: "دور کریں", zoomReset: "نقشہ فٹ کریں", risingHelp: "اشارے: واجب الادا پانی، بکنگ میں اچانک اضافہ، \"پانی نہیں\" شکایات، سپلائی بندش۔", title: "پانی کی ضرورت کا نقشہ", intro: "کہاں پانی نہیں، کہاں ضرورت بڑھ رہی ہے، اور کہاں بکنگ بہت کم ہے۔ تفصیل کے لیے وارڈ پر کلک کریں۔", tabNeed: "1. ضرورت", tabBookings: "2. بکنگ", tabChecks: "3. اندازہ بمقابلہ اصل", layerRising: "آج کے انتباہی اشارے", layerWad: "باہر سے پانی لانے والے", layerCad: "بکنگ کے لیے فون نہیں", layerGrowth: "عمارتوں میں اضافہ", signIn: "آج کے براہِ راست اشارے دیکھنے کے لیے افسر کے طور پر سائن ان کریں۔ محفوظ ڈیٹا دکھایا جا رہا ہے۔", rising: "2 یا زیادہ انتباہی اشارے", oneSign: "1 انتباہی اشارہ", calm: "کوئی انتباہی اشارہ نہیں", noLive: "ابھی براہِ راست ڈیٹا نہیں", wardsRising: "2 یا زیادہ انتباہی اشاروں والے وارڈ", wardsChecked: "کم بکنگ والے وارڈ جن کی جانچ ہونی ہے", search: "وارڈ تلاش کریں", close: "بند کریں", needTitle: "ضرورت (مردم شماری 2011)", wad: "گھر جو احاطے کے باہر سے پانی لاتے ہیں", cad: "گھر جن کے پاس فون نہیں (ٹینکر بک نہیں کر سکتے)", hardship: "مشکل حالات والے گھر", households: "گھرانے", nowTitle: "آج کے انتباہی اشارے", nowNote: "جب ان 4 میں سے {n} یا زیادہ اشارے خراب ہوں تو نقشے پر سرخ۔ جن اشاروں کا ڈیٹا ابھی درج نہیں وہ سرمئی ہیں۔", growthTitle: "اضافہ", growth: "2016 سے عمارتوں میں {p} اضافہ", noGrowth: "عمارتوں کا اضافہ معلوم نہیں", facilities: "نقشے پر ہسپتال، کلینک اور اسکول", owedBad: "{v} ٹینکر لوڈ واجب الادا", owedOk: "کوئی پانی واجب الادا نہیں", bookBad: "{d} دن میں {v} بکنگ (عام مہینہ: {r})", bookOk: "{d} دن میں {v} بکنگ (عام مہینہ: {r})", bookUnknown: "بکنگ: ابھی درج نہیں", compBad: "اس ہفتے {v} \"پانی نہیں\" شکایات", compOk: "اس ہفتے {v} \"پانی نہیں\" شکایات", cutsBad: "اس ہفتے {v} سپلائی بندش", cutsOk: "اس ہفتے کوئی سپلائی بندش نہیں", gwBad: "زیرِ زمین پانی معمول سے {v} میٹر کم: بورویل سوکھ سکتے ہیں", gwOk: "زیرِ زمین پانی تقریباً معمول پر ({v} میٹر)", gwUnknown: "قریب کوئی زیرِ زمین پانی کا کنواں نہیں", checkTitle: "بکنگ کی جانچ", checkBooked: "2025 میں {v} ٹینکر بک کیے", checkPeer: "5 ملتے جلتے وارڈوں نے تقریباً {v} بک کیے", checkModel: "شماریاتی ماڈل (گھر اور ضرورت) کا اندازہ تقریباً {v}", checkFlag: "اندازے سے بہت کم: کسی کو بھیج کر دیکھیں کہ لوگ بک کر سکتے ہیں یا نہیں۔", checkOk: "اندازے سے کچھ کم، مگر نشان زد کرنے جتنا کم نہیں۔", checkNone: "اس وارڈ کی جانچ کے لیے کافی ڈیٹا نہیں۔", topShare: "سب سے اوپر کے {n} علاقے کل ٹینکروں کا {p} لیتے ہیں", gini: "بکنگ کا ارتکاز", giniHigh: "بہت غیر مساوی", giniMid: "غیر مساوی", giniLow: "تقریباً مساوی", sourceLive: "پچھلے {d} دن، {n} براہِ راست بکنگ", sourceHistory: "2022–24 کی بکنگ (ابھی کوئی براہِ راست بکنگ نہیں)", topList: "سب سے مصروف علاقے", bookingsLayer: "ماہانہ بکنگ", checksIntro: "ان وارڈوں نے ملتے جلتے وارڈوں اور ہمارے ماڈل کے اندازے سے بہت کم ٹینکر بک کیے۔ کم بکنگ کا مطلب یہ ہو سکتا ہے کہ لوگ بک نہیں کر پاتے (فون یا اکاؤنٹ نہیں)، یہ نہیں کہ ان کے پاس پانی ہے۔ کچھ بدلنے سے پہلے موقع پر جانچ کریں۔", openWard: "نقشے پر کھولیں", more: "زیادہ", less: "کم", unknownLegend: "ڈیٹا نہیں", searchEmpty: "کوئی وارڈ نہیں ملا" },
  hi: { needScore: "पानी की ज़रूरत का स्कोर", needHelp: "जनगणना से हर वार्ड का एक स्कोर: 1 + 2 x बाहर से पानी लाने वाले घर + बिना फ़ोन के घर + कठिनाई। यही स्कोर निष्पक्ष कतार टैंकर बाँटने में इस्तेमाल करती है।", layerNeed: "पानी की ज़रूरत", layerHouseholds: "परिवार", layerHardship: "कठिनाई", stepChecks: "वे वार्ड जिन्होंने उसी ज़रूरत वाले मिलते-जुलते वार्डों से बहुत कम टैंकर बुक किए: किसी को भेजकर देखें कि लोग बुक कर पाते हैं या नहीं।", stepBookings: "HMWSSB के टैंकर असल में कहाँ जाते हैं: इलाकेवार बुकिंग, और वे कितनी केंद्रित हैं।", stepNeed: "किन वार्डों को पानी की सबसे ज़्यादा ज़रूरत है: बाहर से पानी लाने वाले घर, बिना फ़ोन के घर, कठिनाई, परिवारों की संख्या (जनगणना 2011)।", signs: "4 में से {n} संकेत", growthNote: "वर्णक्रम में, रैंक नहीं: इमारतें परिवार नहीं हैं, इसलिए बढ़ोतरी से वार्डों की रैंकिंग नहीं होती।", showLess: "शीर्ष 15 दिखाएँ", showAll: "सभी वार्ड दिखाएँ", rankTitle: "सभी वार्ड: {layer}", owedUnknown: "बकाया पानी: अभी कोई दिन डिलीवरी के साथ बंद नहीं हुआ", bgTitle: "पृष्ठभूमि", checkMore: "अनुमान से ज़्यादा बुक किए: कम बुकिंग का मामला नहीं।", zoomIn: "पास करें", zoomOut: "दूर करें", zoomReset: "नक्शा फ़िट करें", risingHelp: "संकेत: बकाया पानी, बुकिंग में उछाल, \"पानी नहीं\" शिकायतें, आपूर्ति बंद।", title: "पानी की ज़रूरत का नक्शा", intro: "कहाँ पानी नहीं है, कहाँ ज़रूरत बढ़ रही है, और कहाँ बुकिंग बहुत कम है। विवरण के लिए वार्ड पर क्लिक करें।", tabNeed: "1. ज़रूरत", tabBookings: "2. बुकिंग", tabChecks: "3. अनुमान बनाम असल", layerRising: "आज के चेतावनी संकेत", layerWad: "बाहर से पानी लाने वाले", layerCad: "बुकिंग के लिए फ़ोन नहीं", layerGrowth: "इमारतों में बढ़ोतरी", signIn: "आज के लाइव संकेत देखने के लिए अधिकारी के रूप में साइन इन करें। सहेजा हुआ डेटा दिखाया जा रहा है।", rising: "2 या अधिक चेतावनी संकेत", oneSign: "1 चेतावनी संकेत", calm: "कोई चेतावनी संकेत नहीं", noLive: "अभी लाइव डेटा नहीं", wardsRising: "2 या अधिक चेतावनी संकेत वाले वार्ड", wardsChecked: "कम बुकिंग वाले वार्ड जिनकी जाँच करनी है", search: "वार्ड खोजें", close: "बंद करें", needTitle: "ज़रूरत (जनगणना 2011)", wad: "घर जो परिसर के बाहर से पानी लाते हैं", cad: "घर जिनके पास फ़ोन नहीं (टैंकर बुक नहीं कर सकते)", hardship: "कठिनाई वाले घर", households: "परिवार", nowTitle: "आज के चेतावनी संकेत", nowNote: "इन 4 में से {n} या अधिक संकेत खराब हों तो नक्शे पर लाल। जिन संकेतों का डेटा अभी दर्ज नहीं, वे धूसर हैं।", growthTitle: "बढ़ोतरी", growth: "2016 से इमारतें {p} बढ़ीं", noGrowth: "इमारतों की बढ़ोतरी अज्ञात", facilities: "नक्शे पर अस्पताल, क्लिनिक और स्कूल", owedBad: "{v} टैंकर लोड बकाया", owedOk: "कोई पानी बकाया नहीं", bookBad: "{d} दिनों में {v} बुकिंग (सामान्य महीना: {r})", bookOk: "{d} दिनों में {v} बुकिंग (सामान्य महीना: {r})", bookUnknown: "बुकिंग: अभी दर्ज नहीं", compBad: "इस हफ़्ते {v} \"पानी नहीं\" शिकायतें", compOk: "इस हफ़्ते {v} \"पानी नहीं\" शिकायतें", cutsBad: "इस हफ़्ते {v} आपूर्ति बंद", cutsOk: "इस हफ़्ते कोई आपूर्ति बंद नहीं", gwBad: "भूजल सामान्य से {v} मी. नीचे: बोरवेल सूख सकते हैं", gwOk: "भूजल लगभग सामान्य स्तर पर ({v} मी.)", gwUnknown: "पास में भूजल कुआँ नहीं", checkTitle: "बुकिंग जाँच", checkBooked: "2025 में {v} टैंकर बुक किए", checkPeer: "5 मिलते-जुलते वार्डों ने लगभग {v} बुक किए", checkModel: "सांख्यिकीय मॉडल (घर और ज़रूरत) का अनुमान लगभग {v}", checkFlag: "अनुमान से बहुत कम: किसी को भेजकर देखें कि लोग बुक कर पाते हैं या नहीं।", checkOk: "अनुमान से थोड़ा कम, पर चिह्नित करने जितना कम नहीं।", checkNone: "इस वार्ड की जाँच के लिए पर्याप्त डेटा नहीं।", topShare: "शीर्ष {n} इलाके कुल टैंकरों का {p} लेते हैं", gini: "बुकिंग संकेंद्रण", giniHigh: "बहुत असमान", giniMid: "असमान", giniLow: "लगभग समान", sourceLive: "पिछले {d} दिन, {n} लाइव बुकिंग", sourceHistory: "2022–24 की बुकिंग (अभी कोई लाइव बुकिंग नहीं)", topList: "सबसे व्यस्त इलाके", bookingsLayer: "प्रति माह बुकिंग", checksIntro: "इन वार्डों ने मिलते-जुलते वार्डों और हमारे मॉडल के अनुमान से बहुत कम टैंकर बुक किए। कम बुकिंग का मतलब हो सकता है कि लोग बुक नहीं कर पाते (फ़ोन या खाता नहीं), यह नहीं कि उनके पास पानी है। कुछ बदलने से पहले मौके पर जाँच करें।", openWard: "नक्शे पर खोलें", more: "अधिक", less: "कम", unknownLegend: "डेटा नहीं", searchEmpty: "कोई वार्ड नहीं मिला" },
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
  const [unit, setUnit] = useState<"sections" | "wards">("sections");
  const bySection = unit === "sections";
  const w = useMemo(() => {
    const base = { ...copy[locale], ...sectionCopy[locale], ...outcomeCopy[locale] };
    if (!bySection || locale !== "en") return base;
    // The section screen says "section" where the ward screen says "ward" (English only for now).
    const words = Object.fromEntries(Object.entries(base).map(([k, v]) => [k, v.replace(/\bwards\b/g, "sections").replace(/\bWards\b/g, "Sections").replace(/\bward\b/g, "section").replace(/\bWard\b/g, "Section")])) as typeof base;
    return { ...words, households: "Domestic connections", needTitle: "Need (Census 2011, estimated for this area)" };
  }, [locale, bySection]);
  const nf = useMemo(() => new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { maximumFractionDigits: 1 }), [locale]);
  const pf = useMemo(() => new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { style: "percent", maximumFractionDigits: 0 }), [locale]);
  const fmt = (n: number) => nf.format(n);
  const pct = (n: number | null | undefined) => (n === null || n === undefined ? "—" : pf.format(n));
  const [tab, setTab] = useState<Tab>("need");
  const [layer, setLayer] = useState<Layer>("rising");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  // Live data needs an officer token; signed out the screen shows the saved snapshot.
  const { status } = useAuth();
  const enabled = status !== "anonymous" && status !== "rejected";
  const wardLive = enabled && !bySection; // the ward answers are not needed on the section screen
  const atlas = useApi<unknown>(wardLive ? "/atlas/wards" + PAGE : null);
  const equityWards = useApi<unknown>(wardLive ? "/equity/wards" + PAGE : null);
  const equitySummary = useApi<unknown>(wardLive ? "/equity/summary" : null);
  const fieldChecks = useApi<unknown>(wardLive ? "/underserved/field-checks" + PAGE : null);
  const sectionApi = useApi<unknown>(enabled ? "/underserved/section-checks" + PAGE : null);
  const checkedSectionsApi = useApi<unknown>(enabled ? "/field-checks/sections" + PAGE : null);
  // Every section's booking check comes from the section-checks list (live, else the saved
  // snapshot); the field-check list holds only the flagged sections, so it adds their latest visit
  // outcome and never replaces the full list (else unflagged sections lose their booking check).
  const allSectionRows = (sectionApi.live ? adaptSectionChecks(sectionApi.data) : null) ?? adaptSectionChecks(savedSections) ?? [];
  const visited = checkedSectionsApi.live ? adaptSectionChecks(checkedSectionsApi.data) : null;
  const visitOf = new Map((visited ?? []).map((r) => [r.section_id, r.latest_outcome]));
  const sectionRows = allSectionRows.length ? allSectionRows.map((r) => ({ ...r, latest_outcome: visitOf.get(r.section_id) ?? r.latest_outcome })) : visited ?? [];
  const layerGeo = useApi<unknown>(wardLive ? "/coverage/layers/water_access_evidence" : null);
  const liveNeedApi = useApi<unknown>(enabled ? (bySection ? "/atlas/live-sections" : "/atlas/live") : null);
  const weeklyApi = useApi<{ items: WeeklyRow[] }>(enabled && bySection ? "/field-checks/weekly-priority" : null);
  const weekly = new Map((Array.isArray(weeklyApi.data?.items) ? weeklyApi.data.items : []).map(r => [r.section_id, r]));
  const sources = [atlas, equityWards, equitySummary, fieldChecks, layerGeo];
  const allLive = sources.every((s) => s.live);
  const live = useMemo(() => (allLive ? adaptLiveEvidence({ atlas: atlas.data, equityWards: equityWards.data, equitySummary: equitySummary.data, fieldChecks: fieldChecks.data, layer: layerGeo.data }) : null), [allLive, atlas.data, equityWards.data, equitySummary.data, fieldChecks.data, layerGeo.data]);
  const need = useMemo(() => (liveNeedApi.live ? adaptLiveNeed(liveNeedApi.data) : null), [liveNeedApi.live, liveNeedApi.data]);
  // Why there are no live signs: signed out, still loading, an old server, or an error (not always "sign in").
  const noLive = !enabled || need ? w.signIn
    : liveNeedApi.loading ? "Checking for live signs…"
    : liveNeedApi.error?.status === 404 ? "This server has no live signs for sections yet. Restart the API from the section branch. Showing saved data."
    : liveNeedApi.error ? `Live signs could not be loaded (${liveNeedApi.error.status === 0 ? "server not reachable" : "server error " + liveNeedApi.error.status}). Showing saved data.`
    : adaptLiveNeed(liveNeedApi.data) === null ? "The server's live signs answer was incomplete. Showing saved data."
    : w.signIn;

  const dataset = bySection ? sectionSnapshot : live?.dataset ?? snapshot;
  const features = bySection ? sectionFeatures : live?.features ?? snapshotFeatures;
  const rows = dataset.wards;
  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const liveOf = (id: string): LiveWard | undefined => need?.wards.get(id);
  const conc = need?.concentration ?? null;
  // Without live data the live layer has nothing to show: fall back to the Census layer.
  const shown: Layer = layer === "rising" && !need ? "wad" : layer === "current" && !bySection ? "need" : layer;
  const usualMonth = (r: Ward) => (r.bookings === null ? null : r.bookings / 25);
  const bookingsOf = (r: Ward) => (conc?.source === "live" ? liveOf(r.id)?.bookingsWindow ?? 0 : usualMonth(r));

  // Map: equirectangular projection corrected for latitude, so wards keep their shape.
  const shapes = useMemo(() => features.flatMap((f) => (byId.has(f.properties.ward_id) ? [{ id: f.properties.ward_id, rings: rings(f) }] : [])), [features, byId]);
  const base = useMemo(() => (bySection ? snapshotFeatures.map((f) => ({ id: f.properties.ward_id, rings: rings(f) })) : []), [bySection]);
  const view = useMemo(() => {
    const all = [...shapes, ...base].flatMap((s) => s.rings.flat());
    const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
    const width = 1000, height = Math.round((width * (maxY - minY)) / ((maxX - minX) * k));
    const project = ([x, y]: Position) => `${(((x - minX) / (maxX - minX)) * width).toFixed(1)},${(((maxY - y) / (maxY - minY)) * height).toFixed(1)}`;
    return { width, height, project, base: base.map((s) => s.rings.map((r) => "M" + r.map(project).join("L") + "Z").join("")), paths: new Map(shapes.map((s) => [s.id, s.rings.map((r) => "M" + r.map(project).join("L") + "Z").join("")])) };
  }, [shapes, base]);

  // Zoom by the + / - buttons only (no wheel or drag, so the map box never changes size):
  // towards the selected ward, else the centre of the current view.
  const [zoom, setZoom] = useState<{ x: number; y: number; w: number } | null>(null);
  const full = view.width + 20, fullH = view.height + 20;
  const box = zoom ?? { x: -10, y: -10, w: full };
  const boxH = (box.w * fullH) / full;
  const centre = (): [number, number] => {
    const d = selectedId ? view.paths.get(selectedId) : undefined;
    const nums = d ? (d.match(/-?\d+(\.\d+)?/g) ?? []).map(Number) : [];
    if (nums.length < 2) return [box.x + box.w / 2, box.y + boxH / 2];
    const xs = nums.filter((_, i) => i % 2 === 0), ys = nums.filter((_, i) => i % 2 === 1);
    return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  };
  const zoomBy = (factor: number) => {
    const w2 = Math.min(full, Math.max(80, box.w * factor));
    if (w2 >= full) { setZoom(null); return; }
    const h2 = (w2 * fullH) / full;
    const [cx, cy] = centre();
    setZoom({ x: Math.min(Math.max(cx - w2 / 2, -10), full - 10 - w2), y: Math.min(Math.max(cy - h2 / 2, -10), fullH - 10 - h2), w: w2 });
  };
  const pick = (id: string) => setSelectedId(id);

  const metric = (r: Ward): number | null =>
    tab === "bookings" ? bookingsOf(r) : shown === "current" ? (weekly.get(r.id)?.status === "UNKNOWN" ? null : weekly.get(r.id)?.current_need_weight ?? null) : shown === "wad" ? r.waterAccessDeficitShare : shown === "cad" ? r.constrainedAccessShare ?? null : shown === "need" ? liveOf(r.id)?.needWeight ?? r.needWeight ?? savedNeed.get(r.id) ?? null : shown === "growth" ? (r.growthRatio === null ? null : r.growthRatio - 1) : null;
  const scale = useMemo(() => classes(rows.map(metric)), [rows, tab, shown, conc, weeklyApi.data]); // eslint-disable-line react-hooks/exhaustive-deps
  function colour(r: Ward) {
    if (tab === "checks") return bySection && r.fieldCandidate ? "#c9783f" : NO_DATA;
    if (tab === "need" && shown === "rising") {
      const l = liveOf(r.id);
      if (!l || l.knownCount === 0) return NO_DATA;
      return l.rising ? "#c4473a" : l.badCount === 1 ? "#e3a64a" : "#9fd0b8";
    }
    const c = scale.of(metric(r));
    return c === null ? NO_DATA : SCALE[c];
  }

  const rising = rows.filter((r) => liveOf(r.id)?.rising).length;
  const checks = sectionRows.filter((r) => r.field_check_candidate).sort((a, b) => (a.rate ?? 0) / (a.reference_rate || 1) - (b.rate ?? 0) / (b.reference_rate || 1));
  const selectedSection = checks.find((r) => r.section_id === selectedSectionId);
  const found = query.trim() ? rows.filter((r) => r.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];
  const legendScale = tab !== "checks" && (tab === "bookings" || shown !== "rising");

  // Ranked list under the map for the layer on screen (building growth is listed A-Z: design doc F2
  // says growth must not rank areas).
  const growthList = tab === "need" && shown === "growth";
  const rankValue = (r: Ward): number | null => {
    if (tab === "need" && shown === "rising") { const l = liveOf(r.id); return l && l.knownCount > 0 ? l.badCount : null; }
    return metric(r);
  };
  const ranked = rows.map((r) => ({ r, v: rankValue(r) })).sort((a, b) =>
    growthList ? a.r.name.localeCompare(b.r.name) : (b.v ?? -Infinity) - (a.v ?? -Infinity) || a.r.name.localeCompare(b.r.name));
  const rankText = (v: number | null) => v === null ? "—" : tab === "bookings" ? fmt(Math.round(v)) : (shown === "need" || shown === "current") ? v.toFixed(2) : shown === "rising" ? fill(w.signs, { n: v }) : pct(v);
  const layerName = shown === "current" ? weeklyCopy[locale].title : tab === "bookings" ? w.bookingsLayer : shown === "rising" ? w.layerRising : shown === "wad" ? w.layerWad : shown === "cad" ? w.layerCad : shown === "need" ? w.layerNeed : w.layerGrowth;

  const unitToggle = (
    <div className="atlas-tabs atlas-unit" role="tablist" aria-label="Map by">
      {(["sections", "wards"] as const).map((u) => <button key={u} role="tab" aria-selected={unit === u} className={unit === u ? "active" : ""} onClick={() => { setUnit(u); setSelectedId(null); setSelectedSectionId(null); }}>{u === "sections" ? "Sections" : "Wards"}</button>)}
    </div>
  );

  return (
    <div className="atlas-page">
      {unitToggle}
      <header className="atlas-head">
        <div><h1>{w.title}</h1><p className="muted">{need ? w.intro : noLive}</p></div>
        <div className="atlas-search">
          <input aria-label={w.search} placeholder={w.search} value={query} onChange={(e) => setQuery(e.target.value)} />
          {query.trim() && <ul>{found.length ? found.map((r) => <li key={r.id}><button onClick={() => { setSelectedId(r.id); setQuery(""); }}>{r.name}</button></li>) : <li className="muted">{w.searchEmpty}</li>}</ul>}
        </div>
      </header>

      <div className="atlas-tabs" role="tablist">
        {(["need", "bookings", "checks"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t === "need" ? w.tabNeed : t === "bookings" ? w.tabBookings : w.tabChecks}</button>)}
      </div>

      <p className="atlas-step">{tab === "need" ? w.stepNeed : tab === "bookings" ? w.stepBookings : w.stepChecks}</p>
        <div className="atlas-toolbar">
        {tab === "need" && <div className="atlas-chips" role="radiogroup">{(["current", "rising", "need", "wad", "cad", "growth"] as const).filter(l => l !== "current" || bySection).map((l) => <button key={l} role="radio" aria-checked={shown === l} className={shown === l ? "active" : ""} disabled={l === "rising" && !need} title={l === "rising" && !need ? w.signIn : undefined} onClick={() => setLayer(l)}>{l === "current" ? weeklyCopy[locale].title : l === "rising" ? w.layerRising : l === "wad" ? w.layerWad : l === "cad" ? w.layerCad : l === "need" ? w.layerNeed : w.layerGrowth}</button>)}</div>}
        {tab === "need" && shown === "rising" && <p className="atlas-help">{w.risingHelp}</p>}
        {tab === "need" && shown === "current" && <p className="atlas-help">{weeklyCopy[locale].intro}</p>}
        {tab === "need" && shown === "need" && <p className="atlas-help">{w.needHelp}</p>}
        {tab === "need" && shown === "rising" && need && <p className="atlas-stat"><strong>{fmt(rising)}</strong> {w.wardsRising}</p>}
        {tab === "bookings" && conc && <div className="atlas-stat-card">
          <p className="atlas-big">{fill(w.topShare, { n: fmt(conc.topSections), p: pct(conc.topShare) })}</p>
          <p>{w.gini}: <strong>{conc.gini === null ? "—" : conc.gini >= 0.6 ? w.giniHigh : conc.gini >= 0.35 ? w.giniMid : w.giniLow}</strong> ({conc.gini?.toFixed(2) ?? "—"})</p>
          <p className="muted">{conc.source === "live" ? fill(w.sourceLive, { d: need?.windowDays ?? 30, n: fmt(conc.liveBookings) }) : w.sourceHistory}</p>
        </div>}
        {tab === "bookings" && !conc && <div className="atlas-stat-card"><p className="atlas-big">{fill(w.topShare, { n: fmt(dataset.summary.equity.top_section_count), p: pct(dataset.summary.equity.top_booking_share) })}</p><p className="muted">{w.sourceHistory}</p></div>}
        {tab === "checks" && <p className="atlas-stat"><strong>{fmt(checks.length)}</strong> {w.wardsChecked}</p>}
      </div>
      <section className="atlas-stage">
        <svg className="atlas-map" viewBox={`${box.x} ${box.y} ${box.w} ${boxH}`} role="group" aria-label={w.title}>
          {view.base.map((d, i) => <path key={"b" + i} d={d} className="atlas-base" fill="#f1f3f0" pointerEvents="none" />)}
          {rows.map((r) => {
            const d = view.paths.get(r.id);
            if (!d) return null;
            return <path key={r.id} d={d} fill={colour(r)} className={(selectedId === r.id ? "selected " : "") + (hover === r.id ? "hover" : "")} tabIndex={0} role="button" aria-label={r.name}
              onClick={() => pick(r.id)} onMouseEnter={() => setHover(r.id)} onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedId(r.id); } }}><title>{r.name}</title></path>;
          })}
          {tab === "checks" && !bySection && checks.filter((r) => r.lat !== null && r.lng !== null).map((r) => {
            const [cx, cy] = view.project([r.lng!, r.lat!]).split(",");
            return <g key={r.section_id}><circle cx={cx} cy={cy} r={selectedSectionId === r.section_id ? 8 : 5} fill={selectedSectionId === r.section_id ? "#76390e" : "#c9783f"} stroke="#fff" tabIndex={0} role="button" aria-label={r.section} aria-pressed={selectedSectionId === r.section_id}
              onClick={() => { setSelectedSectionId(r.section_id); setSelectedId(null); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedSectionId(r.section_id); setSelectedId(null); } }}><title>{r.section}</title></circle>{selectedSectionId === r.section_id && <text className="atlas-section-label" x={Number(cx) + 12} y={Number(cy) - 10}>{r.section}</text>}</g>;
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
        {tab === "checks" && selectedSection && <aside className="atlas-overlay atlas-section-detail" role="region" aria-label={selectedSection.section}>
          <header><h3>{selectedSection.section}</h3><button className="atlas-close" aria-label={w.close} onClick={() => setSelectedSectionId(null)}>×</button></header>
          <SectionRates section={selectedSection} w={w} fmt={fmt} rich={locale === "en"} />
          <p className="atlas-verdict flag">{w.stepChecks}</p>
        </aside>}
      </section>

      {tab !== "checks" && <section className="atlas-rank">
        <h2>{fill(w.rankTitle, { layer: layerName })}</h2>
        {growthList && <p className="muted small">{w.growthNote}</p>}
        <ol>{(showAll ? ranked : ranked.slice(0, 15)).map(({ r, v }, i) => <li key={r.id}><button className={selectedId === r.id ? "active" : ""} onClick={() => setSelectedId(r.id)}><span className="atlas-rank-n">{growthList ? "" : i + 1}</span><span className="atlas-rank-name">{r.name}</span><strong>{rankText(v)}</strong></button></li>)}</ol>
        <button className="text-button" onClick={() => setShowAll(!showAll)}>{showAll ? w.showLess : w.showAll}</button>
      </section>}

      {tab === "checks" && <section className="atlas-checks">
        <p className="atlas-explain">{w.checksIntro}</p>
        <p className="muted">{sectionApi.live && adaptSectionChecks(sectionApi.data) ? w.sectionLive : w.sectionSnapshot}</p>
        {checks.length === 0 && <p>{w.emptyChecks}</p>}
        <div className="atlas-check-grid">{checks.map((r) => <article key={r.section_id} className="atlas-check-card">
          <h3>{r.section}</h3>
          <SectionRates section={r} w={w} fmt={fmt} rich={locale === "en"} />
          {(bySection || r.ward_id) && <button className="text-button" onClick={() => setSelectedId(bySection ? r.section_id : r.ward_id)}>{w.openWard}</button>}
        </article>)}</div>
        <SectionOutcomeForm onSaved={() => { checkedSectionsApi.reload(); weeklyApi.reload(); }} />
      </section>}

      {selected && <WardSheet ward={selected} sections={bySection ? sectionRows.filter((r) => r.section_id === selected.id) : checks.filter((r) => r.ward_id === selected.id)} live={liveOf(selected.id)} noLive={noLive} days={need?.windowDays ?? 30} minBad={need?.minBad ?? 2} w={w} fmt={fmt} pct={pct} rich={locale === "en"} onSupplySaved={weeklyApi.reload} onClose={() => setSelectedId(null)} />}
    </div>
  );
}

function SectionRates({ section, w, fmt, rich }: { section: SectionCheck; w: SectionWords; fmt: (n: number) => string; rich: boolean }) {
  const outcome = <p className="muted">{section.latest_outcome ? `${section.latest_outcome.checked_on} · ${section.latest_outcome.could_not_book === "yes" ? w.checkedYes : section.latest_outcome.could_not_book === "no" ? w.checkedNo : w.checkedUnclear}` : w.unchecked}</p>;
  const expected = section.reference_rate !== null && section.domestic_connections ? Math.round((section.reference_rate * section.domestic_connections) / 1000) : null;
  if (!rich || expected === null) return <div className="atlas-bars">
    <p>{fill(w.checkBooked, { v: fmt(section.bookings) })}</p>
    <p>{fill(w.sectionRate, { v: section.rate === null ? "—" : fmt(section.rate) })}</p>
    <p>{fill(w.sectionPeer, { v: section.reference_rate === null ? "—" : fmt(section.reference_rate) })}</p>
    {outcome}
  </div>;
  // Same look as the ward booking check: what the section booked, what similar sections would
  // have booked with its connections, and a plain verdict. Bars share one scale.
  const top = Math.max(section.bookings, expected, 1);
  const share = section.ratio ?? (expected ? section.bookings / expected : null);
  const verdict = section.field_check_candidate ? { tone: "flag", text: `Far lower than similar sections (${fmt(Math.round((share ?? 0) * 100))}% of what they book) in an area with high water need: worth a visit to check whether people can book.` }
    : share !== null && share < 0.5 ? { tone: "", text: `Lower than similar sections (${fmt(Math.round(share * 100))}%), but not flagged: the area's need is not above the cohort's.` }
    : share !== null && share < 0.9 ? { tone: "", text: "A bit lower than similar sections, but not low enough to flag." }
    : share !== null && share <= 1.5 ? { tone: "", text: "In line with similar sections." }
    : { tone: "", text: "More bookings than similar sections." };
  return <div className="atlas-bars">
    <p>Booked {fmt(section.bookings)} tankers in 2025</p>
    <div className="atlas-bar"><i className="seen" style={{ width: `${Math.max(1, (section.bookings / top) * 100)}%` }} /></div>
    <p>Similar sections booked about {fmt(expected)} for this many connections</p>
    <div className="atlas-bar"><i className="peer" style={{ width: `${Math.max(1, (expected / top) * 100)}%` }} /></div>
    <p className={"atlas-verdict " + verdict.tone}>{verdict.text}</p>
    {outcome}
  </div>;
}

type SectionWords = Words & Record<keyof typeof sectionCopy.en | keyof typeof outcomeCopy.en, string>;
function WardSheet({ ward, sections, live, noLive, days, minBad, w, fmt, pct, rich, onSupplySaved, onClose }: { onSupplySaved: () => void; rich: boolean; ward: Ward; sections: SectionCheck[]; live: LiveWard | undefined; noLive: string; days: number; minBad: number; w: SectionWords; fmt: (n: number) => string; pct: (n: number | null | undefined) => string; onClose: () => void }) {
  const status = !live || live.knownCount === 0 ? w.noLive : live.rising ? w.rising : live.badCount === 1 ? w.oneSign : w.calm;
  return (
    <section className="atlas-sheet" role="dialog" aria-label={ward.name}>
      <header><div><h2>{ward.name}</h2><span className={"atlas-pill " + (!live || live.knownCount === 0 ? "none" : live.rising ? "bad" : live.badCount === 1 ? "warn" : "ok")}>{status}</span></div><button className="atlas-close" onClick={onClose} aria-label={w.close}>×</button></header>
      <div className="atlas-sheet-grid">
        <div><h3>{w.nowTitle}</h3>
          {live ? <><ul className="atlas-clues">{live.clues.filter((c) => c.counts).map((c) => <li key={c.code} className={c.bad ? "bad" : c.known ? "ok" : "unknown"}>{clueText(c, w, days, fmt)}</li>)}</ul><p className="muted small">{fill(w.nowNote, { n: minBad })}</p>
            <h3 className="atlas-bg-title">{w.bgTitle}</h3><ul className="atlas-clues">{live.clues.filter((c) => !c.counts).map((c) => <li key={c.code} className="info">{clueText(c, w, days, fmt)}</li>)}</ul></> : <p className="muted">{noLive}</p>}
        </div>
        <div><h3>{w.needTitle}</h3>
          {ward.id.includes(":") && !ward.id.startsWith("relation/") && <WeeklyPriorityPanel key={ward.id} sectionId={ward.id} onSaved={onSupplySaved} />}
          <dl className="atlas-facts">
            <div><dt>{w.needScore}</dt><dd>{(ward.needWeight ?? savedNeed.get(ward.id) ?? null) === null ? "—" : (ward.needWeight ?? savedNeed.get(ward.id))!.toFixed(2)}</dd></div>
            <div><dt>{w.wad}</dt><dd>{pct(ward.waterAccessDeficitShare)}</dd></div>
            <div><dt>{w.cad}</dt><dd>{pct(ward.constrainedAccessShare)}</dd></div>
            <div><dt>{w.hardship}</dt><dd>{pct(ward.hardshipShare)}</dd></div>
            <div><dt>{w.households}</dt><dd>{ward.households2011 === null ? "—" : fmt(ward.households2011)}</dd></div>
            {ward.criticalFacilities !== null && ward.criticalFacilities !== undefined && <div><dt>{w.facilities}</dt><dd>{fmt(ward.criticalFacilities)}</dd></div>}
          </dl>
          <p className="small">{ward.growthRatio === null ? w.noGrowth : fill(w.growth, { p: pct(ward.growthRatio - 1) })}</p>
        </div>
        <div><h3>{w.checkTitle}</h3>{sections.length ? sections.map((s) => <div key={s.section_id}><h4>{s.section}</h4><SectionRates section={s} w={w} fmt={fmt} rich={rich} /></div>) : <p className="muted">{w.checkNone}</p>}</div>
      </div>
    </section>
  );
}
