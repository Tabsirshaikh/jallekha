import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "./api";
import { useAuth, type AuthStatus, type Role } from "./auth";
import DataSourceChip from "./DataSource";
import {
  bookingFromApi,
  contestDetailFromApi,
  contestsFromApi,
  errorKind,
  wardFromApi,
  type ApiBookingResponse,
  type ApiContestDetail,
  type ApiContestPage,
  type ApiContestResult,
  type ApiWardResponse,
  type BookingView,
  type ContestView,
  type CounterfactualStep,
  type CounterfactualView,
  type Num,
  type ReplyView,
  type WardView,
} from "./explainAdapter";
import { useLocale, type Locale } from "./i18n";
import { liveReasonCopy } from "./liveReason";
import { useApi, type ApiState } from "./useApi";
import "./ExplainExperience.css";

type ReasonCode = "ranking_wrong" | "need_data_wrong" | "service_class_wrong" | "delivery_not_received" | "other";
type OutcomeCode = "ranking_stands" | "ranking_changed" | "data_corrected" | "referred";
/** A contest filed in the sample preview: kept in this browser only, never sent to the server. */
type Contest = { id: string; reason: ReasonCode; text: string; outcome?: OutcomeCode; reply?: string };

const copy = {
  en: { title:"Why this booking is in the queue", intro:"Read the factors behind a sample queue position and raise a contest for officer review.", demo:"SYNTHETIC PREVIEW · T7 routes not available", caveat:"Example values only. This screen does not call T7 or write to the ledger; contests and replies stay in this browser preview.", booking:"Sample booking", ward:"Sample Ward 12", status:"Waiting", place:"Queue place", capacity:"Today's capacity", tier:"Priority tier", arrived:"Arrival time", group:"Fairness group", entitlement:"Group entitlement", quantum:"Round-robin quantum", deficit:"Carried-over deficit", reason:"Queue reason", why:"Why this place?", explanation:"The booking is after today's capacity. Its position reflects its priority tier, arrival order, group entitlement and round-robin balance.", counterfactual:"Example counterfactual", counterfactualText:"An earlier arrival could move this booking up in the sample replay. The exact smallest change must come from the T7 service.", notInput:"Water debt is not an input to today's queue order.", contestTitle:"Contest this explanation", reasonCode:"Reason", detail:"What should the officer check?", detailHint:"Do not include names or phone numbers.", file:"File sample contest", contests:"Contest preview", filed:"Filed locally", pending:"Waiting for officer reply", replyTitle:"Officer reply", outcome:"Outcome", replyReason:"Reason for this decision", replyHint:"A reason is required for every reply.", submitReply:"Save sample reply", replied:"Reply saved in this preview", noContests:"No sample contests filed yet.", close:"Close", reasonLabels:{ranking_wrong:"Queue ranking seems wrong",need_data_wrong:"Need data may be wrong",service_class_wrong:"Service class may be wrong",delivery_not_received:"Delivery was not received",other:"Other reason"}, outcomeLabels:{ranking_stands:"Ranking stands",ranking_changed:"Ranking changed",data_corrected:"Data corrected",referred:"Referred for review"}, storedNote:"Demo only: no backend or ledger was updated." },
  te: { title:"ఈ బుకింగ్ క్రమంలో ఎందుకు ఉంది?", intro:"ఉదాహరణ క్రమానికి కారణాలు చూడండి; అధికారి పరిశీలనకు అభ్యంతరం పంపండి.", demo:"కల్పిత నమూనా · T7 మార్గాలు అందుబాటులో లేవు", caveat:"ఇవి ఉదాహరణ విలువలు. ఈ పేజీ T7 సేవను పిలవదు లేదా లెడ్జర్‌లో నమోదు చేయదు; అభ్యంతరాలు ఈ బ్రౌజర్ నమూనాలోనే ఉంటాయి.", booking:"నమూనా బుకింగ్", ward:"నమూనా వార్డు 12", status:"వేచి ఉంది", place:"క్యూలో స్థానం", capacity:"ఈ రోజు సామర్థ్యం", tier:"ప్రాధాన్యత స్థాయి", arrived:"వచ్చిన సమయం", group:"న్యాయ సమూహం", entitlement:"సమూహ కేటాయింపు", quantum:"రౌండ్-రాబిన్ పరిమాణం", deficit:"మిగిలిన లోటు", reason:"క్రమ కారణం", why:"ఈ స్థానం ఎందుకు?", explanation:"ఈ రోజు సామర్థ్యానికి మించి బుకింగ్ ఉంది. దాని స్థానం ప్రాధాన్యత, వచ్చిన క్రమం, సమూహ కేటాయింపు, రౌండ్-రాబిన్ సమతుల్యతపై ఆధారపడుతుంది.", counterfactual:"ఉదాహరణ ప్రత్యామ్నాయం", counterfactualText:"ఉదాహరణ పునఃప్లేలో ముందుగా రావడం వల్ల స్థానం మెరుగవవచ్చు. ఖచ్చితమైన కనిష్ఠ మార్పు T7 సేవ నుంచే రావాలి.", notInput:"ఈ రోజు క్రమంలో నీటి బాకీ ఒక ఇన్‌పుట్ కాదు.", contestTitle:"ఈ వివరణపై అభ్యంతరం", reasonCode:"కారణం", detail:"అధికారి ఏమి పరిశీలించాలి?", detailHint:"పేరు లేదా ఫోన్ నంబరు రాయకండి.", file:"ఉదాహరణ అభ్యంతరం పంపండి", contests:"అభ్యంతర నమూనా", filed:"ఇక్కడే నమోదు అయింది", pending:"అధికారి సమాధానం కోసం వేచి ఉంది", replyTitle:"అధికారి సమాధానం", outcome:"ఫలితం", replyReason:"నిర్ణయానికి కారణం", replyHint:"ప్రతి సమాధానానికి కారణం అవసరం.", submitReply:"ఉదాహరణ సమాధానాన్ని సేవ్ చేయండి", replied:"ఈ నమూనాలో సమాధానం సేవ్ అయింది", noContests:"ఇంకా నమూనా అభ్యంతరాలు లేవు.", close:"మూసివేయండి", reasonLabels:{ranking_wrong:"క్యూ క్రమం తప్పుగా ఉంది",need_data_wrong:"అవసర సమాచారం తప్పుగా ఉండవచ్చు",service_class_wrong:"సేవా తరగతి తప్పుగా ఉండవచ్చు",delivery_not_received:"నీరు అందలేదు",other:"ఇతర కారణం"}, outcomeLabels:{ranking_stands:"క్రమం అలాగే ఉంటుంది",ranking_changed:"క్రమం మార్చబడింది",data_corrected:"సమాచారం సరిచేశారు",referred:"పరిశీలనకు పంపారు"}, storedNote:"డెమో మాత్రమే: బ్యాకెండ్ లేదా లెడ్జర్ మారలేదు." },
  ur: { title:"یہ بکنگ قطار میں کیوں ہے؟", intro:"نمونے کی قطار کے عوامل دیکھیں اور افسر کے جائزے کے لیے اعتراض درج کریں۔", demo:"مصنوعی پیش منظر · T7 راستے دستیاب نہیں", caveat:"یہ صرف مثالیں ہیں۔ یہ صفحہ T7 کو کال یا لیجر میں اندراج نہیں کرتا؛ اعتراض اور جواب اسی براؤزر میں رہتے ہیں۔", booking:"نمونہ بکنگ", ward:"نمونہ وارڈ 12", status:"انتظار میں", place:"قطار میں جگہ", capacity:"آج کی گنجائش", tier:"ترجیحی درجہ", arrived:"آمد کا وقت", group:"انصاف کا گروپ", entitlement:"گروپ کا حصہ", quantum:"راؤنڈ رابن مقدار", deficit:"پچھلا بقایا", reason:"قطار کی وجہ", why:"یہ جگہ کیوں؟", explanation:"یہ بکنگ آج کی گنجائش سے آگے ہے۔ اس کی جگہ ترجیح، آمد کی ترتیب، گروپ کے حصے اور راؤنڈ رابن توازن پر منحصر ہے۔", counterfactual:"مثالی متبادل", counterfactualText:"مثالی دوبارہ حساب میں پہلے آنے سے جگہ بہتر ہوسکتی ہے۔ درست کم سے کم تبدیلی T7 سروس سے آنی چاہیے۔", notInput:"آج کی قطار میں پانی کا بقایا شامل نہیں۔", contestTitle:"اس وضاحت پر اعتراض", reasonCode:"وجہ", detail:"افسر کو کیا دیکھنا چاہیے؟", detailHint:"نام یا فون نمبر شامل نہ کریں۔", file:"نمونہ اعتراض درج کریں", contests:"اعتراض کا پیش منظر", filed:"یہیں درج ہوا", pending:"افسر کے جواب کا انتظار", replyTitle:"افسر کا جواب", outcome:"نتیجہ", replyReason:"فیصلے کی وجہ", replyHint:"ہر جواب کے ساتھ وجہ ضروری ہے۔", submitReply:"نمونہ جواب محفوظ کریں", replied:"اس پیش منظر میں جواب محفوظ ہوا", noContests:"ابھی کوئی نمونہ اعتراض نہیں۔", close:"بند کریں", reasonLabels:{ranking_wrong:"قطار کی ترتیب غلط لگتی ہے",need_data_wrong:"ضرورت کا ڈیٹا غلط ہوسکتا ہے",service_class_wrong:"سروس کی قسم غلط ہوسکتی ہے",delivery_not_received:"پانی نہیں پہنچا",other:"دوسری وجہ"}, outcomeLabels:{ranking_stands:"ترتیب برقرار",ranking_changed:"ترتیب تبدیل",data_corrected:"ڈیٹا درست کیا",referred:"جائزے کے لیے بھیجا"}, storedNote:"صرف ڈیمو: بیک اینڈ یا لیجر تبدیل نہیں ہوا۔" },
  hi: { title:"यह बुकिंग कतार में क्यों है?", intro:"नमूना कतार के कारण देखें और अधिकारी की समीक्षा के लिए आपत्ति दर्ज करें।", demo:"सिंथेटिक पूर्वावलोकन · T7 मार्ग उपलब्ध नहीं", caveat:"ये केवल उदाहरण हैं। यह पेज T7 को कॉल या लेजर में लिखता नहीं है; आपत्तियाँ और जवाब इसी ब्राउज़र में रहते हैं।", booking:"नमूना बुकिंग", ward:"नमूना वार्ड 12", status:"प्रतीक्षा में", place:"कतार में स्थान", capacity:"आज की क्षमता", tier:"प्राथमिकता स्तर", arrived:"आने का समय", group:"न्याय समूह", entitlement:"समूह का हिस्सा", quantum:"राउंड-रॉबिन मात्रा", deficit:"पिछला घाटा", reason:"कतार का कारण", why:"यह स्थान क्यों?", explanation:"यह बुकिंग आज की क्षमता से आगे है। इसका स्थान प्राथमिकता, आने का क्रम, समूह के हिस्से और राउंड-रॉबिन संतुलन पर निर्भर है।", counterfactual:"उदाहरण विकल्प", counterfactualText:"नमूना दोबारा चलाने में पहले आने से स्थान बेहतर हो सकता है। सही न्यूनतम बदलाव T7 सेवा से आना चाहिए।", notInput:"आज की कतार में पानी का बकाया शामिल नहीं है।", contestTitle:"इस स्पष्टीकरण पर आपत्ति", reasonCode:"कारण", detail:"अधिकारी को क्या जाँचना चाहिए?", detailHint:"नाम या फोन नंबर न लिखें।", file:"नमूना आपत्ति दर्ज करें", contests:"आपत्ति पूर्वावलोकन", filed:"यहीं दर्ज हुई", pending:"अधिकारी के जवाब का इंतज़ार", replyTitle:"अधिकारी का जवाब", outcome:"नतीजा", replyReason:"इस निर्णय का कारण", replyHint:"हर जवाब के लिए कारण ज़रूरी है।", submitReply:"नमूना जवाब सेव करें", replied:"इस पूर्वावलोकन में जवाब सेव हुआ", noContests:"अभी कोई नमूना आपत्ति दर्ज नहीं।", close:"बंद करें", reasonLabels:{ranking_wrong:"कतार क्रम गलत लगता है",need_data_wrong:"ज़रूरत का डेटा गलत हो सकता है",service_class_wrong:"सेवा वर्ग गलत हो सकता है",delivery_not_received:"पानी नहीं पहुँचा",other:"दूसरा कारण"}, outcomeLabels:{ranking_stands:"क्रम बरकरार",ranking_changed:"क्रम बदला",data_corrected:"डेटा सुधारा",referred:"समीक्षा के लिए भेजा"}, storedNote:"केवल डेमो: बैकएंड या लेजर नहीं बदला।" },
} satisfies Record<Locale, Record<string, unknown>>;

// Words for the live T10 view (explanations from the API, contests and replies in the ledger); merged over `copy`.
const liveCopy = {
  en: { liveTitle:"Explanations and contests", liveIntro:"Look up why a ward or booking is ranked as it is, contest it, and follow the officer's reply.", liveNotice:"Live from the JalLekha API. The server records every contest and reply in the ledger.", bookingIdNote:"Booking ids come from stored plans. Phone numbers are never shown.", lookupTitle:"Find an explanation", targetType:"What to explain", targetWard:"Ward", targetBooking:"Booking", targetId:"Ward or booking id", targetIdHint:"For example relation/7848799", show:"Show explanation", loadingExplanation:"Loading the explanation…", pickFirst:"Enter a ward or booking id to see its explanation.", serviceClass:"Service class", needWeight:"Need weight", wad:"Water access deficit", cad:"Constrained access", hardship:"Hardship", households:"Households", wardEntitlement:"Entitlement", criticalFacilities:"Critical facilities", qualityFlags:"Data quality flags", checkReasons:"Why it needs a check", reviewRequired:"Needs review", censusOk:"Census-linked", noCensus:"This ward has no usable Census data, so no need number is shown. Join status: {join}.", debtUnavailable:"Water debt is not recorded yet.", statusLabel:"Status", statusServed:"Served today", statusWaiting:"Waiting", statusRejected:"Not accepted today", position:"Served position", arrivalRank:"Arrival order", capReason:"Limit that stopped it", waitingHours:"Hours waiting", whyWaiting:"This booking is at place {place} and today's capacity is {capacity}, so it is waiting.", whyServed:"This booking is served today at position {position}.", whyRejected:"This booking was not accepted today because of a limit: {cap}.", cfTitle:"What would have to change", cfTier:"If its priority tier were {to} instead of {from}, it would move from place {before} to place {after}.", cfArrival:"If it had been booked {minutes} minutes earlier, it would move from place {before} to place {after}.", cfEntitlement:"If its group's entitlement were {percent}% higher, it would move from place {before} to place {after}.", cfDeficit:"If its group carried {amount} more round-robin credit, it would move from place {before} to place {after}.", cfOther:"A change to {input} would move it from place {before} to place {after}.", cfFirst:"This booking is already first in today's queue; nothing needs to change.", cfNone:"No single change within the search limits moves this booking up from place {before}.", cfMissing:"The server sent no 'what would have to change' answer for this booking.", fileLive:"Send contest", filedLive:"Contest sent. The server recorded it in the ledger.", officerCannotFile:"Only residents and councillors can file a contest.", needExplanation:"Open an explanation first; the contest is about the ward or booking shown.", notBoundFile:"This sign-in cannot file a contest because it is not linked to a person.", yourContests:"Your contests", allContests:"Contests", filterLabel:"Show contests", filterAll:"All", filterOpen:"Open", filterReplied:"Replied", repliedState:"Replied", refresh:"Refresh", loadingContests:"Loading contests…", noLiveContests:"No contests yet.", review:"Review", about:"About", replyLoading:"Loading the reply…", sendReply:"Send reply", repliedLive:"Reply sent. The server recorded it in the ledger.", officerId:"Your officer id", notBound:"This sign-in is not linked to a person, so it has no contests of its own. Ask the office for a personal sign-in.", notSent:"Not sent to the server", showing:"Showing {shown} of {total}", errRejected:"Your sign-in was not accepted. Sign in again.", errForbidden:"Your role cannot do this.", errNotFoundWard:"No ward with this id.", errNotFoundBooking:"No booking with this id in the stored plans.", errNotFoundContest:"This contest was not found.", errConflict:"This contest already has a reply. The list has been refreshed.", errInvalid:"The server did not accept this:", errUnreachable:"The server could not be reached. Try again.", errServer:"The server returned an error. Try again.", reasonSignIn:"Sign in as an officer, resident or councillor to see live explanations and contests. Showing the saved sample.", reasonNotAllowed:"Explanations and contests are for officers, residents and councillors. Showing the saved sample." },
  te: { liveTitle:"వివరణలు మరియు అభ్యంతరాలు", liveIntro:"వార్డు లేదా బుకింగ్ ఈ స్థానంలో ఎందుకు ఉందో చూడండి, అభ్యంతరం పంపండి, అధికారి సమాధానం తెలుసుకోండి.", liveNotice:"JalLekha API నుంచి ప్రత్యక్షంగా. ప్రతి అభ్యంతరం, సమాధానాన్ని సర్వర్ లెడ్జర్‌లో నమోదు చేస్తుంది.", bookingIdNote:"బుకింగ్ ఐడీలు సేవ్ చేసిన ప్రణాళికల నుంచి వస్తాయి. ఫోన్ నంబర్లు ఎప్పుడూ చూపించం.", lookupTitle:"వివరణ వెతకండి", targetType:"ఏది వివరించాలి", targetWard:"వార్డు", targetBooking:"బుకింగ్", targetId:"వార్డు లేదా బుకింగ్ ఐడీ", targetIdHint:"ఉదాహరణకు relation/7848799", show:"వివరణ చూపించు", loadingExplanation:"వివరణ లోడ్ అవుతోంది…", pickFirst:"వివరణ చూడటానికి వార్డు లేదా బుకింగ్ ఐడీ ఇవ్వండి.", serviceClass:"సేవా తరగతి", needWeight:"అవసర బరువు", wad:"నీటి లభ్యత లోటు", cad:"పరిమిత ప్రాప్యత", hardship:"కష్టం", households:"కుటుంబాలు", wardEntitlement:"కేటాయింపు", criticalFacilities:"కీలక సౌకర్యాలు", qualityFlags:"డేటా నాణ్యత సూచనలు", checkReasons:"పరిశీలన ఎందుకు అవసరం", reviewRequired:"పరిశీలన అవసరం", censusOk:"జనగణన అనుసంధానం", noCensus:"ఈ వార్డుకు ఉపయోగపడే జనగణన డేటా లేదు, అందుకే అవసర సంఖ్య చూపించలేదు. అనుసంధాన స్థితి: {join}.", debtUnavailable:"నీటి బాకీ ఇంకా నమోదు కాలేదు.", statusLabel:"స్థితి", statusServed:"ఈ రోజు అందింది", statusWaiting:"వేచి ఉంది", statusRejected:"ఈ రోజు అంగీకరించలేదు", position:"సేవ స్థానం", arrivalRank:"వచ్చిన క్రమం", capReason:"ఆపిన పరిమితి", waitingHours:"వేచి ఉన్న గంటలు", whyWaiting:"ఈ బుకింగ్ స్థానం {place}, ఈ రోజు సామర్థ్యం {capacity}, అందుకే వేచి ఉంది.", whyServed:"ఈ బుకింగ్ ఈ రోజు {position} స్థానంలో అందుతుంది.", whyRejected:"ఒక పరిమితి వల్ల ఈ బుకింగ్ ఈ రోజు అంగీకరించలేదు: {cap}.", cfTitle:"ఏమి మారాలి", cfTier:"ప్రాధాన్యత స్థాయి {from} బదులు {to} అయితే, ఇది స్థానం {before} నుంచి {after}కి వెళ్తుంది.", cfArrival:"{minutes} నిమిషాలు ముందుగా బుక్ చేసి ఉంటే, ఇది స్థానం {before} నుంచి {after}కి వెళ్తుంది.", cfEntitlement:"సమూహ కేటాయింపు {percent}% ఎక్కువగా ఉంటే, ఇది స్థానం {before} నుంచి {after}కి వెళ్తుంది.", cfDeficit:"సమూహానికి {amount} అదనపు రౌండ్-రాబిన్ క్రెడిట్ ఉంటే, ఇది స్థానం {before} నుంచి {after}కి వెళ్తుంది.", cfOther:"{input}లో మార్పు వల్ల ఇది స్థానం {before} నుంచి {after}కి వెళ్తుంది.", cfFirst:"ఈ బుకింగ్ ఈ రోజు క్యూలో ఇప్పటికే మొదటిది; ఏమీ మారాల్సిన అవసరం లేదు.", cfNone:"శోధన పరిమితుల్లో ఏ ఒక్క మార్పూ ఈ బుకింగ్‌ను స్థానం {before} నుంచి ముందుకు తీసుకెళ్లదు.", cfMissing:"ఈ బుకింగ్‌కు 'ఏమి మారాలి' సమాధానం సర్వర్ పంపలేదు.", fileLive:"అభ్యంతరం పంపండి", filedLive:"అభ్యంతరం పంపబడింది. సర్వర్ దాన్ని లెడ్జర్‌లో నమోదు చేసింది.", officerCannotFile:"నివాసులు, కౌన్సిలర్లు మాత్రమే అభ్యంతరం పంపగలరు.", needExplanation:"ముందు ఒక వివరణ తెరవండి; అభ్యంతరం చూపిన వార్డు లేదా బుకింగ్ గురించి ఉంటుంది.", notBoundFile:"ఈ సైన్ ఇన్ ఒక వ్యక్తికి అనుసంధానం కానందున అభ్యంతరం పంపలేదు.", yourContests:"మీ అభ్యంతరాలు", allContests:"అభ్యంతరాలు", filterLabel:"అభ్యంతరాలు చూపించు", filterAll:"అన్నీ", filterOpen:"తెరిచినవి", filterReplied:"సమాధానం ఇచ్చినవి", repliedState:"సమాధానం ఇచ్చారు", refresh:"తాజా చేయండి", loadingContests:"అభ్యంతరాలు లోడ్ అవుతున్నాయి…", noLiveContests:"ఇంకా అభ్యంతరాలు లేవు.", review:"పరిశీలించు", about:"దేని గురించి", replyLoading:"సమాధానం లోడ్ అవుతోంది…", sendReply:"సమాధానం పంపండి", repliedLive:"సమాధానం పంపబడింది. సర్వర్ దాన్ని లెడ్జర్‌లో నమోదు చేసింది.", officerId:"మీ అధికారి ఐడీ", notBound:"ఈ సైన్ ఇన్ ఒక వ్యక్తికి అనుసంధానం కాలేదు, అందుకే దీనికి సొంత అభ్యంతరాలు లేవు. వ్యక్తిగత సైన్ ఇన్ కోసం కార్యాలయాన్ని అడగండి.", notSent:"సర్వర్‌కు పంపలేదు", showing:"{total}లో {shown} చూపిస్తున్నాం", errRejected:"మీ సైన్ ఇన్ అంగీకరించబడలేదు. మళ్లీ సైన్ ఇన్ చేయండి.", errForbidden:"మీ పాత్రకు ఈ అనుమతి లేదు.", errNotFoundWard:"ఈ ఐడీతో వార్డు లేదు.", errNotFoundBooking:"సేవ్ చేసిన ప్రణాళికల్లో ఈ ఐడీతో బుకింగ్ లేదు.", errNotFoundContest:"ఈ అభ్యంతరం కనబడలేదు.", errConflict:"ఈ అభ్యంతరానికి ఇప్పటికే సమాధానం ఉంది. జాబితా తాజా చేశాం.", errInvalid:"సర్వర్ దీన్ని అంగీకరించలేదు:", errUnreachable:"సర్వర్‌ను చేరుకోలేకపోయాం. మళ్లీ ప్రయత్నించండి.", errServer:"సర్వర్ లోపం చూపింది. మళ్లీ ప్రయత్నించండి.", reasonSignIn:"ప్రత్యక్ష వివరణలు, అభ్యంతరాల కోసం అధికారి, నివాసి లేదా కౌన్సిలర్‌గా సైన్ ఇన్ చేయండి. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.", reasonNotAllowed:"వివరణలు, అభ్యంతరాలు అధికారులు, నివాసులు, కౌన్సిలర్ల కోసం. సేవ్ చేసిన నమూనా చూపిస్తున్నాం." },
  ur: { liveTitle:"وضاحتیں اور اعتراضات", liveIntro:"دیکھیں کہ کوئی وارڈ یا بکنگ اس درجے پر کیوں ہے، اعتراض کریں اور افسر کا جواب دیکھیں۔", liveNotice:"JalLekha API سے براہِ راست۔ سرور ہر اعتراض اور جواب لیجر میں درج کرتا ہے۔", bookingIdNote:"بکنگ کی شناخت محفوظ شدہ منصوبوں سے آتی ہے۔ فون نمبر کبھی نہیں دکھائے جاتے۔", lookupTitle:"وضاحت تلاش کریں", targetType:"کس کی وضاحت", targetWard:"وارڈ", targetBooking:"بکنگ", targetId:"وارڈ یا بکنگ کی شناخت", targetIdHint:"مثال کے طور پر relation/7848799", show:"وضاحت دکھائیں", loadingExplanation:"وضاحت لوڈ ہو رہی ہے…", pickFirst:"وضاحت دیکھنے کے لیے وارڈ یا بکنگ کی شناخت درج کریں۔", serviceClass:"سروس کی قسم", needWeight:"ضرورت کا وزن", wad:"پانی تک رسائی کی کمی", cad:"محدود رسائی", hardship:"مشکل حالات", households:"گھرانے", wardEntitlement:"حصہ", criticalFacilities:"اہم سہولیات", qualityFlags:"ڈیٹا کے معیار کے اشارے", checkReasons:"جانچ کیوں ضروری ہے", reviewRequired:"جائزہ ضروری", censusOk:"مردم شماری سے منسلک", noCensus:"اس وارڈ کا قابلِ استعمال مردم شماری ڈیٹا نہیں، اس لیے ضرورت کا کوئی عدد نہیں دکھایا گیا۔ ربط کی حالت: {join}۔", debtUnavailable:"پانی کا بقایا ابھی درج نہیں۔", statusLabel:"حالت", statusServed:"آج فراہم", statusWaiting:"انتظار میں", statusRejected:"آج قبول نہیں", position:"فراہمی کی جگہ", arrivalRank:"آمد کی ترتیب", capReason:"روکنے والی حد", waitingHours:"انتظار کے گھنٹے", whyWaiting:"یہ بکنگ جگہ {place} پر ہے اور آج کی گنجائش {capacity} ہے، اس لیے یہ انتظار میں ہے۔", whyServed:"یہ بکنگ آج جگہ {position} پر فراہم ہو رہی ہے۔", whyRejected:"یہ بکنگ ایک حد کی وجہ سے آج قبول نہیں ہوئی: {cap}۔", cfTitle:"کیا بدلنا ہوگا", cfTier:"اگر اس کا ترجیحی درجہ {from} کے بجائے {to} ہوتا تو یہ جگہ {before} سے {after} پر آ جاتی۔", cfArrival:"اگر یہ {minutes} منٹ پہلے بک ہوتی تو جگہ {before} سے {after} پر آ جاتی۔", cfEntitlement:"اگر اس کے گروپ کا حصہ {percent}% زیادہ ہوتا تو یہ جگہ {before} سے {after} پر آ جاتی۔", cfDeficit:"اگر اس کے گروپ کے پاس {amount} مزید راؤنڈ رابن کریڈٹ ہوتا تو یہ جگہ {before} سے {after} پر آ جاتی۔", cfOther:"{input} میں تبدیلی سے یہ جگہ {before} سے {after} پر آ جاتی۔", cfFirst:"یہ بکنگ آج کی قطار میں پہلے ہی پہلی ہے؛ کچھ بدلنے کی ضرورت نہیں۔", cfNone:"تلاش کی حدود میں کوئی ایک تبدیلی اس بکنگ کو جگہ {before} سے آگے نہیں لاتی۔", cfMissing:"سرور نے اس بکنگ کے لیے 'کیا بدلنا ہوگا' کا جواب نہیں بھیجا۔", fileLive:"اعتراض بھیجیں", filedLive:"اعتراض بھیج دیا گیا۔ سرور نے اسے لیجر میں درج کیا۔", officerCannotFile:"صرف رہائشی اور کونسلر اعتراض درج کر سکتے ہیں۔", needExplanation:"پہلے کوئی وضاحت کھولیں؛ اعتراض دکھائے گئے وارڈ یا بکنگ کے بارے میں ہوگا۔", notBoundFile:"یہ سائن ان کسی فرد سے منسلک نہیں، اس لیے اعتراض درج نہیں کر سکتا۔", yourContests:"آپ کے اعتراضات", allContests:"اعتراضات", filterLabel:"اعتراضات دکھائیں", filterAll:"سب", filterOpen:"کھلے", filterReplied:"جواب شدہ", repliedState:"جواب دیا گیا", refresh:"تازہ کریں", loadingContests:"اعتراضات لوڈ ہو رہے ہیں…", noLiveContests:"ابھی کوئی اعتراض نہیں۔", review:"جائزہ", about:"بارے میں", replyLoading:"جواب لوڈ ہو رہا ہے…", sendReply:"جواب بھیجیں", repliedLive:"جواب بھیج دیا گیا۔ سرور نے اسے لیجر میں درج کیا۔", officerId:"آپ کی افسر شناخت", notBound:"یہ سائن ان کسی فرد سے منسلک نہیں، اس لیے اس کے اپنے اعتراضات نہیں۔ ذاتی سائن ان کے لیے دفتر سے رابطہ کریں۔", notSent:"سرور کو نہیں بھیجا گیا", showing:"{total} میں سے {shown} دکھائے گئے", errRejected:"آپ کا سائن ان قبول نہیں ہوا۔ دوبارہ سائن ان کریں۔", errForbidden:"آپ کے کردار کو اس کی اجازت نہیں۔", errNotFoundWard:"اس شناخت کا کوئی وارڈ نہیں۔", errNotFoundBooking:"محفوظ شدہ منصوبوں میں اس شناخت کی کوئی بکنگ نہیں۔", errNotFoundContest:"یہ اعتراض نہیں ملا۔", errConflict:"اس اعتراض کا جواب پہلے ہی دیا جا چکا ہے۔ فہرست تازہ کر دی گئی ہے۔", errInvalid:"سرور نے اسے قبول نہیں کیا:", errUnreachable:"سرور سے رابطہ نہیں ہو سکا۔ دوبارہ کوشش کریں۔", errServer:"سرور نے خرابی بتائی۔ دوبارہ کوشش کریں۔", reasonSignIn:"براہِ راست وضاحتوں اور اعتراضات کے لیے افسر، رہائشی یا کونسلر کے طور پر سائن ان کریں۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔", reasonNotAllowed:"وضاحتیں اور اعتراضات افسران، رہائشیوں اور کونسلروں کے لیے ہیں۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔" },
  hi: { liveTitle:"स्पष्टीकरण और आपत्तियाँ", liveIntro:"देखें कि कोई वार्ड या बुकिंग इस स्थान पर क्यों है, आपत्ति दर्ज करें और अधिकारी का जवाब देखें।", liveNotice:"JalLekha API से लाइव। सर्वर हर आपत्ति और जवाब को लेजर में दर्ज करता है।", bookingIdNote:"बुकिंग आईडी सहेजी गई योजनाओं से आती हैं। फोन नंबर कभी नहीं दिखाए जाते।", lookupTitle:"स्पष्टीकरण खोजें", targetType:"किसका स्पष्टीकरण", targetWard:"वार्ड", targetBooking:"बुकिंग", targetId:"वार्ड या बुकिंग आईडी", targetIdHint:"उदाहरण के लिए relation/7848799", show:"स्पष्टीकरण दिखाएँ", loadingExplanation:"स्पष्टीकरण लोड हो रहा है…", pickFirst:"स्पष्टीकरण देखने के लिए वार्ड या बुकिंग आईडी दर्ज करें।", serviceClass:"सेवा वर्ग", needWeight:"ज़रूरत का भार", wad:"पानी की उपलब्धता में कमी", cad:"सीमित पहुँच", hardship:"कठिनाई", households:"परिवार", wardEntitlement:"हिस्सा", criticalFacilities:"ज़रूरी सुविधाएँ", qualityFlags:"डेटा गुणवत्ता संकेत", checkReasons:"जाँच क्यों ज़रूरी है", reviewRequired:"समीक्षा ज़रूरी", censusOk:"जनगणना से जुड़ा", noCensus:"इस वार्ड का उपयोगी जनगणना डेटा नहीं है, इसलिए ज़रूरत का कोई अंक नहीं दिखाया गया। जोड़ की स्थिति: {join}।", debtUnavailable:"पानी का बकाया अभी दर्ज नहीं है।", statusLabel:"स्थिति", statusServed:"आज मिलेगा", statusWaiting:"प्रतीक्षा में", statusRejected:"आज स्वीकार नहीं", position:"सेवा स्थान", arrivalRank:"आने का क्रम", capReason:"रोकने वाली सीमा", waitingHours:"प्रतीक्षा के घंटे", whyWaiting:"यह बुकिंग स्थान {place} पर है और आज की क्षमता {capacity} है, इसलिए यह प्रतीक्षा में है।", whyServed:"यह बुकिंग आज स्थान {position} पर पूरी होगी।", whyRejected:"यह बुकिंग एक सीमा के कारण आज स्वीकार नहीं हुई: {cap}।", cfTitle:"क्या बदलना होगा", cfTier:"अगर इसका प्राथमिकता स्तर {from} की जगह {to} होता, तो यह स्थान {before} से {after} पर आ जाती।", cfArrival:"अगर यह {minutes} मिनट पहले बुक होती, तो यह स्थान {before} से {after} पर आ जाती।", cfEntitlement:"अगर इसके समूह का हिस्सा {percent}% अधिक होता, तो यह स्थान {before} से {after} पर आ जाती।", cfDeficit:"अगर इसके समूह के पास {amount} अधिक राउंड-रॉबिन क्रेडिट होता, तो यह स्थान {before} से {after} पर आ जाती।", cfOther:"{input} में बदलाव से यह स्थान {before} से {after} पर आ जाती।", cfFirst:"यह बुकिंग आज की कतार में पहले से पहली है; कुछ बदलने की ज़रूरत नहीं।", cfNone:"खोज की सीमाओं में कोई एक बदलाव इस बुकिंग को स्थान {before} से आगे नहीं लाता।", cfMissing:"सर्वर ने इस बुकिंग के लिए 'क्या बदलना होगा' का जवाब नहीं भेजा।", fileLive:"आपत्ति भेजें", filedLive:"आपत्ति भेज दी गई। सर्वर ने इसे लेजर में दर्ज किया।", officerCannotFile:"केवल निवासी और पार्षद आपत्ति दर्ज कर सकते हैं।", needExplanation:"पहले कोई स्पष्टीकरण खोलें; आपत्ति दिखाए गए वार्ड या बुकिंग के बारे में होगी।", notBoundFile:"यह साइन इन किसी व्यक्ति से जुड़ा नहीं है, इसलिए आपत्ति दर्ज नहीं कर सकता।", yourContests:"आपकी आपत्तियाँ", allContests:"आपत्तियाँ", filterLabel:"आपत्तियाँ दिखाएँ", filterAll:"सभी", filterOpen:"खुली", filterReplied:"जवाब दी गई", repliedState:"जवाब दिया गया", refresh:"ताज़ा करें", loadingContests:"आपत्तियाँ लोड हो रही हैं…", noLiveContests:"अभी कोई आपत्ति नहीं।", review:"समीक्षा", about:"किस बारे में", replyLoading:"जवाब लोड हो रहा है…", sendReply:"जवाब भेजें", repliedLive:"जवाब भेज दिया गया। सर्वर ने इसे लेजर में दर्ज किया।", officerId:"आपकी अधिकारी आईडी", notBound:"यह साइन इन किसी व्यक्ति से जुड़ा नहीं है, इसलिए इसकी अपनी कोई आपत्ति नहीं है। निजी साइन इन के लिए कार्यालय से पूछें।", notSent:"सर्वर को नहीं भेजी गई", showing:"{total} में से {shown} दिखाई गईं", errRejected:"आपका साइन इन स्वीकार नहीं हुआ। फिर से साइन इन करें।", errForbidden:"आपकी भूमिका को इसकी अनुमति नहीं है।", errNotFoundWard:"इस आईडी का कोई वार्ड नहीं।", errNotFoundBooking:"सहेजी गई योजनाओं में इस आईडी की कोई बुकिंग नहीं।", errNotFoundContest:"यह आपत्ति नहीं मिली।", errConflict:"इस आपत्ति का जवाब पहले ही दिया जा चुका है। सूची ताज़ा कर दी गई है।", errInvalid:"सर्वर ने इसे स्वीकार नहीं किया:", errUnreachable:"सर्वर से संपर्क नहीं हो सका। फिर से कोशिश करें।", errServer:"सर्वर ने त्रुटि बताई। फिर से कोशिश करें।", reasonSignIn:"लाइव स्पष्टीकरण और आपत्तियों के लिए अधिकारी, निवासी या पार्षद के रूप में साइन इन करें। सहेजा हुआ नमूना दिखाया जा रहा है।", reasonNotAllowed:"स्पष्टीकरण और आपत्तियाँ अधिकारियों, निवासियों और पार्षदों के लिए हैं। सहेजा हुआ नमूना दिखाया जा रहा है।" },
} satisfies Record<Locale, Record<string, string>>;

type Words = (typeof copy)[Locale] & (typeof liveCopy)[Locale];
type Reason = "signIn" | "notAllowed" | "rejected" | "unreachable" | "error";
type Filter = "all" | "open" | "replied";
type Target = { type: "ward" | "booking"; id: string };
type Notice = { tone: "ok" | "error"; text: string } | null;

const reasons: ReasonCode[] = ["ranking_wrong", "need_data_wrong", "service_class_wrong", "delivery_not_received", "other"];
const outcomes: OutcomeCode[] = ["ranking_stands", "ranking_changed", "data_corrected", "referred"];
/** Roles the explain and contest routes answer (T10); a driver or field worker sees the sample. */
const READERS: Role[] = ["officer", "resident", "councillor"];
const LIMIT = 50;

function fill(template: string, params: Record<string, string | number | null>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => { const value = params[key]; return value === null || value === undefined ? "—" : String(value); });
}
function humanize(code: string): string { return code.replaceAll("_", " ").toLowerCase(); }
function fmtNum(value: number | null, locale: Locale): string {
  return value === null ? "—" : new Intl.NumberFormat(locale, { maximumFractionDigits: Math.abs(value) < 1 ? 3 : 2 }).format(value);
}
function fmtTime(iso: string, locale: Locale): string {
  const moment = new Date(iso);
  return Number.isNaN(moment.getTime()) ? iso : new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(moment);
}

/** Why the sample is shown instead of live data; null while checking or when live. */
function fallbackReason(status: AuthStatus, role: Role | null, error: ApiError | null): Reason | null {
  if (status === "anonymous") return "signIn";
  if (status === "rejected") return "rejected";
  if (status === "unreachable") return "unreachable";
  if (status === "checking") return null;
  if (role === null || !READERS.includes(role)) return "notAllowed";
  if (!error) return null;
  if (error.status === 401) return "rejected";
  if (error.status === 0) return "unreachable";
  if (error.status === 403) return "notAllowed";
  return "error";
}

function errorText(cause: unknown, w: Words, context: "ward" | "booking" | "contest"): string {
  const error = cause instanceof ApiError ? cause : new ApiError(0, "network_error", "");
  switch (errorKind(error)) {
    case "unreachable": return w.errUnreachable;
    case "rejected": return w.errRejected;
    case "forbidden": return w.errForbidden;
    case "notFound": return context === "ward" ? w.errNotFoundWard : context === "booking" ? w.errNotFoundBooking : w.errNotFoundContest;
    case "conflict": return w.errConflict;
    case "invalid": return `${w.errInvalid} ${error.message}`;
    default: return w.errServer;
  }
}

export default function ExplainExperience() {
  const { locale } = useLocale();
  const { status, role, userId } = useAuth();
  const w: Words = { ...copy[locale], ...liveCopy[locale] };
  const [filter, setFilter] = useState<Filter>("all");

  // The contest list doubles as the live check: it is asked only for a signed-in reader role.
  const reader = status === "signed-in" && role !== null && READERS.includes(role);
  const isOfficer = role === "officer";
  const contests = useApi<ApiContestPage>(reader ? `/contests?limit=${LIMIT}${isOfficer && filter !== "all" ? `&status=${filter}` : ""}` : null);
  // A resident or councillor token without a user id has no own contests (403); explanations still work.
  const notBound = reader && !isOfficer && contests.error?.status === 403;
  const listFailed = contests.error !== null && !notBound;
  // Loading counts as live so a refresh does not flash the sample; any failure shows the sample.
  const live = reader && !listFailed;
  const reason = live ? null : fallbackReason(status, role, listFailed ? contests.error : null);
  const reasonText = reason === null ? null : reason === "signIn" ? w.reasonSignIn : reason === "notAllowed" ? w.reasonNotAllowed : liveReasonCopy[locale][reason];
  const chip = { live: live && (contests.live || notBound), loading: status === "checking" || (live && contests.loading), error: listFailed ? contests.error : null };

  return <div className="explain-page">
    <header className="explain-heading"><div><p className="eyebrow">{live ? "F16 · T7 · T10" : "F16 · T7"}</p><h1>{live ? w.liveTitle : w.title}</h1><p className="muted">{live ? w.liveIntro : w.intro}</p></div><div className="explain-heading-tags"><DataSourceChip state={chip} />{!live && <span className="forecast-demo-badge">{w.demo}</span>}</div></header>
    {reasonText && <p className="explain-live-reason" role="note">{reasonText}</p>}
    {live
      ? <LiveView w={w} locale={locale} isOfficer={isOfficer} userId={userId} notBound={notBound} contests={contests} filter={filter} setFilter={setFilter} />
      : <SampleView w={w} />}
  </div>;
}

type LiveProps = { w: Words; locale: Locale; isOfficer: boolean; userId: string | null; notBound: boolean; contests: ApiState<ApiContestPage>; filter: Filter; setFilter: (filter: Filter) => void };

function LiveView({ w, locale, isOfficer, userId, notBound, contests, filter, setFilter }: LiveProps) {
  const [draftType, setDraftType] = useState<Target["type"]>("ward");
  const [draftId, setDraftId] = useState("");
  const [target, setTarget] = useState<Target | null>(null);
  const [reason, setReason] = useState<ReasonCode>("need_data_wrong");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const path = target ? `/explain/${target.type === "ward" ? "wards" : "bookings"}/${encodeURIComponent(target.id)}` : null;
  const ward = useApi<ApiWardResponse>(target?.type === "ward" ? path : null);
  const booking = useApi<ApiBookingResponse>(target?.type === "booking" ? path : null);
  const current = target?.type === "booking" ? booking : ward;
  const wardView = target?.type === "ward" && ward.data ? wardFromApi(ward.data) : null;
  const bookingView = target?.type === "booking" && booking.data ? bookingFromApi(booking.data) : null;
  // The contest is about what the API just explained, by the API's own id.
  const shown: Target | null = wardView ? { type: "ward", id: wardView.id } : bookingView ? { type: "booking", id: bookingView.booking.id } : null;
  const page = contests.data ? contestsFromApi(contests.data) : null;

  function lookUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = draftId.trim();
    if (!id) return;
    if (target && target.type === draftType && target.id === id) current.reload();
    else setTarget({ type: draftType, id });
  }

  async function fileContest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!shown || !text.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      await apiFetch<ApiContestResult>("/contests", { method: "POST", body: { target_type: shown.type, target_id: shown.id, reason_code: reason, reason_text: text.trim() } });
      setText("");
      setNotice({ tone: "ok", text: w.filedLive });
      contests.reload();
    } catch (cause) {
      setNotice({ tone: "error", text: errorText(cause, w, "contest") });
    } finally {
      setBusy(false);
    }
  }

  const chooseFilter = (value: Filter) => { setFilter(value); setSelected(null); };
  const listLabel = isOfficer ? w.allContests : w.yourContests;

  return <>
    <div className="explain-notice"><strong>{w.liveNotice}</strong><span>{w.bookingIdNote}</span></div>
    <section className="explain-panel"><p className="eyebrow">{w.lookupTitle}</p>
      <form className="explain-form explain-lookup" onSubmit={lookUp}>
        <label>{w.targetType}<select value={draftType} onChange={(event)=>setDraftType(event.target.value as Target["type"])}><option value="ward">{w.targetWard}</option><option value="booking">{w.targetBooking}</option></select></label>
        <label>{w.targetId}<input type="text" value={draftId} onChange={(event)=>setDraftId(event.target.value)} placeholder={w.targetIdHint} autoComplete="off" /></label>
        <button className="button button-dark" type="submit" disabled={!draftId.trim()}>{w.show}</button>
      </form>
    </section>
    {!target ? <p className="muted explain-hint">{w.pickFirst}</p>
      : current.loading ? <p className="muted explain-hint" role="status">{w.loadingExplanation}</p>
      : current.error ? <p className="explain-status explain-error" role="alert">{errorText(current.error, w, target.type)}</p>
      : wardView ? <WardPanel ward={wardView} w={w} locale={locale} />
      : bookingView ? <BookingPanel booking={bookingView.booking} counterfactual={bookingView.counterfactual} w={w} locale={locale} />
      : null}
    <div className="explain-contest-grid">
      <section className="explain-panel"><p className="eyebrow">{w.contestTitle}</p>
        {isOfficer ? <p className="muted">{w.officerCannotFile}</p>
          : notBound ? <p className="muted">{w.notBoundFile}</p>
          : !shown ? <p className="muted">{w.needExplanation}</p>
          : <form className="explain-form" onSubmit={fileContest}>
            <p className="explain-target">{w.about}: {shown.type === "ward" ? w.targetWard : w.targetBooking} {shown.id}</p>
            <label>{w.reasonCode}<select value={reason} onChange={(event)=>setReason(event.target.value as ReasonCode)}>{reasons.map((item)=><option key={item} value={item}>{w.reasonLabels[item]}</option>)}</select></label>
            <label>{w.detail}<textarea value={text} onChange={(event)=>setText(event.target.value)} maxLength={2000} rows={3} placeholder={w.detailHint} /></label>
            <button className="button button-dark" type="submit" disabled={busy || !text.trim()}>{w.fileLive}</button>
          </form>}
      </section>
      <section className="explain-panel"><div className="explain-panel-heading"><div><p className="eyebrow">{listLabel}</p><h2>{page ? page.total : "—"}</h2></div><button type="button" className="button button-secondary" onClick={()=>contests.reload()}>{w.refresh}</button></div>
        {isOfficer && <div className="explain-filter" role="group" aria-label={w.filterLabel}>{(["all", "open", "replied"] as const).map((value)=><button key={value} type="button" aria-pressed={filter===value} className={filter===value?"active":""} onClick={()=>chooseFilter(value)}>{value==="all"?w.filterAll:value==="open"?w.filterOpen:w.filterReplied}</button>)}</div>}
        {notBound ? <p className="muted">{w.notBound}</p>
          : contests.loading || !page ? <p className="muted" role="status">{w.loadingContests}</p>
          : page.items.length === 0 ? <p className="muted">{w.noLiveContests}</p>
          : <ul className="explain-contest-list" aria-label={listLabel}>{page.items.map((contest)=><li key={contest.id}><article className="explain-contest">
            <div><strong>{w.about}: {contest.targetType === "ward" ? w.targetWard : contest.targetType === "booking" ? w.targetBooking : contest.targetType} {contest.targetId}</strong><span className="explain-state">{contest.status === "replied" ? w.repliedState : w.pending}</span></div>
            <p>{w.reasonLabels[contest.reasonCode as ReasonCode] ?? humanize(contest.reasonCode)}</p>
            <p>{contest.text}</p>
            <small>{fmtTime(contest.createdAt, locale)} · {contest.id}</small>
            {!isOfficer && contest.status === "replied" && <ReplyLoader id={contest.id} w={w} locale={locale} />}
            {isOfficer && <button type="button" className="button button-secondary" aria-label={`${w.review} ${contest.id}`} aria-expanded={selected === contest.id} onClick={()=>setSelected(selected === contest.id ? null : contest.id)}>{w.review}</button>}
            {isOfficer && selected === contest.id && <OfficerReview id={contest.id} w={w} locale={locale} userId={userId} onNotice={setNotice} onChanged={()=>contests.reload()} />}
          </article></li>)}</ul>}
        {page && page.total > page.items.length && <p className="explain-footer">{fill(w.showing, { shown: page.items.length, total: page.total })}</p>}
      </section>
    </div>
    {notice && <p className={notice.tone === "error" ? "explain-status explain-error" : "explain-status"} role={notice.tone === "error" ? "alert" : "status"}>{notice.text}</p>}
    <p className="explain-footer">API: /explain/wards, /explain/bookings, /contests</p>
  </>;
}

function Fact({ label, num, locale }: { label: string; num: Num; locale: Locale }) {
  return <div><span>{label}</span><strong>{fmtNum(num.value, locale)}</strong>{num.basis && <small>{num.basis}</small>}</div>;
}

function WardPanel({ ward, w, locale }: { ward: WardView; w: Words; locale: Locale }) {
  return <section className="explain-panel" aria-label={ward.name}>
    <div className="explain-panel-heading"><div><p className="eyebrow">{w.targetWard} · {ward.id}</p><h2>{ward.name}</h2></div><span className="explain-state">{ward.reviewRequired ? w.reviewRequired : w.censusOk}</span></div>
    <div className="explain-facts">
      <div><span>{w.serviceClass}</span><strong>{humanize(ward.serviceClass)}</strong><small>{ward.classBasis}</small></div>
      {ward.hasCensus && <>
        <Fact label={w.needWeight} num={ward.needWeight} locale={locale} />
        <Fact label={w.wad} num={ward.wad} locale={locale} />
        <Fact label={w.cad} num={ward.cad} locale={locale} />
        <Fact label={w.hardship} num={ward.hardship} locale={locale} />
        <Fact label={w.households} num={ward.households} locale={locale} />
        <Fact label={w.wardEntitlement} num={ward.entitlement} locale={locale} />
      </>}
      <Fact label={w.criticalFacilities} num={ward.criticalFacilities} locale={locale} />
    </div>
    <div className="explain-detail">
      {!ward.hasCensus && <p>{fill(w.noCensus, { join: ward.joinStatus })}</p>}
      <p className="explain-census">{ward.censusLabel}</p>
      {ward.qualityFlags.length > 0 && <small>{w.qualityFlags}: {ward.qualityFlags.map(humanize).join(", ")}</small>}
      {ward.checkReasons.length > 0 && <small>{w.checkReasons}: {ward.checkReasons.map(humanize).join(", ")}</small>}
      {!ward.debtAvailable && <small>{w.debtUnavailable}</small>}
    </div>
  </section>;
}

function stepText(step: CounterfactualStep, before: number | null, w: Words): string {
  const base = { before, after: step.after };
  switch (step.kind) {
    case "tier": return fill(w.cfTier, { ...base, from: step.from, to: step.to });
    case "arrival": return fill(w.cfArrival, { ...base, minutes: step.minutes });
    case "entitlement": return fill(w.cfEntitlement, { ...base, percent: step.percent });
    case "deficit": return fill(w.cfDeficit, { ...base, amount: step.amount });
    default: return fill(w.cfOther, { ...base, input: humanize(step.input) });
  }
}

function BookingPanel({ booking, counterfactual, w, locale }: { booking: BookingView; counterfactual: CounterfactualView | null; w: Words; locale: Locale }) {
  const n = (value: number | null) => fmtNum(value, locale);
  const statusWord = booking.status === "served" ? w.statusServed : booking.status === "waiting" ? w.statusWaiting : booking.status === "rejected" ? w.statusRejected : humanize(booking.status);
  const why = booking.status === "served" ? fill(w.whyServed, { position: booking.position }) : booking.status === "rejected" ? fill(w.whyRejected, { cap: booking.capReason ? humanize(booking.capReason) : null }) : fill(w.whyWaiting, { place: booking.place, capacity: booking.capacity });
  return <section className="explain-panel" aria-label={booking.id}>
    <div className="explain-panel-heading"><div><p className="eyebrow">{w.targetBooking}</p><h2>{booking.id}</h2></div><span className="explain-state">{statusWord}</span></div>
    <div className="explain-facts">
      <div><span>{w.place}</span><strong>{n(booking.place)}</strong></div>
      <div><span>{w.capacity}</span><strong>{n(booking.capacity)}</strong></div>
      <div><span>{w.tier}</span><strong>{n(booking.tier)}</strong></div>
      <div><span>{w.arrived}</span><strong>{fmtTime(booking.arrivedAt, locale)}</strong></div>
      <div><span>{w.group}</span><strong>{booking.group}</strong></div>
      <div><span>{w.waitingHours}</span><strong>{n(booking.waitingHours)}</strong></div>
      {booking.status === "served" && <>
        <div><span>{w.position}</span><strong>{n(booking.position)}</strong></div>
        <div><span>{w.reason}</span><strong>{booking.reason ?? "—"}</strong></div>
        <div><span>{w.arrivalRank}</span><strong>{n(booking.arrivalRank)}</strong></div>
        <div><span>{w.entitlement}</span><strong>{n(booking.entitlement)}</strong></div>
        <div><span>{w.quantum}</span><strong>{n(booking.quantum)}</strong></div>
        <div><span>{w.deficit}</span><strong>{n(booking.deficitBefore)}</strong></div>
      </>}
      {booking.status === "rejected" && <div><span>{w.capReason}</span><strong>{booking.capReason ? humanize(booking.capReason) : "—"}</strong></div>}
    </div>
    <div className="explain-detail"><h3>{w.why}</h3><p>{why}</p>{!booking.debtAvailable && <small>{w.debtUnavailable}</small>}</div>
    <div className="explain-counterfactual"><span className="source-tag derived">DERIVED</span><div><h3>{w.cfTitle}</h3>
      {counterfactual === null ? <p>{w.cfMissing}</p>
        : counterfactual.status === "already_first" ? <p>{w.cfFirst}</p>
        : <>{counterfactual.status === "none" && <p>{fill(w.cfNone, { before: counterfactual.before })}</p>}{counterfactual.steps.map((step)=><p key={step.kind + step.after}>{stepText(step, counterfactual.before, w)}</p>)}</>}
      {(counterfactual?.notInputs ?? []).map((code)=><small key={code}>{code === "water_debt" ? w.notInput : humanize(code)}</small>)}
    </div></div>
  </section>;
}

function ReplyBox({ reply, w, locale }: { reply: ReplyView; w: Words; locale: Locale }) {
  return <div className="explain-reply"><strong>{w.replyTitle} · {w.outcomeLabels[reply.outcome as OutcomeCode] ?? humanize(reply.outcome)}</strong><p>{reply.text}</p><small>{reply.officerId} · {fmtTime(reply.createdAt, locale)}</small></div>;
}

/** A resident's or councillor's replied contest: the reply comes from GET /contests/{id}. */
function ReplyLoader({ id, w, locale }: { id: string; w: Words; locale: Locale }) {
  const detail = useApi<ApiContestDetail>(`/contests/${encodeURIComponent(id)}`);
  if (detail.error) return <p className="explain-error">{errorText(detail.error, w, "contest")}</p>;
  if (!detail.data) return <p className="muted" role="status">{w.replyLoading}</p>;
  const view: ContestView = contestDetailFromApi(detail.data);
  return view.reply ? <ReplyBox reply={view.reply} w={w} locale={locale} /> : null;
}

type ReviewProps = { id: string; w: Words; locale: Locale; userId: string | null; onNotice: (notice: Notice) => void; onChanged: () => void };

/** The officer opens one contest and replies; the reply needs a reason (the server checks it too). */
function OfficerReview({ id, w, locale, userId, onNotice, onChanged }: ReviewProps) {
  const detail = useApi<ApiContestDetail>(`/contests/${encodeURIComponent(id)}`);
  const [outcome, setOutcome] = useState<OutcomeCode>("referred");
  const [reply, setReply] = useState("");
  const [officerId, setOfficerId] = useState("");
  const [busy, setBusy] = useState(false);
  const officer = userId ?? officerId.trim();

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reply.trim() || !officer) return;
    setBusy(true);
    onNotice(null);
    try {
      await apiFetch<ApiContestResult>(`/contests/${encodeURIComponent(id)}/reply`, { method: "POST", body: { officer_id: officer, outcome_code: outcome, reason_text: reply.trim() } });
      setReply("");
      onNotice({ tone: "ok", text: w.repliedLive });
      detail.reload();
      onChanged();
    } catch (cause) {
      onNotice({ tone: "error", text: errorText(cause, w, "contest") });
      if (cause instanceof ApiError && cause.status === 409) { detail.reload(); onChanged(); }
    } finally {
      setBusy(false);
    }
  }

  if (detail.error) return <p className="explain-error">{errorText(detail.error, w, "contest")}</p>;
  if (!detail.data) return <p className="muted" role="status">{w.replyLoading}</p>;
  const view = contestDetailFromApi(detail.data);
  if (view.reply) return <ReplyBox reply={view.reply} w={w} locale={locale} />;
  return <form className="explain-form" onSubmit={send}><h3>{w.replyTitle}</h3>
    {userId === null && <label>{w.officerId}<input type="text" value={officerId} onChange={(event)=>setOfficerId(event.target.value)} autoComplete="off" /></label>}
    <label>{w.outcome}<select value={outcome} onChange={(event)=>setOutcome(event.target.value as OutcomeCode)}>{outcomes.map((item)=><option key={item} value={item}>{w.outcomeLabels[item]}</option>)}</select></label>
    <label>{w.replyReason}<textarea value={reply} onChange={(event)=>setReply(event.target.value)} maxLength={2000} rows={2} placeholder={w.replyHint} /></label>
    <button className="button button-dark" type="submit" disabled={busy || !reply.trim() || !officer}>{w.sendReply}</button>
  </form>;
}

/** Today's sample preview, unchanged: synthetic values, contests and replies kept in this browser only. */
function SampleView({ w }: { w: Words }) {
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

  return <>
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
        {contests.length===0?<p className="muted">{w.noContests}</p>:<div className="explain-contest-list">{contests.map((contest)=><article className="explain-contest" key={contest.id}><div><strong>{contest.id}</strong><span className="explain-state">{contest.outcome?w.replied:w.pending}</span></div><small className="explain-local-tag">{w.notSent}</small><p>{w.reasonLabels[contest.reason]}</p><p>{contest.text}</p>{contest.reply?<div className="explain-reply"><strong>{w.outcomeLabels[contest.outcome!]}</strong><p>{contest.reply}</p></div>:<form className="explain-form" onSubmit={(event)=>replyToContest(event,contest.id)}><h3>{w.replyTitle}</h3><label>{w.outcome}<select value={outcome} onChange={(event)=>setOutcome(event.target.value as OutcomeCode)}>{outcomes.map((item)=><option key={item} value={item}>{w.outcomeLabels[item]}</option>)}</select></label><label>{w.replyReason}<textarea value={reply} onChange={(event)=>setReply(event.target.value)} maxLength={500} rows={2} placeholder={w.replyHint}/></label><button className="button button-secondary" type="submit" disabled={!reply.trim()}>{w.submitReply}</button></form>}</article>)}</div>}
      </section>
    </div>
    {message && <p className="explain-status" role="status">{message} · {w.storedNote}</p>}
    <p className="explain-footer">{w.storedNote}</p>
  </>;
}
