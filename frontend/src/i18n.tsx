/* eslint-disable react-refresh/only-export-components -- locale hooks live beside their context provider. */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export const supportedLocales = ["en", "te", "ur", "hi"] as const;
export type Locale = (typeof supportedLocales)[number];

export const localeNames: Record<Locale, string> = {
  en: "English",
  te: "తెలుగు",
  ur: "اردو",
  hi: "हिन्दी",
};

const english = {
  brandTagline: "WATER, SHARED FAIRLY",
  chooseWorkspace: "Choose a workspace",
  navigation: "Navigation",
  officer: "Officer",
  resident: "Resident",
  fieldWorker: "Field worker",
  driver: "Driver",
  help: "Help",
  language: "Language",
  operationsWorkspace: "Operations workspace",
  communityAccess: "Community access",
  fieldOperations: "Field operations",
  officerOverview: "Overview",
  officerWaterAccess: "Water access",
  officerForecast: "Forecast & shortage",
  officerAllocationPlan: "Allocation plan",
  officerImpact: "Impact",
  residentHome: "Home",
  residentRequests: "My requests",
  residentReport: "Report an issue",
  residentUpdates: "Ward updates",
  fieldWorkerNewReport: "Report for a household",
  fieldWorkerQueue: "Saved field reports",
  driverRoute: "Today’s route",
  driverProof: "Delivery proof",
  officerConsole: "Officer console",
  officerDescription: "Evidence-led planning and service oversight",
  residentApp: "Resident app",
  residentDescription: "Water updates and support for your neighbourhood",
  driverApp: "Driver app",
  driverDescription: "Your assigned trips and delivery confirmation",
  fieldWorkerApp: "Field worker mode",
  fieldWorkerDescription: "Record household reports and sync them later",
  demoWorkspace: "Demo workspace",
  yourAccount: "Your account",
  driverProfile: "Driver profile",
  fieldWorkerProfile: "Field worker profile",
  officerProfile: "Officer profile",
  hyderabadTelangana: "Hyderabad, Telangana",
  workspaceSection: "Workspace section",
  sectionPlaceholder: "This section is part of the JalLekha workspace. Its feature view will be added in the next implementation step.",
  shellPreview: "Shell preview · No live data is connected",
  loadingEvidence: "Loading ward evidence…",
  loadingForecast: "Loading forecast screen…",
  planningWorkspace: "Planning workspace",
  goodMorning: "Good morning",
  officerIntro: "A clear view of water access, service, and the work ahead.",
  hyderabad: "Hyderabad",
  evidenceBeforeAllocation: "Evidence before allocation",
  reviewDataBasis: "Review the data basis and confidence before approving a plan.",
  readGuide: "Read the guide",
  atAGlance: "At a glance",
  currentEvidence: "Current evidence available for planning",
  waterAccessEvidence: "Water access evidence",
  wardLevel: "Ward-level",
  censusBaseline: "Census baseline, with source age shown",
  serviceCoverage: "Service and coverage",
  readyToReview: "Ready to review",
  exploreNeed: "Explore need alongside booking history",
  allocationWorkspace: "Allocation workspace",
  noPlanPending: "No plan pending",
  officerReviewPlan: "A plan will need officer review to proceed",
  startHere: "Start here",
  buildFairPicture: "Build a fair picture",
  fairPictureCopy: "See where households face barriers to water access, then compare that evidence with tanker service over time.",
  openWaterAccess: "Open water access",
  accessNeed: "Access need",
  serviceHistory: "Service history",
  needsReview: "Needs review",
  yourWorkflow: "Your workflow",
  planningChecklist: "Planning checklist",
  checklistCount: "01 / 03",
  reviewEvidence: "Review the evidence",
  understandData: "Understand what the data can tell you",
  comparePatterns: "Compare service patterns",
  fieldCheckPrompt: "Look for places to check with the community",
  reviewProposedPlan: "Review a proposed plan",
  approvalReason: "Approve only with a recorded reason",
  historicalApproximate: "Historical and approximate data is labelled where it appears.",
  flagNotProof: "A flag is a prompt to investigate, not proof of neglect.",
  neighbourhoodHyderabad: "Your neighbourhood · Hyderabad",
  waterSupportTitle: "Water support, made easier.",
  residentIntro: "Check updates, tell us what is happening, or get help from a field worker.",
  getHelp: "Get help",
  chooseWardTitle: "Choose your ward to see local updates",
  chooseWardDescription: "Your ward helps us show the right schedule and service information.",
  chooseWard: "Choose ward",
  whatToDo: "What would you like to do?",
  chooseOption: "Choose an option to continue",
  trackRequest: "Track a request",
  trackRequestDescription: "See the latest update on your water request",
  reportWaterIssue: "Report a water issue",
  reportWaterDescription: "Tell us about a shortage, leak, or missed tanker",
  seeWardUpdates: "See ward updates",
  wardUpdatesDescription: "Read local water access and service information",
  speakToSomeone: "Would you rather speak to someone?",
  fieldWorkerHelp: "A field worker can help you make a report.",
  askForHelp: "Ask for help",
  residentDemoNotice: "Demo workspace · No request will be sent to a live service.",
  driverWorkspace: "Driver workspace",
  yourWorkday: "Your workday",
  driverIntro: "Route and delivery details assigned to you.",
  ready: "Ready",
  todaysRoute: "TODAY’S ROUTE",
  noRouteAssigned: "No route assigned",
  routeWaitDescription: "Your assigned stops will appear here when a route is ready.",
  stops: "Stops",
  firstStop: "First stop",
  routeStatus: "Route status",
  waiting: "Waiting",
  atEachStop: "At each stop",
  stopIntro: "A simple record keeps deliveries clear for everyone.",
  arriveAtStop: "Arrive at the stop",
  confirmLocation: "Confirm your location when you reach the delivery point.",
  confirmDeliveryOtp: "Confirm delivery with OTP",
  askRepresentative: "Ask a registered representative for the delivery code.",
  recordOutcome: "Record the outcome",
  saveOutcome: "Save what happened, even if there is a problem.",
  gpsHelp: "Having trouble with GPS? Your app will show when location is unavailable.",
  driverDemoNotice: "Demo workspace · No route or delivery is connected to live operations.",
  footerTagline: "Community water-supply allocation",
  footerPromise: "Built for clarity, fairness, and accountability",
} as const;

type MessageKey = keyof typeof english;

const translated: Record<Exclude<Locale, "en">, Record<MessageKey, string>> = {
  te: {
    brandTagline: "నీరు · న్యాయమైన పంపిణీ", chooseWorkspace: "పని విభాగాన్ని ఎంచుకోండి", navigation: "నావిగేషన్", officer: "అధికారి", resident: "నివాసి", driver: "ట్యాంకర్ డ్రైవర్", help: "సహాయం", language: "భాష",
    loadingEvidence: "వార్డు ఆధారాలు లోడ్ అవుతున్నాయి…", loadingForecast: "అంచనా స్క్రీన్ లోడ్ అవుతోంది…", operationsWorkspace: "నిర్వహణ విభాగం", communityAccess: "ప్రజల సేవలు", fieldOperations: "క్షేత్ర సేవలు", officerOverview: "సారాంశం", officerWaterAccess: "నీటి లభ్యత", officerForecast: "అంచనా మరియు కొరత", officerAllocationPlan: "పంపిణీ ప్రణాళిక", officerImpact: "ప్రభావం", residentHome: "ముఖపుట", residentRequests: "నా అభ్యర్థనలు", residentReport: "సమస్యను తెలియజేయండి", residentUpdates: "వార్డు సమాచారం", fieldWorker: "క్షేత్ర సిబ్బంది", fieldWorkerNewReport: "కుటుంబం తరఫున నమోదు", fieldWorkerQueue: "సేవ్ చేసిన క్షేత్ర నివేదికలు", driverRoute: "నేటి మార్గం", driverProof: "నీటి పంపిణీ నిర్ధారణ",
    officerConsole: "అధికారుల కన్సోల్", officerDescription: "ఆధారాలతో ప్రణాళిక మరియు సేవల పర్యవేక్షణ", residentApp: "నివాసుల యాప్", residentDescription: "మీ ప్రాంత నీటి సమాచారం మరియు సహాయం", driverApp: "డ్రైవర్ యాప్", driverDescription: "మీకు కేటాయించిన ప్రయాణాలు, పంపిణీ వివరాలు", fieldWorkerApp: "క్షేత్ర సిబ్బంది మోడ్", fieldWorkerDescription: "కుటుంబాల సమస్యలను నమోదు చేసి, తర్వాత పంపండి", demoWorkspace: "డెమో వర్క్‌స్పేస్", yourAccount: "మీ ఖాతా", driverProfile: "డ్రైవర్ వివరాలు", fieldWorkerProfile: "క్షేత్ర సిబ్బంది వివరాలు", officerProfile: "అధికారి వివరాలు", hyderabadTelangana: "హైదరాబాద్, తెలంగాణ", workspaceSection: "వర్క్‌స్పేస్ విభాగం", sectionPlaceholder: "ఈ విభాగం జలలేఖ వర్క్‌స్పేస్‌లో భాగం. తదుపరి దశలో దీని పూర్తి వీక్షణను జోడిస్తాము.", shellPreview: "డెమో నమూనా · ప్రత్యక్ష సమాచారం లేదు",
    planningWorkspace: "ప్రణాళిక విభాగం", goodMorning: "శుభోదయం", officerIntro: "నీటి లభ్యత, సేవలు, తదుపరి పనుల స్పష్టమైన సమాచారం.", hyderabad: "హైదరాబాద్", evidenceBeforeAllocation: "పంపిణీకి ముందు ఆధారాలు చూడండి", reviewDataBasis: "ప్రణాళికను ఆమోదించే ముందు సమాచారం మరియు నమ్మక స్థాయిని పరిశీలించండి.", readGuide: "మార్గదర్శిని చూడండి", atAGlance: "ఒక చూపులో", currentEvidence: "ప్రణాళికకు అందుబాటులో ఉన్న ఆధారాలు", waterAccessEvidence: "నీటి లభ్యత ఆధారాలు", wardLevel: "వార్డు స్థాయి", censusBaseline: "జనగణన ఆధారం; సమాచారం ఏ కాలానిదో చూపిస్తాం", serviceCoverage: "సేవలు మరియు కవరేజ్", readyToReview: "పరిశీలనకు సిద్ధం", exploreNeed: "అవసరాన్ని ట్యాంకర్ బుకింగ్‌లతో పోల్చండి", allocationWorkspace: "పంపిణీ ప్రణాళిక", noPlanPending: "పెండింగ్ ప్రణాళిక లేదు", officerReviewPlan: "కొనసాగించే ముందు అధికారి ప్రణాళికను పరిశీలించాలి", startHere: "ఇక్కడ ప్రారంభించండి", buildFairPicture: "న్యాయమైన చిత్రాన్ని తెలుసుకోండి", fairPictureCopy: "ఏ కుటుంబాలకు నీటి లభ్యతలో అడ్డంకులు ఉన్నాయో చూసి, ట్యాంకర్ సేవలతో పోల్చండి.", openWaterAccess: "నీటి లభ్యతను చూడండి", accessNeed: "నీటి అవసరం", serviceHistory: "సేవల చరిత్ర", needsReview: "పరిశీలించాలి", yourWorkflow: "మీ పని క్రమం", planningChecklist: "ప్రణాళిక తనిఖీ జాబితా", checklistCount: "01 / 03", reviewEvidence: "ఆధారాలను పరిశీలించండి", understandData: "సమాచారం ఏమి చెబుతుందో తెలుసుకోండి", comparePatterns: "సేవల సరళిని పోల్చండి", fieldCheckPrompt: "ప్రజలతో కలిసి పరిశీలించాల్సిన ప్రాంతాలను గుర్తించండి", reviewProposedPlan: "ప్రతిపాదిత ప్రణాళికను పరిశీలించండి", approvalReason: "కారణాన్ని నమోదు చేసిన తర్వాతే ఆమోదించండి", historicalApproximate: "పాత లేదా అంచనా సమాచారం ఉన్నచోట దాన్ని స్పష్టంగా చూపిస్తాం.", flagNotProof: "ఈ గుర్తు పరిశీలించాల్సిన సూచన మాత్రమే; నిర్లక్ష్యానికి రుజువు కాదు.",
    neighbourhoodHyderabad: "మీ ప్రాంతం · హైదరాబాద్", waterSupportTitle: "నీటి సహాయం ఇప్పుడు సులభం.", residentIntro: "సమాచారం చూడండి, సమస్యను తెలియజేయండి లేదా క్షేత్ర సిబ్బంది సహాయం పొందండి.", getHelp: "సహాయం పొందండి", chooseWardTitle: "మీ ప్రాంత సమాచారం కోసం వార్డును ఎంచుకోండి", chooseWardDescription: "సరైన షెడ్యూల్‌, సేవా సమాచారం చూపడానికి మీ వార్డు అవసరం.", chooseWard: "వార్డును ఎంచుకోండి", whatToDo: "మీకు ఏ సహాయం కావాలి?", chooseOption: "కొనసాగడానికి ఒక ఎంపికను ఎంచుకోండి", trackRequest: "అభ్యర్థనను తెలుసుకోండి", trackRequestDescription: "మీ నీటి అభ్యర్థన తాజా స్థితిని చూడండి", reportWaterIssue: "నీటి సమస్యను తెలియజేయండి", reportWaterDescription: "నీటి కొరత, లీక్‌ లేదా రాని ట్యాంకర్ గురించి చెప్పండి", seeWardUpdates: "వార్డు సమాచారం చూడండి", wardUpdatesDescription: "మీ ప్రాంత నీటి లభ్యత, సేవల సమాచారం చదవండి", speakToSomeone: "ఎవరితోనైనా మాట్లాడాలనుకుంటున్నారా?", fieldWorkerHelp: "సమస్యను నమోదు చేయడంలో క్షేత్ర సిబ్బంది సహాయం చేస్తారు.", askForHelp: "సహాయం అడగండి", residentDemoNotice: "డెమో వర్క్‌స్పేస్ · మీ అభ్యర్థన ప్రత్యక్ష సేవకు పంపబడదు.",
    driverWorkspace: "డ్రైవర్ విభాగం", yourWorkday: "ఈరోజు మీ పని", driverIntro: "మీకు కేటాయించిన మార్గం మరియు పంపిణీ వివరాలు.", ready: "సిద్ధం", todaysRoute: "నేటి మార్గం", noRouteAssigned: "మార్గం కేటాయించలేదు", routeWaitDescription: "మార్గం సిద్ధమైనప్పుడు మీకు కేటాయించిన నిలయాలు ఇక్కడ కనిపిస్తాయి.", stops: "నిలయాలు", firstStop: "మొదటి నిలయం", routeStatus: "మార్గం స్థితి", waiting: "వేచి ఉంది", atEachStop: "ప్రతి నిలయం వద్ద", stopIntro: "సులభమైన నమోదు అందరికీ పంపిణీ వివరాలను స్పష్టంగా ఉంచుతుంది.", arriveAtStop: "నిలయానికి చేరుకోండి", confirmLocation: "పంపిణీ చోటుకు చేరినప్పుడు మీ స్థానాన్ని నిర్ధారించండి.", confirmDeliveryOtp: "OTPతో పంపిణీ నిర్ధారించండి", askRepresentative: "పంపిణీ కోడ్‌ను నమోదైన ప్రతినిధిని అడగండి.", recordOutcome: "ఫలితాన్ని నమోదు చేయండి", saveOutcome: "సమస్య వచ్చినా ఏం జరిగిందో నమోదు చేయండి.", gpsHelp: "GPS పనిచేయకపోతే? స్థానం అందుబాటులో లేదని యాప్ చూపిస్తుంది.", driverDemoNotice: "డెమో వర్క్‌స్పేస్ · మార్గం లేదా పంపిణీ ప్రత్యక్ష సేవలకు అనుసంధానించలేదు.", footerTagline: "సమాజానికి నీటి పంపిణీ", footerPromise: "స్పష్టత, న్యాయం, బాధ్యత కోసం రూపొందించబడింది",
  },
  hi: {
    brandTagline: "पानी · सबके लिए निष्पक्ष",
    chooseWorkspace: "कार्य क्षेत्र चुनें", navigation: "नेविगेशन", officer: "अधिकारी", resident: "निवासी", driver: "टैंकर चालक", help: "मदद", language: "भाषा",
    loadingEvidence: "वार्ड साक्ष्य लोड हो रहे हैं…", loadingForecast: "पूर्वानुमान स्क्रीन लोड हो रही है…", operationsWorkspace: "संचालन कार्यक्षेत्र", communityAccess: "समुदाय सेवा", fieldOperations: "मैदानी काम", officerOverview: "सारांश", officerWaterAccess: "पानी की उपलब्धता", officerForecast: "पूर्वानुमान और कमी", officerAllocationPlan: "आवंटन योजना", officerImpact: "प्रभाव", residentHome: "मुखपृष्ठ", residentRequests: "मेरे अनुरोध", residentReport: "समस्या बताएं", residentUpdates: "वार्ड अपडेट", fieldWorker: "मैदानी कर्मचारी", fieldWorkerNewReport: "परिवार की रिपोर्ट दर्ज करें", fieldWorkerQueue: "सहेजी गई मैदानी रिपोर्टें", driverRoute: "आज का मार्ग", driverProof: "डिलीवरी की पुष्टि",
    officerConsole: "अधिकारी कंसोल", officerDescription: "साक्ष्य-आधारित योजना और सेवा निगरानी", residentApp: "निवासी ऐप", residentDescription: "आपके इलाके की पानी जानकारी और सहायता", driverApp: "चालक ऐप", driverDescription: "आपको सौंपे गए मार्ग और डिलीवरी की पुष्टि", fieldWorkerApp: "मैदानी कर्मचारी मोड", fieldWorkerDescription: "परिवारों की रिपोर्ट दर्ज करें और बाद में भेजें", demoWorkspace: "डेमो कार्यक्षेत्र", yourAccount: "आपका खाता", driverProfile: "चालक प्रोफ़ाइल", fieldWorkerProfile: "मैदानी कर्मचारी प्रोफ़ाइल", officerProfile: "अधिकारी प्रोफ़ाइल", hyderabadTelangana: "हैदराबाद, तेलंगाना", workspaceSection: "कार्य क्षेत्र", sectionPlaceholder: "यह जललेखा कार्यक्षेत्र का हिस्सा है। इसका पूरा दृश्य अगले चरण में जोड़ा जाएगा।", shellPreview: "डेमो दृश्य · लाइव डेटा जुड़ा नहीं है",
    planningWorkspace: "योजना कार्यक्षेत्र", goodMorning: "सुप्रभात", officerIntro: "पानी की उपलब्धता, सेवाओं और आगे के काम की स्पष्ट जानकारी।", hyderabad: "हैदराबाद", evidenceBeforeAllocation: "आवंटन से पहले साक्ष्य देखें", reviewDataBasis: "योजना मंज़ूर करने से पहले डेटा का आधार और भरोसे का स्तर देखें।", readGuide: "मार्गदर्शिका पढ़ें", atAGlance: "एक नज़र में", currentEvidence: "योजना के लिए उपलब्ध मौजूदा साक्ष्य", waterAccessEvidence: "पानी की उपलब्धता के साक्ष्य", wardLevel: "वार्ड स्तर", censusBaseline: "जनगणना आधार; डेटा की अवधि दिखाई गई है", serviceCoverage: "सेवा और कवरेज", readyToReview: "समीक्षा के लिए तैयार", exploreNeed: "ज़रूरत की तुलना टैंकर बुकिंग से करें", allocationWorkspace: "आवंटन कार्यक्षेत्र", noPlanPending: "कोई योजना लंबित नहीं", officerReviewPlan: "आगे बढ़ने से पहले अधिकारी को योजना देखनी होगी", startHere: "यहाँ से शुरू करें", buildFairPicture: "न्यायसंगत तस्वीर देखें", fairPictureCopy: "देखें कि किन परिवारों को पानी पाने में बाधाएँ हैं, फिर इसकी तुलना टैंकर सेवा से करें।", openWaterAccess: "पानी की उपलब्धता देखें", accessNeed: "पानी की ज़रूरत", serviceHistory: "सेवा इतिहास", needsReview: "समीक्षा ज़रूरी", yourWorkflow: "आपका कार्य क्रम", planningChecklist: "योजना जाँच सूची", checklistCount: "01 / 03", reviewEvidence: "साक्ष्य की समीक्षा करें", understandData: "समझें कि डेटा क्या बताता है", comparePatterns: "सेवा के पैटर्न की तुलना करें", fieldCheckPrompt: "उन जगहों की पहचान करें जिन्हें समुदाय के साथ जाँचना है", reviewProposedPlan: "प्रस्तावित योजना की समीक्षा करें", approvalReason: "कारण दर्ज करने के बाद ही मंज़ूरी दें", historicalApproximate: "पुराना या अनुमानित डेटा जहाँ है, वहाँ उसे स्पष्ट बताया गया है।", flagNotProof: "यह संकेत जाँच करने के लिए है; उपेक्षा का प्रमाण नहीं।",
    neighbourhoodHyderabad: "आपका इलाका · हैदराबाद", waterSupportTitle: "पानी की सहायता अब आसान।", residentIntro: "अपडेट देखें, समस्या बताएं या मैदानी कर्मचारी से मदद लें।", getHelp: "मदद लें", chooseWardTitle: "स्थानीय अपडेट देखने के लिए वार्ड चुनें", chooseWardDescription: "सही समय-सारणी और सेवा जानकारी दिखाने के लिए आपका वार्ड चाहिए।", chooseWard: "वार्ड चुनें", whatToDo: "आप क्या करना चाहेंगे?", chooseOption: "जारी रखने के लिए एक विकल्प चुनें", trackRequest: "अनुरोध की स्थिति देखें", trackRequestDescription: "अपने पानी के अनुरोध का ताज़ा अपडेट देखें", reportWaterIssue: "पानी की समस्या बताएं", reportWaterDescription: "कमी, रिसाव या न आए टैंकर के बारे में बताएं", seeWardUpdates: "वार्ड अपडेट देखें", wardUpdatesDescription: "अपने इलाके की पानी और सेवा जानकारी पढ़ें", speakToSomeone: "क्या आप किसी से बात करना चाहेंगे?", fieldWorkerHelp: "मैदानी कर्मचारी आपकी रिपोर्ट दर्ज करने में मदद कर सकते हैं।", askForHelp: "मदद माँगें", residentDemoNotice: "डेमो कार्यक्षेत्र · आपका अनुरोध लाइव सेवा को नहीं भेजा जाएगा।",
    driverWorkspace: "चालक कार्यक्षेत्र", yourWorkday: "आज का काम", driverIntro: "आपको सौंपे गए मार्ग और डिलीवरी का विवरण।", ready: "तैयार", todaysRoute: "आज का मार्ग", noRouteAssigned: "कोई मार्ग नहीं सौंपा गया", routeWaitDescription: "मार्ग तैयार होने पर आपके पड़ाव यहाँ दिखेंगे।", stops: "पड़ाव", firstStop: "पहला पड़ाव", routeStatus: "मार्ग की स्थिति", waiting: "प्रतीक्षा में", atEachStop: "हर पड़ाव पर", stopIntro: "सरल रिकॉर्ड से डिलीवरी की जानकारी सबके लिए स्पष्ट रहती है।", arriveAtStop: "पड़ाव पर पहुँचें", confirmLocation: "डिलीवरी स्थान पर पहुँचकर अपनी स्थिति की पुष्टि करें।", confirmDeliveryOtp: "OTP से डिलीवरी की पुष्टि करें", askRepresentative: "डिलीवरी कोड पंजीकृत प्रतिनिधि से लें।", recordOutcome: "नतीजा दर्ज करें", saveOutcome: "समस्या होने पर भी जो हुआ उसे दर्ज करें।", gpsHelp: "GPS में दिक्कत है? स्थान उपलब्ध न होने पर ऐप बताएगा।", driverDemoNotice: "डेमो कार्यक्षेत्र · मार्ग या डिलीवरी लाइव सेवा से जुड़ी नहीं है।", footerTagline: "समुदाय के लिए पानी का आवंटन", footerPromise: "स्पष्टता, निष्पक्षता और जवाबदेही के लिए बनाया गया",
  },
  ur: {
    brandTagline: "پانی · سب کے لیے منصفانہ", chooseWorkspace: "کام کا حصہ منتخب کریں", navigation: "مینو", officer: "افسر", resident: "مقامی باشندہ", driver: "ٹینکر ڈرائیور", help: "مدد", language: "زبان",
    loadingEvidence: "وارڈ کے شواہد لوڈ ہو رہے ہیں…", loadingForecast: "پیش گوئی کا صفحہ لوڈ ہو رہا ہے…", operationsWorkspace: "انتظامی کام", communityAccess: "عوامی سہولت", fieldOperations: "میدانی کام", officerOverview: "جائزہ", officerWaterAccess: "پانی کی دستیابی", officerForecast: "پیش گوئی اور قلت", officerAllocationPlan: "تقسیم کا منصوبہ", officerImpact: "اثر", residentHome: "گھر", residentRequests: "میری درخواستیں", residentReport: "مسئلہ بتائیں", residentUpdates: "وارڈ کی تازہ معلومات", fieldWorker: "میدانی کارکن", fieldWorkerNewReport: "گھرانے کی رپورٹ درج کریں", fieldWorkerQueue: "محفوظ میدانی رپورٹیں", driverRoute: "آج کا راستہ", driverProof: "ترسیل کی تصدیق",
    officerConsole: "افسر کا کنسول", officerDescription: "شواہد کی بنیاد پر منصوبہ بندی اور خدمات کی نگرانی", residentApp: "مقامی ایپ", residentDescription: "آپ کے علاقے میں پانی کی معلومات اور مدد", driverApp: "ڈرائیور ایپ", driverDescription: "آپ کے مقررہ سفر اور ترسیل کی تصدیق", fieldWorkerApp: "میدانی کارکن کا موڈ", fieldWorkerDescription: "گھرانوں کی رپورٹ درج کریں اور بعد میں بھیجیں", demoWorkspace: "ڈیمو کام", yourAccount: "آپ کا اکاؤنٹ", driverProfile: "ڈرائیور کی تفصیل", fieldWorkerProfile: "میدانی کارکن کی تفصیل", officerProfile: "افسر کی تفصیل", hyderabadTelangana: "حیدرآباد، تلنگانہ", workspaceSection: "کام کا حصہ", sectionPlaceholder: "یہ جَل لیکھا کے کام کا حصہ ہے۔ اس کا مکمل صفحہ اگلے مرحلے میں شامل ہوگا۔", shellPreview: "ڈیمو · اصل معلومات دستیاب نہیں",
    planningWorkspace: "منصوبہ بندی", goodMorning: "صبح بخیر", officerIntro: "پانی کی دستیابی، خدمات اور اگلے کام کی واضح معلومات۔", hyderabad: "حیدرآباد", evidenceBeforeAllocation: "تقسیم سے پہلے شواہد دیکھیں", reviewDataBasis: "منصوبہ منظور کرنے سے پہلے معلومات کا ماخذ اور اعتماد کی سطح دیکھیں۔", readGuide: "رہنمائی پڑھیں", atAGlance: "ایک نظر میں", currentEvidence: "منصوبہ بندی کے لیے دستیاب شواہد", waterAccessEvidence: "پانی کی دستیابی کے شواہد", wardLevel: "وارڈ کی سطح", censusBaseline: "مردم شماری کی بنیاد؛ معلومات کا زمانہ بھی دکھایا گیا ہے", serviceCoverage: "خدمات اور کوریج", readyToReview: "جائزے کے لیے تیار", exploreNeed: "ضرورت کا ٹینکر بکنگ سے موازنہ کریں", allocationWorkspace: "تقسیم کا کام", noPlanPending: "کوئی منصوبہ زیرِ التوا نہیں", officerReviewPlan: "آگے بڑھنے سے پہلے افسر منصوبے کا جائزہ لے گا", startHere: "یہاں سے شروع کریں", buildFairPicture: "منصفانہ صورتِ حال دیکھیں", fairPictureCopy: "دیکھیں کن خاندانوں کو پانی تک رسائی میں رکاوٹ ہے، پھر اس کا ٹینکر سروس سے موازنہ کریں۔", openWaterAccess: "پانی کی دستیابی دیکھیں", accessNeed: "پانی کی ضرورت", serviceHistory: "سروس کی تاریخ", needsReview: "جائزہ ضروری", yourWorkflow: "آپ کا طریقۂ کار", planningChecklist: "منصوبہ بندی کی فہرست", checklistCount: "01 / 03", reviewEvidence: "شواہد کا جائزہ لیں", understandData: "سمجھیں کہ معلومات کیا بتاتی ہیں", comparePatterns: "سروس کے انداز کا موازنہ کریں", fieldCheckPrompt: "وہ جگہیں شناخت کریں جنہیں لوگوں کے ساتھ دیکھنا چاہیے", reviewProposedPlan: "مجوزہ منصوبے کا جائزہ لیں", approvalReason: "وجہ درج کرنے کے بعد ہی منظوری دیں", historicalApproximate: "پرانا یا اندازاً ڈیٹا جہاں ہے وہاں واضح بتایا گیا ہے۔", flagNotProof: "یہ نشان جانچ کی درخواست ہے، غفلت کا ثبوت نہیں۔",
    neighbourhoodHyderabad: "آپ کا علاقہ · حیدرآباد", waterSupportTitle: "پانی کی مدد، اب آسان۔", residentIntro: "تازہ معلومات دیکھیں، مسئلہ بتائیں یا میدانی کارکن سے مدد لیں۔", getHelp: "مدد حاصل کریں", chooseWardTitle: "اپنے علاقے کی معلومات کے لیے وارڈ منتخب کریں", chooseWardDescription: "درست شیڈول اور سروس کی معلومات دکھانے کے لیے وارڈ منتخب کریں۔", chooseWard: "وارڈ منتخب کریں", whatToDo: "آپ کیا کرنا چاہیں گے؟", chooseOption: "جاری رکھنے کے لیے ایک انتخاب کریں", trackRequest: "درخواست کی حالت دیکھیں", trackRequestDescription: "پانی کی درخواست کی تازہ معلومات دیکھیں", reportWaterIssue: "پانی کا مسئلہ بتائیں", reportWaterDescription: "کمی، رساؤ یا نہ آنے والے ٹینکر کی اطلاع دیں", seeWardUpdates: "وارڈ کی معلومات دیکھیں", wardUpdatesDescription: "اپنے علاقے میں پانی اور خدمات کی معلومات پڑھیں", speakToSomeone: "کیا آپ کسی سے بات کرنا چاہیں گے؟", fieldWorkerHelp: "میدانی کارکن آپ کی رپورٹ درج کرنے میں مدد کر سکتا ہے۔", askForHelp: "مدد طلب کریں", residentDemoNotice: "ڈیمو · آپ کی درخواست اصل سروس کو نہیں بھیجی جائے گی۔",
    driverWorkspace: "ڈرائیور کا کام", yourWorkday: "آج کا کام", driverIntro: "آپ کے مقررہ راستے اور ترسیل کی معلومات۔", ready: "تیار", todaysRoute: "آج کا راستہ", noRouteAssigned: "کوئی راستہ مقرر نہیں", routeWaitDescription: "راستہ تیار ہونے پر آپ کے مقررہ مقامات یہاں آئیں گے۔", stops: "مقامات", firstStop: "پہلا مقام", routeStatus: "راستے کی حالت", waiting: "انتظار میں", atEachStop: "ہر مقام پر", stopIntro: "سادہ ریکارڈ سے ترسیل کی معلومات سب کے لیے واضح رہتی ہیں۔", arriveAtStop: "مقام پر پہنچیں", confirmLocation: "پانی پہنچانے کی جگہ پر اپنی موجودگی کی تصدیق کریں۔", confirmDeliveryOtp: "OTP سے ترسیل کی تصدیق کریں", askRepresentative: "ترسیل کا کوڈ درج شدہ نمائندے سے لیں۔", recordOutcome: "نتیجہ درج کریں", saveOutcome: "مسئلہ ہو تب بھی جو ہوا وہ درج کریں۔", gpsHelp: "GPS میں مسئلہ ہے؟ جگہ دستیاب نہ ہو تو ایپ بتائے گی۔", driverDemoNotice: "ڈیمو · راستہ یا ترسیل اصل نظام سے منسلک نہیں۔", footerTagline: "برادری کے لیے پانی کی منصفانہ تقسیم", footerPromise: "وضاحت، انصاف اور جواب دہی کے لیے بنایا گیا",
  },
};

const messages: Record<Locale, Record<MessageKey, string>> = {
  en: english,
  te: translated.te,
  ur: translated.ur,
  hi: translated.hi,
};

type LocaleContextValue = {
  locale: Locale;
  direction: "ltr" | "rtl";
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children, initialLocale = "en" }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const direction = locale === "ur" ? "rtl" : "ltr";
  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    direction,
    setLocale,
    t: (key) => messages[locale][key],
  }), [locale, direction]);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = direction;
  }, [locale, direction]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used within LocaleProvider");
  return context;
}

export type { MessageKey };
