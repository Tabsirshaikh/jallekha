import PlanMap from "./PlanMap";
import SectionPlanForm from "./SectionPlanForm";
import { useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { ApiError, apiFetch } from "./api";
import { useAuth } from "./auth";
import { parseBookingsCsv, type CsvProblem } from "./bookingsCsv";
import DataSourceChip from "./DataSource";
import { useLocale, type Locale } from "./i18n";
import { adaptCompare, adaptLivePlan, adaptPlanList, planReason, REPLAY_FIRST_DAY, REPLAY_LAST_DAY, type FallbackReason, type PlanList, type Weights } from "./planAdapter";
import { useApi } from "./useApi";
import "./PlanExperience.css";

// Used only when the server does not say (it reports its configured defaults and maximum with the plan list).
const FALLBACK_WEIGHTS: Weights = { wad: 2, cad: 1, hardship: 1 };
const FALLBACK_MAX_WEIGHT = 5;

type Group = { id: string; name: string; need: number; gap: number; debt: number; confidence: "good" | "review" };
const groups: Group[] = [
  { id: "a", name: "Sample Ward A", need: 86, gap: 72, debt: 35, confidence: "good" },
  { id: "b", name: "Sample Ward B", need: 68, gap: 88, debt: 60, confidence: "good" },
  { id: "c", name: "Sample Ward C", need: 74, gap: 54, debt: 82, confidence: "good" },
  { id: "d", name: "Sample Ward D", need: 91, gap: 70, debt: 20, confidence: "review" },
];

// Non-English strings added for the live plan (U7) are drafts awaiting a native-speaker review.
const copy = {
  en: { title:"Daily allocation plan", intro:"Review a draft queue, scheduled supply, confidence checks, and the effect of priority weights.", demo:"SIMULATION · No live allocation API", caveat:"All ward names, inputs, trip counts, and outcomes on this screen are synthetic examples. Approval here does not dispatch tankers or change entitlements.", draft:"Draft for officer review", trips:"Demo trips", reserve:"Scheduled reserve", outage:"Outage response", queue:"Fair-queue trips", weights:"Priority weights", need:"Need signal", gap:"Service gap", debt:"Water debt", beneficiaries:"Who gains", recipient:"Sample ward", allocation:"Trips", change:"Change vs equal split", confidence:"Confidence check", confident:"Inputs present", review:"Manual review required", reviewText:"This sample group has incomplete evidence. Review it before approval.", markReviewed:"I reviewed this group", schedule:"Illustrative schedule", time:"Window", stop:"Stop", quantity:"Loads", scheduleNote:"Example schedule only; no service point registry is connected.", reason:"Officer approval reason", reasonHint:"Explain why this draft is appropriate (required).", approve:"Approve demo plan", approved:"Demo plan approved", blocked:"Review flagged groups and enter a reason to approve.", queueOrder:"Priority queue", basis:"SIMULATION", rank:"Priority", reset:"Reset draft", weightsHint:"Adjust weights to see how the synthetic queue changes. Scores are not validated policy.", equal:"Equal-split reference", complete:"Complete", flagged:"Needs review", approvedNote:"Recorded locally for this preview only. No backend or ledger was updated.",
    liveBadge:"SIMULATION · Replay plan from the API", liveIntro:"Build a plan for a replay day, check the low-confidence groups and approve it with a reason.", liveCaveat:"Every plan here is SIMULATION: March–July 2025 replay, monthly totals REAL, daily arrivals SYNTHETIC. Approval is saved on the server and logged in the ledger; it does not dispatch tankers.", dataSource:"Data source", liveNote:"Served by the JalLekha API just now. Plans are built from the committed A8 replay (SIMULATION), not from today's operations.", loadingNote:"Checking for live plans; showing the sample plan meanwhile.", signInNote:"Sign in with an officer token to see live plans. Showing the sample plan.", forbiddenNote:"This account cannot open officer plans. Showing the sample plan.", unreachableNote:"The server could not be reached. Showing the sample plan.", serverErrorNote:"The server returned an error. Showing the sample plan.", incompleteNote:"The server's answer was incomplete. Showing the sample plan.",
    plans:"Stored plans", noPlans:"No plans are stored yet. Build one for a replay day.", showing:"Showing {shown} of {total} plans.", statusDraft:"Draft", statusApproved:"Approved", flagsProgress:"{checked} of {total} flagged groups checked", open:"Open", opened:"Open now", openAria:"Open plan {day}",
    buildTitle:"Build plan for a day", buildHint:"Pick a day in the replay window, 2025-03-01 to 2025-07-31.", build:"Build plan", building:"Building the plan… the first one after a server start can take about 15 seconds.", buildDone:"Plan for {day} built and opened.", buildExisting:"A plan for {day} already existed; it is open now.", buildOutside:"That day is outside the replay window (2025-03-01 to 2025-07-31).", buildInvalid:"Enter a valid date (YYYY-MM-DD).",
    pickPlan:"Open a stored plan or build one to review it.", loadingPlan:"Loading the plan…", planFailed:"This plan could not be loaded.", planIncomplete:"The server's answer for this plan was incomplete, so it is not shown.",
    liveTrips:"Trips planned", served:"Bookings served", waitingCount:"{count} waiting", liveQueue:"Groups in today's queue", queueNote:"Bookings served per group across all stations, in fair-queue (DRR) order at each station.", servedBookings:"Served bookings", confidenceLabel:"Confidence",
    checkTitle:"Flagged groups to check", thresholdNoteDerived:"The confidence threshold {threshold} was chosen on a simulated replay with deliberately wrong data (T9): the lowest cut-off that kept 90% of unflagged decisions right in every draw. It holds only if real data errors follow the assumed pattern. {below} of {groups} groups in this plan are below it and need an officer check before approval.", thresholdNote:"The confidence threshold {threshold} is PROVISIONAL and not calibrated (T9): the replay could not tell thresholds apart, so it is a placeholder cut-off, not a validated one. {below} of {groups} groups in this plan are below it and need an officer check before approval.", progress:"{checked} of {total} checked", checkReason:"Check reason (used for each group you mark)", checkReasonHint:"What did you check? Required for every group.", markChecked:"Mark checked", markAria:"Mark {group} checked", checkedLabel:"Checked", needsCheck:"Needs check", inputsOk:"Above threshold", checkDone:"{group} marked checked.", allChecked:"All flagged groups are checked.", noFlags:"No group in this plan is below the threshold.",
    officerId:"Officer id", officerIdHint:"Your sign-in token carries no officer id. Type yours; it is recorded with every check and the approval.", needOfficer:"Enter your officer id first.",
    liveSchedule:"Scheduled supply", liveScheduleNote:"Wards on the scheduled supply (litres SIMULATION). A ward marked as needing a service point has no routed stop yet.", ward:"Ward", litres:"Litres / floor", scheduleStatus:"Status", floorNotMet:"Below the floor", floorMet:"Floor met", needsServicePoint:"Needs a service point",
    liveOutage:"Outage response", outageCritical:"Critical areas", outageAllocations:"Allocations", outageUnused:"Unused outage litres", outageDebt:"Counts toward water debt", yes:"Yes", no:"No",
    approveLive:"Approve plan", approving:"Approving…", approveBlockedFlags:"Check all flagged groups first ({checked} of {total} checked).", approveNeedReason:"Enter a reason to approve.", alreadyApproved:"This plan is already approved.", approveReady:"Approval is saved on the server and logged in the ledger.", approvedLive:"Plan approved by {officer}", approvedLiveNote:"Saved on the server and logged in the ledger. SIMULATION plan: no tankers are dispatched.",
    refused:"The server refused:", unreachableShort:"The server could not be reached. Try again.",
    weightsTitle:"Priority weights", wWad:"Water access", wCad:"Phone access", wHardship:"Hardship", weightDefault:"default", weightsLiveHint:"Choose how much each need counts when the plan is built. Weights can move only a few trips: daily capacity limits what they change. A plan with other weights is a separate plan, recorded in the ledger with its weights.", weightsReset:"Reset weights", weightsBadge:"Weights {wad} / {cad} / {hardship}", openWeightedAria:"Open plan {day} with weights {wad} / {cad} / {hardship}", gainsTitle:"Who gains and who loses", gainsIntro:"Booked trips on {day} with these weights, compared with the default weights. The same trips are shared out differently.", gainsLoading:"Comparing with the default plan…", gainers:"Gains trips", losers:"Loses trips", servedWas:"default", servedNow:"weighted", noChanges:"No group gets a different number of trips under these weights.", compareFailed:"The comparison could not be loaded.", gainsNote:"Capacity limits how far weights can move trips, so changes are usually small.",
    bookingsTitle:"Build from supplied bookings", bookingsHint:"There is no live booking feed, so the plan uses exactly the bookings you supply. Paste them as CSV or choose a file. Columns: booking_id, section, arrived_at (with a time zone); optional consumer_id, category, tier.", bookingsDay:"Day of these bookings", bookingsText:"Bookings (CSV)", bookingsFile:"Or choose a CSV file", bookingsWeightsNote:"The priority weights chosen above are used.", bookingsBuild:"Build plan from bookings", bookingsBuilding:"Building the plan from the bookings…", bookingsNeed:"Choose the day of the bookings and paste at least one booking.", bookingsDone:"Plan built from {count} bookings for {day}.", csvMissing:"Missing column: {name}. The first line must name booking_id, section and arrived_at.", csvUnknown:"Unknown column: {name}.", csvShape:"Line {line}: expected {expected} values but found {found}.", csvTier:"Line {line}: tier must be 0, 1 or 2.", suppliedLabel:"Supplied bookings", openSuppliedAria:"Open plan {day} built from supplied bookings", suppliedNote:"Built from {count} bookings supplied for {day}, not the replay. The bookings are as supplied (not verified here); capacity is an ASSUMED fleet scenario." },
  te: { title:"రోజువారీ పంపిణీ ప్రణాళిక", intro:"ముసాయిదా క్రమం, షెడ్యూల్ సరఫరా, నమ్మక తనిఖీలు, ప్రాధాన్యత బరువుల ప్రభావాన్ని పరిశీలించండి.", demo:"అనుకరణ · ప్రత్యక్ష పంపిణీ API లేదు", caveat:"ఈ స్క్రీన్‌లోని వార్డు పేర్లు, ఇన్‌పుట్‌లు, ప్రయాణాల సంఖ్యలు, ఫలితాలు అన్నీ కల్పిత ఉదాహరణలు. ఇక్కడ ఆమోదం ట్యాంకర్లను పంపదు లేదా హక్కులను మార్చదు.", draft:"అధికారి పరిశీలనకు ముసాయిదా", trips:"ఉదాహరణ ప్రయాణాలు", reserve:"షెడ్యూల్ నిల్వ", outage:"అంతరాయం స్పందన", queue:"న్యాయ క్రమ ప్రయాణాలు", weights:"ప్రాధాన్యత బరువులు", need:"అవసర సూచిక", gap:"సేవా లోటు", debt:"నీటి బాకీ", beneficiaries:"ఎవరికి ప్రయోజనం", recipient:"ఉదాహరణ వార్డు", allocation:"ప్రయాణాలు", change:"సమాన పంపిణీతో తేడా", confidence:"నమ్మక తనిఖీ", confident:"ఇన్‌పుట్‌లు ఉన్నాయి", review:"మానవ పరిశీలన అవసరం", reviewText:"ఈ ఉదాహరణ గుంపుకు పూర్తి ఆధారాలు లేవు. ఆమోదానికి ముందు పరిశీలించండి.", markReviewed:"ఈ గుంపును పరిశీలించాను", schedule:"ఉదాహరణ షెడ్యూల్", time:"సమయం", stop:"నిలయం", quantity:"లోడ్లు", scheduleNote:"ఇది ఉదాహరణ షెడ్యూల్ మాత్రమే; సేవా కేంద్రాల జాబితా అనుసంధానం కాలేదు.", reason:"అధికారి ఆమోద కారణం", reasonHint:"ఈ ముసాయిదా ఎందుకు సరైనదో రాయండి (తప్పనిసరి).", approve:"ఉదాహరణ ప్రణాళిక ఆమోదించు", approved:"ఉదాహరణ ప్రణాళిక ఆమోదించబడింది", blocked:"ఆమోదానికి గుర్తించిన గుంపులను పరిశీలించి కారణం రాయండి.", queueOrder:"ప్రాధాన్యత క్రమం", basis:"అనుకరణ", rank:"ప్రాధాన్యత", reset:"ముసాయిదా రీసెట్", weightsHint:"బరువులను మార్చి కల్పిత క్రమం ఎలా మారుతుందో చూడండి. స్కోర్లు ధృవీకరించిన విధానం కాదు.", equal:"సమాన పంపిణీ ప్రమాణం", complete:"పూర్తి", flagged:"పరిశీలించాలి", approvedNote:"ఈ ప్రివ్యూ కోసం స్థానికంగా మాత్రమే నమోదు. బ్యాకెండ్ లేదా లెడ్జర్ మారలేదు.",
    liveBadge:"అనుకరణ · API నుంచి రీప్లే ప్రణాళిక", liveIntro:"రీప్లే రోజుకు ప్రణాళిక తయారు చేసి, తక్కువ నమ్మకం ఉన్న గుంపులను పరిశీలించి, కారణంతో ఆమోదించండి.", liveCaveat:"ఇక్కడి ప్రతి ప్రణాళిక అనుకరణ: మార్చి–జూలై 2025 రీప్లే, నెలవారీ మొత్తాలు వాస్తవం, రోజువారీ రాకలు కల్పితం. ఆమోదం సర్వర్‌లో సేవ్ అయి లెడ్జర్‌లో నమోదవుతుంది; ట్యాంకర్లను పంపదు.", dataSource:"డేటా మూలం", liveNote:"JalLekha API నుంచి ఇప్పుడే వచ్చిన డేటా. ప్రణాళికలు కమిట్ చేసిన A8 రీప్లే (అనుకరణ) నుంచి తయారవుతాయి, నేటి కార్యకలాపాల నుంచి కాదు.", loadingNote:"ప్రత్యక్ష ప్రణాళికల కోసం తనిఖీ చేస్తోంది; అప్పటివరకు ఉదాహరణ ప్రణాళిక.", signInNote:"ప్రత్యక్ష ప్రణాళికల కోసం అధికారి టోకెన్‌తో సైన్ ఇన్ చేయండి. ఉదాహరణ ప్రణాళిక చూపిస్తున్నాం.", forbiddenNote:"ఈ ఖాతాకు అధికారి ప్రణాళికలు చూసే అనుమతి లేదు. ఉదాహరణ ప్రణాళిక చూపిస్తున్నాం.", unreachableNote:"సర్వర్‌ను చేరుకోలేకపోయాం. ఉదాహరణ ప్రణాళిక చూపిస్తున్నాం.", serverErrorNote:"సర్వర్ లోపం చూపింది. ఉదాహరణ ప్రణాళిక చూపిస్తున్నాం.", incompleteNote:"సర్వర్ సమాధానం అసంపూర్ణంగా ఉంది. ఉదాహరణ ప్రణాళిక చూపిస్తున్నాం.",
    plans:"సేవ్ చేసిన ప్రణాళికలు", noPlans:"ఇంకా ప్రణాళికలు లేవు. రీప్లే రోజుకు ఒకటి తయారు చేయండి.", showing:"{total}లో {shown} ప్రణాళికలు చూపిస్తున్నాం.", statusDraft:"ముసాయిదా", statusApproved:"ఆమోదించబడింది", flagsProgress:"గుర్తించిన {total} గుంపుల్లో {checked} పరిశీలించారు", open:"తెరవండి", opened:"తెరిచి ఉంది", openAria:"{day} ప్రణాళిక తెరవండి",
    buildTitle:"ఒక రోజుకు ప్రణాళిక తయారు చేయండి", buildHint:"రీప్లే వ్యవధిలో (2025-03-01 నుంచి 2025-07-31) ఒక రోజు ఎంచుకోండి.", build:"ప్రణాళిక తయారు చేయి", building:"ప్రణాళిక తయారవుతోంది… సర్వర్ ప్రారంభం తర్వాత మొదటిదానికి సుమారు 15 సెకన్లు పట్టవచ్చు.", buildDone:"{day} ప్రణాళిక తయారై తెరవబడింది.", buildExisting:"{day} ప్రణాళిక ఇప్పటికే ఉంది; ఇప్పుడు తెరిచి ఉంది.", buildOutside:"ఆ రోజు రీప్లే వ్యవధి (2025-03-01 నుంచి 2025-07-31) బయట ఉంది.", buildInvalid:"సరైన తేదీ (YYYY-MM-DD) ఇవ్వండి.",
    pickPlan:"పరిశీలించడానికి సేవ్ చేసిన ప్రణాళికను తెరవండి లేదా కొత్తది తయారు చేయండి.", loadingPlan:"ప్రణాళిక లోడ్ అవుతోంది…", planFailed:"ఈ ప్రణాళికను లోడ్ చేయలేకపోయాం.", planIncomplete:"ఈ ప్రణాళికకు సర్వర్ సమాధానం అసంపూర్ణం, కాబట్టి చూపడం లేదు.",
    liveTrips:"ప్రణాళికలోని ప్రయాణాలు", served:"అందిన బుకింగ్‌లు", waitingCount:"{count} వేచి ఉన్నాయి", liveQueue:"నేటి క్రమంలోని గుంపులు", queueNote:"అన్ని కేంద్రాల్లో ప్రతి గుంపుకు అందిన బుకింగ్‌లు; ప్రతి కేంద్రంలో న్యాయ క్రమం (DRR).", servedBookings:"అందిన బుకింగ్‌లు", confidenceLabel:"నమ్మకం",
    checkTitle:"పరిశీలించాల్సిన గుంపులు", thresholdNoteDerived:"నమ్మక పరిమితి {threshold}ను ఉద్దేశపూర్వకంగా తప్పు డేటాతో చేసిన అనుకరణ రీప్లేలో ఎంచుకున్నాం (T9): ప్రతి ప్రయత్నంలో గుర్తించని నిర్ణయాల్లో 90% సరిగా ఉంచిన అతి తక్కువ పరిమితి ఇది. అసలు డేటా లోపాలు ఊహించిన తీరులో ఉంటేనే ఇది వర్తిస్తుంది. ఈ ప్రణాళికలో {groups} గుంపుల్లో {below} దీని కంటే తక్కువ; ఆమోదానికి ముందు అధికారి పరిశీలన అవసరం.", thresholdNote:"నమ్మక పరిమితి {threshold} తాత్కాలికం, క్రమాంకనం కాలేదు (T9): రీప్లే పరిమితుల మధ్య తేడా చెప్పలేకపోయింది, కాబట్టి ఇది ధృవీకరించిన పరిమితి కాదు. ఈ ప్రణాళికలోని {groups} గుంపుల్లో {below} దీని కంటే తక్కువ; ఆమోదానికి ముందు అధికారి పరిశీలన అవసరం.", progress:"{total}లో {checked} పరిశీలించారు", checkReason:"పరిశీలన కారణం (మీరు గుర్తించే ప్రతి గుంపుకు)", checkReasonHint:"మీరు ఏమి పరిశీలించారు? ప్రతి గుంపుకు తప్పనిసరి.", markChecked:"పరిశీలించినట్లు గుర్తించు", markAria:"{group} పరిశీలించినట్లు గుర్తించు", checkedLabel:"పరిశీలించారు", needsCheck:"పరిశీలన అవసరం", inputsOk:"పరిమితి కంటే ఎక్కువ", checkDone:"{group} పరిశీలించినట్లు గుర్తించారు.", allChecked:"గుర్తించిన అన్ని గుంపులు పరిశీలించారు.", noFlags:"ఈ ప్రణాళికలో పరిమితి కంటే తక్కువ గుంపు లేదు.",
    officerId:"అధికారి ఐడీ", officerIdHint:"మీ టోకెన్‌లో అధికారి ఐడీ లేదు. మీ ఐడీ రాయండి; ప్రతి పరిశీలన, ఆమోదంతో నమోదవుతుంది.", needOfficer:"ముందు మీ అధికారి ఐడీ రాయండి.",
    liveSchedule:"షెడ్యూల్ సరఫరా", liveScheduleNote:"షెడ్యూల్ సరఫరాలోని వార్డులు (లీటర్లు అనుకరణ). సేవా కేంద్రం అవసరమని గుర్తించిన వార్డుకు ఇంకా మార్గం లేదు.", ward:"వార్డు", litres:"లీటర్లు / కనీసం", scheduleStatus:"స్థితి", floorNotMet:"కనీసం కంటే తక్కువ", floorMet:"కనీసం చేరింది", needsServicePoint:"సేవా కేంద్రం అవసరం",
    liveOutage:"అంతరాయం స్పందన", outageCritical:"క్లిష్ట ప్రాంతాలు", outageAllocations:"కేటాయింపులు", outageUnused:"వాడని అంతరాయ లీటర్లు", outageDebt:"నీటి బాకీలో లెక్కిస్తారా", yes:"అవును", no:"కాదు",
    approveLive:"ప్రణాళిక ఆమోదించు", approving:"ఆమోదిస్తోంది…", approveBlockedFlags:"ముందు గుర్తించిన అన్ని గుంపులను పరిశీలించండి ({total}లో {checked}).", approveNeedReason:"ఆమోదానికి కారణం రాయండి.", alreadyApproved:"ఈ ప్రణాళిక ఇప్పటికే ఆమోదించబడింది.", approveReady:"ఆమోదం సర్వర్‌లో సేవ్ అయి లెడ్జర్‌లో నమోదవుతుంది.", approvedLive:"{officer} ప్రణాళికను ఆమోదించారు", approvedLiveNote:"సర్వర్‌లో సేవ్ అయి లెడ్జర్‌లో నమోదైంది. అనుకరణ ప్రణాళిక: ట్యాంకర్లు పంపబడవు.",
    refused:"సర్వర్ తిరస్కరించింది:", unreachableShort:"సర్వర్‌ను చేరుకోలేకపోయాం. మళ్లీ ప్రయత్నించండి.",
    weightsTitle:"ప్రాధాన్యత బరువులు", wWad:"నీటి లభ్యత", wCad:"ఫోన్ లభ్యత", wHardship:"కష్టం", weightDefault:"డిఫాల్ట్", weightsLiveHint:"ప్రణాళిక తయారయ్యేటప్పుడు ప్రతి అవసరానికి ఎంత విలువ ఇవ్వాలో ఎంచుకోండి. బరువులు కొన్ని ప్రయాణాలను మాత్రమే మార్చగలవు: రోజువారీ సామర్థ్యం వాటి ప్రభావాన్ని పరిమితం చేస్తుంది. ఇతర బరువులతో చేసిన ప్రణాళిక వేరే ప్రణాళిక; దాని బరువులతో సహా లెడ్జర్‌లో నమోదవుతుంది.", weightsReset:"బరువులను రీసెట్ చేయి", weightsBadge:"బరువులు {wad} / {cad} / {hardship}", openWeightedAria:"{day} ప్రణాళిక తెరువు, బరువులు {wad} / {cad} / {hardship}", gainsTitle:"ఎవరికి లాభం, ఎవరికి నష్టం", gainsIntro:"ఈ బరువులతో {day} నాటి బుకింగ్ ప్రయాణాలను డిఫాల్ట్ బరువులతో పోల్చాం. అవే ప్రయాణాలు వేరేగా పంచబడతాయి.", gainsLoading:"డిఫాల్ట్ ప్రణాళికతో పోలుస్తోంది…", gainers:"ప్రయాణాలు పెరిగినవి", losers:"ప్రయాణాలు తగ్గినవి", servedWas:"డిఫాల్ట్", servedNow:"బరువుతో", noChanges:"ఈ బరువులతో ఏ గుంపుకూ ప్రయాణాల సంఖ్య మారదు.", compareFailed:"పోలికను లోడ్ చేయలేకపోయాం.", gainsNote:"సామర్థ్యం బరువుల ప్రభావాన్ని పరిమితం చేస్తుంది, కాబట్టి మార్పులు సాధారణంగా చిన్నవి.",
    bookingsTitle:"అందించిన బుకింగ్‌ల నుంచి తయారు చేయండి", bookingsHint:"ప్రత్యక్ష బుకింగ్ ఫీడ్ లేదు, కాబట్టి ప్రణాళిక మీరు ఇచ్చిన బుకింగ్‌లనే ఉపయోగిస్తుంది. వాటిని CSV గా అతికించండి లేదా ఫైల్ ఎంచుకోండి. నిలువు వరుసలు: booking_id, section, arrived_at (టైమ్ జోన్‌తో); ఐచ్ఛికం: consumer_id, category, tier.", bookingsDay:"ఈ బుకింగ్‌ల రోజు", bookingsText:"బుకింగ్‌లు (CSV)", bookingsFile:"లేదా CSV ఫైల్ ఎంచుకోండి", bookingsWeightsNote:"పైన ఎంచుకున్న ప్రాధాన్యత బరువులు ఉపయోగించబడతాయి.", bookingsBuild:"బుకింగ్‌ల నుంచి ప్రణాళిక తయారు చేయి", bookingsBuilding:"బుకింగ్‌ల నుంచి ప్రణాళిక తయారవుతోంది…", bookingsNeed:"బుకింగ్‌ల రోజును ఎంచుకుని కనీసం ఒక బుకింగ్ అతికించండి.", bookingsDone:"{day} కోసం {count} బుకింగ్‌ల నుంచి ప్రణాళిక తయారైంది.", csvMissing:"నిలువు వరుస లేదు: {name}. మొదటి వరుసలో booking_id, section, arrived_at ఉండాలి.", csvUnknown:"తెలియని నిలువు వరుస: {name}.", csvShape:"{line}వ వరుస: {expected} విలువలు అవసరం, {found} ఉన్నాయి.", csvTier:"{line}వ వరుస: tier 0, 1 లేదా 2 అయి ఉండాలి.", suppliedLabel:"అందించిన బుకింగ్‌లు", openSuppliedAria:"అందించిన బుకింగ్‌లతో చేసిన {day} ప్రణాళిక తెరువు", suppliedNote:"{day} కోసం అందించిన {count} బుకింగ్‌ల నుంచి తయారైంది, రీప్లే నుంచి కాదు. బుకింగ్‌లు ఇచ్చినట్టే (ఇక్కడ ధృవీకరించలేదు); సామర్థ్యం ఊహించిన వాహన పరిస్థితి (ASSUMED)." },
  ur: { title:"روزانہ تقسیم کا منصوبہ", intro:"مسودہ قطار، طے شدہ فراہمی، اعتماد کی جانچ اور ترجیحی وزن کا اثر دیکھیں۔", demo:"تخمینی · براہ راست تقسیم API نہیں", caveat:"اس صفحے کے تمام وارڈ نام، معلومات، ٹرپ کی تعداد اور نتائج فرضی مثالیں ہیں۔ یہاں منظوری سے ٹینکر نہیں بھیجے جاتے اور نہ حق بدلتا ہے۔", draft:"افسر کے جائزے کے لیے مسودہ", trips:"نمائشی ٹرپ", reserve:"طے شدہ ذخیرہ", outage:"تعطل کا جواب", queue:"منصفانہ قطار کے ٹرپ", weights:"ترجیحی وزن", need:"ضرورت کا اشارہ", gap:"سروس کا فرق", debt:"پانی کا بقایا", beneficiaries:"کسے فائدہ", recipient:"نمونہ وارڈ", allocation:"ٹرپ", change:"برابر تقسیم سے فرق", confidence:"اعتماد کی جانچ", confident:"معلومات موجود", review:"افسر کا جائزہ ضروری", reviewText:"اس فرضی گروپ کے شواہد نامکمل ہیں۔ منظوری سے پہلے دیکھیں۔", markReviewed:"میں نے یہ گروپ دیکھا", schedule:"نمائشی شیڈول", time:"وقت", stop:"مقام", quantity:"لوڈ", scheduleNote:"یہ صرف مثال ہے؛ سروس پوائنٹ کی فہرست منسلک نہیں۔", reason:"افسر کی منظوری کی وجہ", reasonHint:"بتائیں یہ مسودہ کیوں مناسب ہے (ضروری)۔", approve:"نمائشی منصوبہ منظور کریں", approved:"نمائشی منصوبہ منظور ہوگیا", blocked:"منظوری کے لیے نشان زد گروپس دیکھیں اور وجہ درج کریں۔", queueOrder:"ترجیحی قطار", basis:"تخمینی", rank:"ترجیح", reset:"مسودہ دوبارہ ترتیب دیں", weightsHint:"وزن بدل کر فرضی قطار کا اثر دیکھیں۔ اسکور منظور شدہ پالیسی نہیں۔", equal:"برابر تقسیم کا معیار", complete:"مکمل", flagged:"جائزہ لازم", approvedNote:"صرف اس پیش منظر میں مقامی طور پر درج۔ بیک اینڈ یا لیجر تبدیل نہیں ہوا۔",
    liveBadge:"تخمینی · API سے ری پلے منصوبہ", liveIntro:"ری پلے کے کسی دن کا منصوبہ بنائیں، کم اعتماد والے گروپس جانچیں اور وجہ کے ساتھ منظور کریں۔", liveCaveat:"یہاں ہر منصوبہ تخمینی ہے: مارچ تا جولائی 2025 کا ری پلے، ماہانہ مجموعے حقیقی، روزانہ آمد فرضی۔ منظوری سرور پر محفوظ ہو کر لیجر میں درج ہوتی ہے؛ اس سے ٹینکر نہیں بھیجے جاتے۔", dataSource:"ڈیٹا کا ذریعہ", liveNote:"یہ ڈیٹا ابھی JalLekha API سے آیا ہے۔ منصوبے محفوظ شدہ A8 ری پلے (تخمینی) سے بنتے ہیں، آج کے کام سے نہیں۔", loadingNote:"براہِ راست منصوبوں کی جانچ ہو رہی ہے؛ تب تک نمونہ منصوبہ۔", signInNote:"براہِ راست منصوبوں کے لیے افسر ٹوکن سے سائن ان کریں۔ نمونہ منصوبہ دکھایا جا رہا ہے۔", forbiddenNote:"اس اکاؤنٹ کو افسر کے منصوبے دیکھنے کی اجازت نہیں۔ نمونہ منصوبہ دکھایا جا رہا ہے۔", unreachableNote:"سرور سے رابطہ نہیں ہو سکا۔ نمونہ منصوبہ دکھایا جا رہا ہے۔", serverErrorNote:"سرور نے خرابی بتائی۔ نمونہ منصوبہ دکھایا جا رہا ہے۔", incompleteNote:"سرور کا جواب نامکمل تھا۔ نمونہ منصوبہ دکھایا جا رہا ہے۔",
    plans:"محفوظ منصوبے", noPlans:"ابھی کوئی منصوبہ محفوظ نہیں۔ ری پلے کے کسی دن کا منصوبہ بنائیں۔", showing:"{total} میں سے {shown} منصوبے دکھائے جا رہے ہیں۔", statusDraft:"مسودہ", statusApproved:"منظور شدہ", flagsProgress:"{total} نشان زد گروپس میں سے {checked} جانچے گئے", open:"کھولیں", opened:"کھلا ہے", openAria:"{day} کا منصوبہ کھولیں",
    buildTitle:"کسی دن کا منصوبہ بنائیں", buildHint:"ری پلے کی مدت (2025-03-01 تا 2025-07-31) میں سے دن چنیں۔", build:"منصوبہ بنائیں", building:"منصوبہ بن رہا ہے… سرور شروع ہونے کے بعد پہلے منصوبے میں تقریباً 15 سیکنڈ لگ سکتے ہیں۔", buildDone:"{day} کا منصوبہ بن کر کھل گیا۔", buildExisting:"{day} کا منصوبہ پہلے سے موجود تھا؛ اب کھلا ہے۔", buildOutside:"یہ دن ری پلے کی مدت (2025-03-01 تا 2025-07-31) سے باہر ہے۔", buildInvalid:"درست تاریخ (YYYY-MM-DD) درج کریں۔",
    pickPlan:"جائزے کے لیے محفوظ منصوبہ کھولیں یا نیا بنائیں۔", loadingPlan:"منصوبہ لوڈ ہو رہا ہے…", planFailed:"یہ منصوبہ لوڈ نہیں ہو سکا۔", planIncomplete:"اس منصوبے کے لیے سرور کا جواب نامکمل تھا، اس لیے نہیں دکھایا گیا۔",
    liveTrips:"منصوبے کے ٹرپ", served:"پوری ہونے والی بکنگ", waitingCount:"{count} منتظر", liveQueue:"آج کی قطار کے گروپس", queueNote:"تمام اسٹیشنوں پر ہر گروپ کی پوری ہونے والی بکنگ؛ ہر اسٹیشن پر منصفانہ قطار (DRR)۔", servedBookings:"پوری ہونے والی بکنگ", confidenceLabel:"اعتماد",
    checkTitle:"جانچ کے لیے نشان زد گروپس", thresholdNoteDerived:"اعتماد کی حد {threshold} جان بوجھ کر غلط ڈیٹا والے مصنوعی ری پلے پر چنی گئی (T9): یہ وہ کم ترین حد ہے جس نے ہر بار بغیر نشان والے 90% فیصلے درست رکھے۔ یہ تبھی درست ہے جب اصل ڈیٹا کی غلطیاں فرض کیے گئے انداز میں ہوں۔ اس منصوبے کے {groups} گروپس میں سے {below} اس سے نیچے ہیں اور منظوری سے پہلے افسر کی جانچ ضروری ہے۔", thresholdNote:"اعتماد کی حد {threshold} عارضی ہے اور جانچی نہیں گئی (T9): ری پلے حدوں میں فرق نہیں بتا سکا، اس لیے یہ عارضی حد ہے، تصدیق شدہ نہیں۔ اس منصوبے کے {groups} گروپس میں سے {below} اس سے کم ہیں اور منظوری سے پہلے افسر کی جانچ ضروری ہے۔", progress:"{total} میں سے {checked} جانچے گئے", checkReason:"جانچ کی وجہ (ہر نشان زد گروپ کے لیے)", checkReasonHint:"آپ نے کیا جانچا؟ ہر گروپ کے لیے ضروری۔", markChecked:"جانچا ہوا نشان لگائیں", markAria:"{group} کو جانچا ہوا نشان لگائیں", checkedLabel:"جانچا گیا", needsCheck:"جانچ ضروری", inputsOk:"حد سے اوپر", checkDone:"{group} کو جانچا ہوا نشان لگا دیا گیا۔", allChecked:"تمام نشان زد گروپس جانچے جا چکے ہیں۔", noFlags:"اس منصوبے میں کوئی گروپ حد سے کم نہیں۔",
    officerId:"افسر آئی ڈی", officerIdHint:"آپ کے ٹوکن میں افسر آئی ڈی نہیں۔ اپنی آئی ڈی لکھیں؛ یہ ہر جانچ اور منظوری کے ساتھ درج ہوتی ہے۔", needOfficer:"پہلے اپنی افسر آئی ڈی درج کریں۔",
    liveSchedule:"طے شدہ فراہمی", liveScheduleNote:"طے شدہ فراہمی کے وارڈ (لیٹر تخمینی)۔ جس وارڈ کو سروس پوائنٹ درکار ہے اس کا ابھی کوئی راستہ نہیں۔", ward:"وارڈ", litres:"لیٹر / کم از کم", scheduleStatus:"حالت", floorNotMet:"کم از کم سے کم", floorMet:"کم از کم پورا", needsServicePoint:"سروس پوائنٹ درکار",
    liveOutage:"تعطل کا جواب", outageCritical:"نازک علاقے", outageAllocations:"تقسیم", outageUnused:"غیر استعمال شدہ تعطل لیٹر", outageDebt:"پانی کے بقایا میں شمار", yes:"ہاں", no:"نہیں",
    approveLive:"منصوبہ منظور کریں", approving:"منظور ہو رہا ہے…", approveBlockedFlags:"پہلے تمام نشان زد گروپس جانچیں ({total} میں سے {checked})۔", approveNeedReason:"منظوری کے لیے وجہ درج کریں۔", alreadyApproved:"یہ منصوبہ پہلے ہی منظور ہو چکا ہے۔", approveReady:"منظوری سرور پر محفوظ ہو کر لیجر میں درج ہوتی ہے۔", approvedLive:"منصوبہ {officer} نے منظور کیا", approvedLiveNote:"سرور پر محفوظ اور لیجر میں درج۔ تخمینی منصوبہ: کوئی ٹینکر نہیں بھیجا جاتا۔",
    refused:"سرور نے انکار کیا:", unreachableShort:"سرور سے رابطہ نہیں ہو سکا۔ دوبارہ کوشش کریں۔",
    weightsTitle:"ترجیحی وزن", wWad:"پانی تک رسائی", wCad:"فون تک رسائی", wHardship:"مشکل حالات", weightDefault:"طے شدہ", weightsLiveHint:"منصوبہ بناتے وقت ہر ضرورت کو کتنی اہمیت دینی ہے، چنیں۔ وزن صرف چند ٹرپ بدل سکتے ہیں: روزانہ صلاحیت ان کے اثر کو محدود کرتی ہے۔ دوسرے وزن والا منصوبہ الگ منصوبہ ہے اور اپنے وزن کے ساتھ لیجر میں درج ہوتا ہے۔", weightsReset:"وزن دوبارہ ترتیب دیں", weightsBadge:"وزن {wad} / {cad} / {hardship}", openWeightedAria:"{day} کا منصوبہ کھولیں، وزن {wad} / {cad} / {hardship}", gainsTitle:"کسے فائدہ، کسے نقصان", gainsIntro:"ان وزنوں کے ساتھ {day} کے بک شدہ ٹرپ کا طے شدہ وزن سے موازنہ۔ وہی ٹرپ مختلف طرح بانٹے جاتے ہیں۔", gainsLoading:"طے شدہ منصوبے سے موازنہ ہو رہا ہے…", gainers:"ٹرپ بڑھے", losers:"ٹرپ گھٹے", servedWas:"طے شدہ", servedNow:"نئے وزن کے ساتھ", noChanges:"ان وزنوں سے کسی گروپ کے ٹرپ نہیں بدلتے۔", compareFailed:"موازنہ لوڈ نہیں ہو سکا۔", gainsNote:"صلاحیت وزن کے اثر کو محدود کرتی ہے، اس لیے تبدیلیاں عموماً چھوٹی ہوتی ہیں۔",
    bookingsTitle:"فراہم کردہ بکنگ سے بنائیں", bookingsHint:"براہِ راست بکنگ فیڈ موجود نہیں، اس لیے منصوبہ وہی بکنگ استعمال کرتا ہے جو آپ دیں۔ انہیں CSV کے طور پر چسپاں کریں یا فائل چنیں۔ کالم: booking_id، section، arrived_at (ٹائم زون کے ساتھ)؛ اختیاری: consumer_id، category، tier۔", bookingsDay:"ان بکنگ کا دن", bookingsText:"بکنگ (CSV)", bookingsFile:"یا CSV فائل چنیں", bookingsWeightsNote:"اوپر منتخب کردہ ترجیحی وزن استعمال ہوتے ہیں۔", bookingsBuild:"بکنگ سے منصوبہ بنائیں", bookingsBuilding:"بکنگ سے منصوبہ بن رہا ہے…", bookingsNeed:"بکنگ کا دن چنیں اور کم از کم ایک بکنگ چسپاں کریں۔", bookingsDone:"{day} کے لیے {count} بکنگ سے منصوبہ بن گیا۔", csvMissing:"کالم موجود نہیں: {name}۔ پہلی لائن میں booking_id، section اور arrived_at ہونے چاہییں۔", csvUnknown:"نامعلوم کالم: {name}۔", csvShape:"لائن {line}: {expected} قدریں درکار تھیں، {found} ملیں۔", csvTier:"لائن {line}: tier 0، 1 یا 2 ہونا چاہیے۔", suppliedLabel:"فراہم کردہ بکنگ", openSuppliedAria:"فراہم کردہ بکنگ سے بنا {day} کا منصوبہ کھولیں", suppliedNote:"{day} کے لیے فراہم کردہ {count} بکنگ سے بنا، ری پلے سے نہیں۔ بکنگ جیسی دی گئیں (یہاں تصدیق نہیں)؛ صلاحیت فرضی بیڑے کا منظرنامہ (ASSUMED) ہے۔" },
  hi: { title:"दैनिक आवंटन योजना", intro:"मसौदा कतार, तय आपूर्ति, भरोसे की जाँच और प्राथमिकता भार का असर देखें।", demo:"सिमुलेशन · लाइव आवंटन API नहीं", caveat:"इस स्क्रीन के सभी वार्ड नाम, इनपुट, ट्रिप संख्या और परिणाम काल्पनिक उदाहरण हैं। यहाँ मंज़ूरी से टैंकर नहीं भेजे जाते और न ही पात्रता बदलती है।", draft:"अधिकारी की समीक्षा के लिए मसौदा", trips:"डेमो ट्रिप", reserve:"निर्धारित आरक्षित ट्रिप", outage:"आपूर्ति बाधा प्रतिक्रिया", queue:"न्याय कतार ट्रिप", weights:"प्राथमिकता भार", need:"ज़रूरत संकेत", gap:"सेवा अंतर", debt:"पानी बकाया", beneficiaries:"किसे लाभ", recipient:"नमूना वार्ड", allocation:"ट्रिप", change:"समान बाँट से बदलाव", confidence:"भरोसे की जाँच", confident:"इनपुट मौजूद", review:"मानवीय समीक्षा ज़रूरी", reviewText:"इस नमूना समूह के साक्ष्य अधूरे हैं। मंज़ूरी से पहले समीक्षा करें।", markReviewed:"मैंने इस समूह की समीक्षा की", schedule:"उदाहरण समय-सारणी", time:"समय", stop:"स्थान", quantity:"लोड", scheduleNote:"यह केवल उदाहरण है; सेवा केंद्र सूची जुड़ी नहीं है।", reason:"अधिकारी की मंज़ूरी का कारण", reasonHint:"बताएँ कि यह मसौदा उचित क्यों है (ज़रूरी)।", approve:"डेमो योजना मंज़ूर करें", approved:"डेमो योजना मंज़ूर", blocked:"मंज़ूरी के लिए चिह्नित समूह देखें और कारण लिखें।", queueOrder:"प्राथमिकता कतार", basis:"सिमुलेशन", rank:"प्राथमिकता", reset:"मसौदा रीसेट करें", weightsHint:"भार बदलकर काल्पनिक कतार में बदलाव देखें। स्कोर सत्यापित नीति नहीं हैं।", equal:"समान बाँट संदर्भ", complete:"पूरा", flagged:"समीक्षा ज़रूरी", approvedNote:"केवल इस पूर्वावलोकन में स्थानीय रूप से दर्ज। बैकएंड या लेजर नहीं बदला।",
    liveBadge:"सिमुलेशन · API से रीप्ले योजना", liveIntro:"रीप्ले के किसी दिन की योजना बनाएँ, कम भरोसे वाले समूह जाँचें और कारण के साथ मंज़ूर करें।", liveCaveat:"यहाँ हर योजना सिमुलेशन है: मार्च–जुलाई 2025 का रीप्ले, मासिक योग वास्तविक, दैनिक आगमन काल्पनिक। मंज़ूरी सर्वर पर सहेजी जाती है और लेजर में दर्ज होती है; इससे टैंकर नहीं भेजे जाते।", dataSource:"डेटा स्रोत", liveNote:"यह डेटा अभी JalLekha API से आया है। योजनाएँ सहेजे गए A8 रीप्ले (सिमुलेशन) से बनती हैं, आज के संचालन से नहीं।", loadingNote:"लाइव योजनाओं की जाँच हो रही है; तब तक नमूना योजना।", signInNote:"लाइव योजनाएँ देखने के लिए अधिकारी टोकन से साइन इन करें। नमूना योजना दिखाई जा रही है।", forbiddenNote:"इस खाते को अधिकारी योजनाएँ देखने की अनुमति नहीं है। नमूना योजना दिखाई जा रही है।", unreachableNote:"सर्वर से संपर्क नहीं हो सका। नमूना योजना दिखाई जा रही है।", serverErrorNote:"सर्वर ने त्रुटि लौटाई। नमूना योजना दिखाई जा रही है।", incompleteNote:"सर्वर का उत्तर अधूरा था। नमूना योजना दिखाई जा रही है।",
    plans:"सहेजी गई योजनाएँ", noPlans:"अभी कोई योजना सहेजी नहीं गई। रीप्ले के किसी दिन की योजना बनाएँ।", showing:"{total} में से {shown} योजनाएँ दिखाई जा रही हैं।", statusDraft:"मसौदा", statusApproved:"मंज़ूर", flagsProgress:"{total} चिह्नित समूहों में से {checked} जाँचे गए", open:"खोलें", opened:"खुली है", openAria:"{day} की योजना खोलें",
    buildTitle:"किसी दिन की योजना बनाएँ", buildHint:"रीप्ले अवधि (2025-03-01 से 2025-07-31) में से एक दिन चुनें।", build:"योजना बनाएँ", building:"योजना बन रही है… सर्वर शुरू होने के बाद पहली योजना में लगभग 15 सेकंड लग सकते हैं।", buildDone:"{day} की योजना बनकर खुल गई।", buildExisting:"{day} की योजना पहले से थी; अब खुली है।", buildOutside:"यह दिन रीप्ले अवधि (2025-03-01 से 2025-07-31) से बाहर है।", buildInvalid:"सही तारीख (YYYY-MM-DD) लिखें।",
    pickPlan:"समीक्षा के लिए सहेजी गई योजना खोलें या नई बनाएँ।", loadingPlan:"योजना लोड हो रही है…", planFailed:"यह योजना लोड नहीं हो सकी।", planIncomplete:"इस योजना के लिए सर्वर का उत्तर अधूरा था, इसलिए नहीं दिखाई गई।",
    liveTrips:"योजना के ट्रिप", served:"पूरी हुई बुकिंग", waitingCount:"{count} प्रतीक्षा में", liveQueue:"आज की कतार के समूह", queueNote:"सभी स्टेशनों पर हर समूह की पूरी हुई बुकिंग; हर स्टेशन पर न्याय कतार (DRR)।", servedBookings:"पूरी हुई बुकिंग", confidenceLabel:"भरोसा",
    checkTitle:"जाँच के लिए चिह्नित समूह", thresholdNoteDerived:"भरोसे की सीमा {threshold} जानबूझकर गलत डेटा वाले सिम्युलेटेड रीप्ले पर चुनी गई (T9): यह वह सबसे कम सीमा है जिसने हर बार बिना चिह्नित 90% फैसले सही रखे। यह तभी लागू है जब असली डेटा की गलतियाँ माने गए ढंग से हों। इस योजना के {groups} समूहों में से {below} इससे नीचे हैं और मंज़ूरी से पहले अधिकारी की जाँच ज़रूरी है।", thresholdNote:"भरोसे की सीमा {threshold} अस्थायी है और कैलिब्रेट नहीं की गई (T9): रीप्ले सीमाओं में फ़र्क़ नहीं बता सका, इसलिए यह अस्थायी सीमा है, सत्यापित नहीं। इस योजना के {groups} समूहों में से {below} इससे नीचे हैं और मंज़ूरी से पहले अधिकारी की जाँच ज़रूरी है।", progress:"{total} में से {checked} जाँचे गए", checkReason:"जाँच का कारण (हर चिह्नित समूह के लिए)", checkReasonHint:"आपने क्या जाँचा? हर समूह के लिए ज़रूरी।", markChecked:"जाँचा हुआ चिह्नित करें", markAria:"{group} को जाँचा हुआ चिह्नित करें", checkedLabel:"जाँचा गया", needsCheck:"जाँच ज़रूरी", inputsOk:"सीमा से ऊपर", checkDone:"{group} जाँचा हुआ चिह्नित किया गया।", allChecked:"सभी चिह्नित समूह जाँचे जा चुके हैं।", noFlags:"इस योजना में कोई समूह सीमा से नीचे नहीं है।",
    officerId:"अधिकारी आईडी", officerIdHint:"आपके टोकन में अधिकारी आईडी नहीं है। अपनी आईडी लिखें; यह हर जाँच और मंज़ूरी के साथ दर्ज होती है।", needOfficer:"पहले अपनी अधिकारी आईडी लिखें।",
    liveSchedule:"निर्धारित आपूर्ति", liveScheduleNote:"निर्धारित आपूर्ति वाले वार्ड (लीटर सिमुलेशन)। जिस वार्ड को सेवा केंद्र चाहिए उसका अभी कोई मार्ग नहीं है।", ward:"वार्ड", litres:"लीटर / न्यूनतम", scheduleStatus:"स्थिति", floorNotMet:"न्यूनतम से कम", floorMet:"न्यूनतम पूरा", needsServicePoint:"सेवा केंद्र चाहिए",
    liveOutage:"आपूर्ति बाधा प्रतिक्रिया", outageCritical:"गंभीर क्षेत्र", outageAllocations:"आवंटन", outageUnused:"बिना उपयोग के बाधा लीटर", outageDebt:"पानी बकाया में गिना जाता है", yes:"हाँ", no:"नहीं",
    approveLive:"योजना मंज़ूर करें", approving:"मंज़ूर हो रही है…", approveBlockedFlags:"पहले सभी चिह्नित समूह जाँचें ({total} में से {checked})।", approveNeedReason:"मंज़ूरी के लिए कारण लिखें।", alreadyApproved:"यह योजना पहले ही मंज़ूर है।", approveReady:"मंज़ूरी सर्वर पर सहेजी जाती है और लेजर में दर्ज होती है।", approvedLive:"योजना {officer} ने मंज़ूर की", approvedLiveNote:"सर्वर पर सहेजी गई और लेजर में दर्ज। सिमुलेशन योजना: कोई टैंकर नहीं भेजा जाता।",
    refused:"सर्वर ने मना किया:", unreachableShort:"सर्वर से संपर्क नहीं हो सका। फिर कोशिश करें।",
    weightsTitle:"प्राथमिकता भार", wWad:"पानी की उपलब्धता", wCad:"फ़ोन की उपलब्धता", wHardship:"कठिनाई", weightDefault:"डिफ़ॉल्ट", weightsLiveHint:"योजना बनाते समय हर ज़रूरत को कितना महत्व देना है, चुनें। भार केवल कुछ ट्रिप ही बदल सकते हैं: दैनिक क्षमता उनके असर को सीमित करती है। अलग भार वाली योजना एक अलग योजना है और अपने भार के साथ लेजर में दर्ज होती है।", weightsReset:"भार रीसेट करें", weightsBadge:"भार {wad} / {cad} / {hardship}", openWeightedAria:"{day} की योजना खोलें, भार {wad} / {cad} / {hardship}", gainsTitle:"किसे लाभ, किसे नुकसान", gainsIntro:"इन भारों के साथ {day} की बुक की गई ट्रिप की तुलना डिफ़ॉल्ट भार से। वही ट्रिप अलग तरह से बँटती हैं।", gainsLoading:"डिफ़ॉल्ट योजना से तुलना हो रही है…", gainers:"ट्रिप बढ़ीं", losers:"ट्रिप घटीं", servedWas:"डिफ़ॉल्ट", servedNow:"नए भार के साथ", noChanges:"इन भारों से किसी समूह की ट्रिप संख्या नहीं बदलती।", compareFailed:"तुलना लोड नहीं हो सकी।", gainsNote:"क्षमता भार के असर को सीमित करती है, इसलिए बदलाव आमतौर पर छोटे होते हैं।",
    bookingsTitle:"उपलब्ध कराई गई बुकिंग से बनाएँ", bookingsHint:"लाइव बुकिंग फ़ीड नहीं है, इसलिए योजना वही बुकिंग इस्तेमाल करती है जो आप देते हैं। उन्हें CSV के रूप में चिपकाएँ या फ़ाइल चुनें। कॉलम: booking_id, section, arrived_at (टाइम ज़ोन के साथ); वैकल्पिक: consumer_id, category, tier।", bookingsDay:"इन बुकिंग का दिन", bookingsText:"बुकिंग (CSV)", bookingsFile:"या CSV फ़ाइल चुनें", bookingsWeightsNote:"ऊपर चुने गए प्राथमिकता भार इस्तेमाल होते हैं।", bookingsBuild:"बुकिंग से योजना बनाएँ", bookingsBuilding:"बुकिंग से योजना बन रही है…", bookingsNeed:"बुकिंग का दिन चुनें और कम से कम एक बुकिंग चिपकाएँ।", bookingsDone:"{day} के लिए {count} बुकिंग से योजना बन गई।", csvMissing:"कॉलम नहीं है: {name}। पहली पंक्ति में booking_id, section और arrived_at होने चाहिए।", csvUnknown:"अज्ञात कॉलम: {name}।", csvShape:"पंक्ति {line}: {expected} मान चाहिए थे, {found} मिले।", csvTier:"पंक्ति {line}: tier 0, 1 या 2 होना चाहिए।", suppliedLabel:"उपलब्ध कराई गई बुकिंग", openSuppliedAria:"उपलब्ध कराई गई बुकिंग से बनी {day} की योजना खोलें", suppliedNote:"{day} के लिए दी गई {count} बुकिंग से बनी, रीप्ले से नहीं। बुकिंग जैसी दी गईं (यहाँ सत्यापित नहीं); क्षमता एक अनुमानित बेड़ा परिदृश्य (ASSUMED) है।" },
} satisfies Record<Locale, Record<string, string>>;

type Copy = (typeof copy)["en"];
type Note = { tone: "ok" | "error"; text: string };

const fill = (template: string, vars: Record<string, string | number>) => template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ""));

/** The last non-null value, kept only while a refresh is in flight, so a reload does not blank the screen. */
function useKeptWhileLoading<T>(value: T | null, loading: boolean): T | null {
  const [kept, setKept] = useState<T | null>(null);
  if (value !== null && value !== kept) setKept(value);
  if (value === null && !loading && kept !== null) setKept(null);
  return value ?? (loading ? kept : null);
}

export default function PlanExperience() {
  const { locale } = useLocale();
  const t: Copy = copy[locale];
  // Live plans need an officer token; signed out (or rejected) the screen does not call the API.
  const { status, userId } = useAuth();
  const enabled = status !== "anonymous" && status !== "rejected";
  const list = useApi<unknown>(enabled ? "/plans?limit=200" : null);
  const adapted = useMemo(() => (list.live ? adaptPlanList(list.data) : null), [list.live, list.data]);
  const plans = useKeptWhileLoading(enabled ? adapted : null, list.loading);
  const reason: FallbackReason | null = plans ? null : !enabled ? "signIn" : list.error ? planReason(list.error) : list.live ? "incomplete" : null;
  const notes: Record<FallbackReason, string> = { signIn: t.signInNote, forbidden: t.forbiddenNote, unreachable: t.unreachableNote, serverError: t.serverErrorNote, incomplete: t.incompleteNote };
  const notice = <div className="plan-notice plan-source"><strong>{t.dataSource}: <DataSourceChip state={{ live: plans !== null, loading: !plans && reason === null, error: reason === "unreachable" ? list.error : null }} /></strong><span>{plans ? t.liveNote : reason ? notes[reason] : t.loadingNote}</span></div>;
  if (!plans) return <SamplePlan t={t} notice={notice} />;
  return <LivePlans t={t} locale={locale} notice={notice} plans={plans} reloadList={list.reload} userId={userId} />;
}

function LivePlans({ t, locale, notice, plans, reloadList, userId }: { t: Copy; locale: Locale; notice: ReactNode; plans: PlanList; reloadList: () => void; userId: string | null }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [day, setDay] = useState("");
  const [building, setBuilding] = useState(false);
  const [buildNote, setBuildNote] = useState<Note | null>(null);
  const [officerInput, setOfficerInput] = useState("");
  const [checkReason, setCheckReason] = useState("");
  const [checkNote, setCheckNote] = useState<Note | null>(null);
  const [approvalReason, setApprovalReason] = useState("");
  const [approveNote, setApproveNote] = useState<Note | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // the group being checked, or "approve"
  const defaults = plans.defaultWeights ?? FALLBACK_WEIGHTS;
  const maxWeight = plans.maxWeight ?? FALLBACK_MAX_WEIGHT;
  const [edited, setEdited] = useState<Weights | null>(null); // null: the defaults
  const [suppliedDay, setSuppliedDay] = useState("");
  const [suppliedText, setSuppliedText] = useState("");
  const [suppliedBusy, setSuppliedBusy] = useState(false);
  const [suppliedNote, setSuppliedNote] = useState<Note | null>(null);
  const [suppliedProblems, setSuppliedProblems] = useState<string[]>([]);
  const chosen = edited ?? defaults;

  const base = selectedId ? `/plans/${encodeURIComponent(selectedId)}` : null;
  const planApi = useApi<unknown>(base);
  const confidenceApi = useApi<unknown>(base && `${base}/confidence`);
  const adapted = useMemo(() => (planApi.live && confidenceApi.live ? adaptLivePlan(planApi.data, confidenceApi.data) : null), [planApi.live, planApi.data, confidenceApi.live, confidenceApi.data]);
  const kept = useKeptWhileLoading(adapted, planApi.loading || confidenceApi.loading);
  const plan = kept && kept.id === selectedId ? kept : null;
  const planError = planApi.error ?? confidenceApi.error;
  // A plan with other weights is compared with the default plan for the same day.
  const weighted = plan !== null && plan.weights !== null && !plan.weights.isDefault;
  const compareApi = useApi<unknown>(weighted && base ? `${base}/compare` : null);
  const compare = useMemo(() => (compareApi.live ? adaptCompare(compareApi.data) : null), [compareApi.live, compareApi.data]);

  const numbers = new Intl.NumberFormat(locale === "ur" ? "ur-PK" : locale, { maximumFractionDigits: 0 });
  const n = (value: number | null) => (value === null ? "—" : numbers.format(value));
  const score = (value: number | null) => (value === null ? "—" : value.toFixed(2));
  const statusLabel = (value: string) => (value === "APPROVED" ? t.statusApproved : value === "DRAFT" ? t.statusDraft : value);
  const officerId = (userId ?? officerInput).trim();
  const nameOf = (group: string) => plan?.names[group] ?? plan?.names[`ward:${group}`] ?? null;
  const label = (group: string) => nameOf(group) ?? group;
  const sameWeights = (a: Weights, b: Weights) => a.wad === b.wad && a.cad === b.cad && a.hardship === b.hardship;
  const signed = (change: number) => (change > 0 ? `+${n(change)}` : `\u2212${n(Math.abs(change))}`);
  const failure = (cause: unknown) => (cause instanceof ApiError && cause.status !== 0 ? `${t.refused} ${cause.message}` : t.unreachableShort);

  function open(id: string) {
    setSelectedId(id);
    setCheckNote(null);
    setApproveNote(null);
  }

  async function build(event: FormEvent) {
    event.preventDefault();
    if (!day || building) return;
    // Checked here (the form is noValidate) so the message is in the screen's language.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return setBuildNote({ tone: "error", text: t.buildInvalid });
    if (day < REPLAY_FIRST_DAY || day > REPLAY_LAST_DAY) return setBuildNote({ tone: "error", text: t.buildOutside });
    const existed = plans.items.some((item) => item.day === day && sameWeights(item.weights ?? defaults, chosen));
    setBuilding(true);
    setBuildNote(null);
    try {
      const built = await apiFetch<{ plan_id: string }>("/plans", { method: "POST", body: { day, weights: chosen } });
      open(built.plan_id);
      setBuildNote({ tone: "ok", text: fill(existed ? t.buildExisting : t.buildDone, { day }) });
      reloadList();
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : 0;
      setBuildNote({ tone: "error", text: status === 404 ? t.buildOutside : status === 422 ? t.buildInvalid : failure(cause) });
    } finally {
      setBuilding(false);
    }
  }

  const csvMessage = (problem: CsvProblem) =>
    problem.code === "missingColumn" ? fill(t.csvMissing, { name: problem.name })
      : problem.code === "unknownColumn" ? fill(t.csvUnknown, { name: problem.name })
      : problem.code === "rowShape" ? fill(t.csvShape, { line: problem.line, expected: problem.expected, found: problem.found })
      : fill(t.csvTier, { line: problem.line });

  function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSuppliedText(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file);
  }

  async function buildSupplied(event: FormEvent) {
    event.preventDefault();
    if (suppliedBusy) return;
    setSuppliedNote(null);
    const { rows, errors } = parseBookingsCsv(suppliedText);
    if (errors.length > 0) return setSuppliedProblems(errors.slice(0, 8).map(csvMessage));
    setSuppliedProblems([]);
    if (!suppliedDay || rows.length === 0) return setSuppliedNote({ tone: "error", text: t.bookingsNeed });
    setSuppliedBusy(true);
    try {
      const built = await apiFetch<{ plan_id: string }>("/plans", { method: "POST", body: { day: suppliedDay, weights: chosen, bookings: rows } });
      open(built.plan_id);
      setSuppliedNote({ tone: "ok", text: fill(t.bookingsDone, { count: rows.length, day: suppliedDay }) });
      reloadList();
    } catch (cause) {
      setSuppliedNote({ tone: "error", text: cause instanceof ApiError && cause.status === 422 ? cause.message : failure(cause) });
    } finally {
      setSuppliedBusy(false);
    }
  }

  async function check(group: string) {
    if (!plan || busy) return;
    setBusy(group);
    setCheckNote(null);
    try {
      await apiFetch(`/plans/${encodeURIComponent(plan.id)}/groups/${encodeURIComponent(group)}/check`, { method: "POST", body: { officer_id: officerId, reason: checkReason.trim() } });
      setCheckNote({ tone: "ok", text: fill(t.checkDone, { group: label(group) }) });
      planApi.reload();
      reloadList();
    } catch (cause) {
      setCheckNote({ tone: "error", text: failure(cause) });
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!plan || busy) return;
    setBusy("approve");
    setApproveNote(null);
    try {
      await apiFetch(`/plans/${encodeURIComponent(plan.id)}/approve`, { method: "POST", body: { officer_id: officerId, reason: approvalReason.trim() } });
      planApi.reload();
      reloadList();
    } catch (cause) {
      setApproveNote({ tone: "error", text: failure(cause) });
    } finally {
      setBusy(null);
    }
  }

  const canCheck = officerId.length > 0 && checkReason.trim().length > 0 && busy === null;
  const blockedBy = !plan ? null : plan.approved ? t.alreadyApproved : plan.unchecked.length > 0 ? fill(t.approveBlockedFlags, { checked: plan.checkedTotal, total: plan.flagsTotal }) : !officerId ? t.needOfficer : !approvalReason.trim() ? t.approveNeedReason : null;

  const tag = plan?.source === "section_month" ? "DERIVED · ASSUMED CAPACITY" : "SIMULATION"; // a plan by section uses real monthly totals
  return <div className="plan-page">
    <header className="plan-heading"><div><p className="eyebrow">{t.draft}</p><h1>{t.title}</h1><p className="muted">{t.liveIntro}</p></div><span className="forecast-demo-badge">{t.liveBadge}</span></header>
    {notice}
    <div className="plan-notice"><strong>{plan?.source === "section_month" ? "This plan uses the real monthly booking totals of each HMWSSB section, divided by the days of the month; the trips available are an assumption. Approval is saved on the server and logged in the ledger; it does not dispatch tankers." : t.liveCaveat}</strong></div>

    <section className="plan-panel plan-plans" aria-labelledby="plan-list-title">
      <div className="plan-plans-list">
        <div className="plan-panel-title"><div><p className="eyebrow">{tag}</p><h2 id="plan-list-title">{t.plans}</h2></div></div>
        {plans.items.length === 0 ? <p className="plan-empty">{t.noPlans}</p> : <ul className="plan-list">{plans.items.map((item) => <li key={item.id} className={item.id === selectedId ? "plan-list-row selected" : "plan-list-row"}>
          <div><strong>{item.day}</strong><small><span>{statusLabel(item.status)}</span> · <span>{fill(t.flagsProgress, { checked: n(item.checkedTotal), total: n(item.flagsTotal) })}</span></small>{item.source === "supplied_bookings" && <small><span>{t.suppliedLabel}</span></small>}{item.source === "section_month" && <small><span>By section · real monthly totals</span></small>}{item.weights && <small><span>{fill(t.weightsBadge, { wad: item.weights.wad, cad: item.weights.cad, hardship: item.weights.hardship })}</span></small>}</div>
          <button className="button button-secondary" aria-label={item.weights ? fill(t.openWeightedAria, { day: item.day, wad: item.weights.wad, cad: item.weights.cad, hardship: item.weights.hardship }) : item.source === "supplied_bookings" ? fill(t.openSuppliedAria, { day: item.day }) : fill(t.openAria, { day: item.day })} aria-pressed={item.id === selectedId} onClick={() => open(item.id)}>{item.id === selectedId ? t.opened : t.open}</button>
        </li>)}</ul>}
        {plans.total > plans.items.length && <p className="plan-empty">{fill(t.showing, { shown: plans.items.length, total: plans.total })}</p>}
      </div>
      <SectionPlanForm weights={chosen} onBuilt={(id) => { open(id); reloadList(); }} />
      <form className="plan-build" noValidate onSubmit={(event) => void build(event)}>
        <label htmlFor="plan-build-day">{t.buildTitle}</label>
        <div className="plan-build-row"><input id="plan-build-day" type="date" min={REPLAY_FIRST_DAY} max={REPLAY_LAST_DAY} value={day} required onChange={(event) => setDay(event.target.value)} /><button className="button button-primary" type="submit" disabled={!day || building}>{t.build}</button></div>
        <small>{t.buildHint}</small>
        <fieldset className="plan-weights"><legend>{t.weightsTitle}</legend><small>{t.weightsLiveHint}</small>
          {(["wad", "cad", "hardship"] as const).map((key) => { const name = key === "wad" ? t.wWad : key === "cad" ? t.wCad : t.wHardship; return <label className="plan-slider" key={key}><span>{name} <output>{chosen[key]}</output> <small>({t.weightDefault} {defaults[key]})</small></span><input type="range" min="0" max={maxWeight} step="0.5" value={chosen[key]} aria-label={name} onChange={(event) => setEdited({ ...chosen, [key]: Number(event.target.value) })} /></label>; })}
          <button className="button button-secondary" type="button" disabled={edited === null} onClick={() => setEdited(null)}>{t.weightsReset}</button>
        </fieldset>
        {building && <p className="plan-message" role="status">{t.building}</p>}
        {buildNote && <p className={`plan-message ${buildNote.tone}`} role={buildNote.tone === "error" ? "alert" : "status"}>{buildNote.text}</p>}
      </form>
      <form className="plan-build plan-supplied" noValidate onSubmit={(event) => void buildSupplied(event)}>
        <strong>{t.bookingsTitle}</strong>
        <small>{t.bookingsHint}</small>
        <label htmlFor="plan-supplied-day">{t.bookingsDay}</label>
        <input id="plan-supplied-day" type="date" value={suppliedDay} onChange={(event) => setSuppliedDay(event.target.value)} />
        <label htmlFor="plan-supplied-text">{t.bookingsText}</label>
        <textarea id="plan-supplied-text" rows={6} spellCheck={false} value={suppliedText} placeholder={"booking_id,section,arrived_at\nB-1,ADARSHNAGAR,2026-10-03T05:30:00+05:30"} onChange={(event) => setSuppliedText(event.target.value)} />
        <label htmlFor="plan-supplied-file">{t.bookingsFile}</label>
        <input id="plan-supplied-file" type="file" accept=".csv,text/csv,text/plain" onChange={readFile} />
        <small>{t.bookingsWeightsNote}</small>
        <button className="button button-primary" type="submit" disabled={suppliedBusy}>{t.bookingsBuild}</button>
        {suppliedBusy && <p className="plan-message" role="status">{t.bookingsBuilding}</p>}
        {suppliedProblems.length > 0 && <div className="plan-message error" role="alert"><ul>{suppliedProblems.map((text) => <li key={text}>{text}</li>)}</ul></div>}
        {suppliedNote && <p className={`plan-message ${suppliedNote.tone}`} role={suppliedNote.tone === "error" ? "alert" : "status"}>{suppliedNote.text}</p>}
      </form>
    </section>

    {!selectedId && <p className="plan-empty">{t.pickPlan}</p>}
    {selectedId && !plan && (planError ? <div className="plan-message error" role="alert"><strong>{t.planFailed}</strong> {planError.status === 0 ? t.unreachableShort : planError.message}</div> : planApi.live && confidenceApi.live ? <div className="plan-message error" role="alert">{t.planIncomplete}</div> : <p className="plan-empty" role="status">{t.loadingPlan}</p>)}

    {plan && <>
      {plan.approved && <div className="plan-approved" role="status"><strong>{fill(t.approvedLive, { officer: plan.approvedBy ?? "—" })}</strong>{plan.approvalReason && <span>“{plan.approvalReason}”</span>}<span>{t.approvedLiveNote}</span></div>}
      {plan.source === "section_month" && <div className="plan-notice"><strong>{plan.basis.plan}</strong></div>}
      {plan.source === "supplied_bookings" && <div className="plan-notice"><strong>{fill(t.suppliedNote, { count: plan.bookingsSupplied ?? "?", day: plan.day })}</strong></div>}
      <section className="plan-summary" aria-label={`${t.draft} · ${plan.day}`}>
        <article><span>{t.liveTrips}</span><strong>{n(plan.trips)}</strong><small>{tag}</small></article>
        <article><span>{t.reserve}</span><strong>{n(plan.reserveTrips)}</strong><small>{tag}</small></article>
        <article><span>{t.outage}</span><strong>{n(plan.outageTrips)}</strong><small>{tag}</small></article>
        <article><span>{t.served}</span><strong>{n(plan.served)}</strong><small>{tag} · {fill(t.waitingCount, { count: n(plan.waiting) })}</small></article>
      </section>

      <PlanMap plan={plan} />

      {weighted && <section className="plan-panel plan-gains" aria-labelledby="plan-gains-title"><div className="plan-panel-title"><div><p className="eyebrow">{t.weightsTitle}</p><h2 id="plan-gains-title">{t.gainsTitle}</h2></div><span className="source-tag">{tag}</span></div>
        <p className="plan-threshold">{fill(t.gainsIntro, { day: plan.day })}</p>
        {compareApi.loading && <p className="plan-message" role="status">{t.gainsLoading}</p>}
        {!compareApi.loading && !compare && <p className="plan-message error" role="alert">{t.compareFailed}</p>}
        {compare && (compare.gainers.length === 0 && compare.losers.length === 0 ? <p className="plan-empty">{t.noChanges}</p> : <div className="plan-gains-columns">
          {([[t.gainers, compare.gainers], [t.losers, compare.losers]] as const).map(([title, items]) => items.length > 0 && <div key={title}><h3>{title}</h3><ul className="plan-gains-list">{items.map((row) => <li key={row.group}><div className="plan-queue-copy"><strong>{row.name ?? row.group}</strong><span>{t.servedWas} {n(row.servedDefault)} → {t.servedNow} {n(row.servedWeighted)}</span></div><b className={row.change > 0 ? "plan-gain" : "plan-loss"}>{signed(row.change)}</b></li>)}</ul></div>)}
        </div>)}
        <p className="plan-threshold">{t.gainsNote}</p>
      </section>}

      {!userId && <div className="plan-officer"><label htmlFor="plan-officer-id">{t.officerId}</label><input id="plan-officer-id" value={officerInput} required autoComplete="off" onChange={(event) => setOfficerInput(event.target.value)} /><small>{t.officerIdHint}</small></div>}

      <div className="plan-grid">
        <section className="plan-panel" aria-labelledby="plan-check-title"><div className="plan-panel-title"><div><p className="eyebrow">{t.confidence}</p><h2 id="plan-check-title">{t.checkTitle}</h2></div><span className="source-tag">{plan.confidence.thresholdBasis === "DERIVED" ? "DERIVED · SIMULATION" : "DERIVED · PROVISIONAL"}</span></div>
          <p className="plan-threshold">{fill(plan.confidence.thresholdBasis === "DERIVED" ? t.thresholdNoteDerived : t.thresholdNote, { threshold: score(plan.confidence.threshold), below: plan.confidence.belowThreshold, groups: plan.confidence.groups })}</p>
          <div className="plan-progress"><strong>{fill(t.progress, { checked: plan.checkedTotal, total: plan.flagsTotal })}</strong><span className="plan-progress-bar" aria-hidden="true"><i style={{ width: `${plan.flagsTotal ? (100 * plan.checkedTotal) / plan.flagsTotal : 100}%` }} /></span></div>
          {plan.flagsTotal === 0 ? <p className="plan-empty">{t.noFlags}</p> : <>
            {plan.unchecked.length > 0 && !plan.approved && <div className="plan-check-reason"><label htmlFor="plan-check-reason">{t.checkReason}</label><textarea id="plan-check-reason" value={checkReason} maxLength={500} placeholder={t.checkReasonHint} onChange={(event) => setCheckReason(event.target.value)} /></div>}
            {plan.unchecked.length === 0 && <p className="plan-reviewed-note" role="status">✓ {t.allChecked}</p>}
            <ul className="plan-flag-list">{plan.flags.map((flag) => <li className="plan-flag-row" key={flag.group}>
              <div className="plan-queue-copy"><strong>{label(flag.group)}</strong>{nameOf(flag.group) && <small>{flag.group}</small>}<span>{t.confidenceLabel} {score(flag.confidence)}</span>{flag.checked ? flag.checkReason && <small>“{flag.checkReason}”</small> : flag.reason && <small>{flag.reason}</small>}</div>
              {flag.checked ? <span className="evidence-status">✓ {t.checkedLabel}</span> : <button className="button button-secondary" aria-label={fill(t.markAria, { group: label(flag.group) })} disabled={!canCheck || plan.approved} onClick={() => void check(flag.group)}>{t.markChecked}</button>}
            </li>)}</ul>
            {!officerId && plan.unchecked.length > 0 && <p className="plan-message">{t.needOfficer}</p>}
          </>}
          {checkNote && <p className={`plan-message ${checkNote.tone}`} role={checkNote.tone === "error" ? "alert" : "status"}>{checkNote.text}</p>}
        </section>

        <section className="plan-panel" aria-labelledby="plan-queue-title"><div className="plan-panel-title"><div><p className="eyebrow">{t.queueOrder}</p><h2 id="plan-queue-title">{t.liveQueue}</h2></div><span className="source-tag">{tag}</span></div>
          <p className="plan-threshold">{t.queueNote}</p>
          <div className="plan-queue plan-queue-scroll">{plan.queue.map((row) => <article className="plan-queue-row" key={row.group}>
            <div className="plan-queue-copy"><strong>{label(row.group)}</strong><span>{t.servedBookings}: {n(row.served)} · {t.confidenceLabel} {score(row.confidence)}</span></div>
            <span className={row.needsCheck && !row.checked ? "evidence-status candidate-status" : "evidence-status"}>{row.needsCheck ? (row.checked ? t.checkedLabel : t.needsCheck) : t.inputsOk}</span>
          </article>)}</div>
        </section>
      </div>

      <section className="plan-panel plan-schedule" aria-labelledby="plan-schedule-title"><div className="plan-panel-title"><div><p className="eyebrow" id="plan-schedule-title">{t.liveSchedule}</p><h2>{plan.source === "section_month" ? "Sections the field-check screen flags (F4) get tankers although they did not book. Litres are the section’s need at 15 litres per person a day; the stop is an estimated centre and is not routed yet." : t.liveScheduleNote}</h2></div><span className="source-tag">{tag}</span></div>
        <div className="plan-schedule-table"><div className="plan-schedule-row plan-schedule-head"><span>{plan.source === "section_month" ? "Section" : t.ward}</span><span>{t.litres}</span><span>{t.scheduleStatus}</span></div>
          {plan.schedule.map((row) => <div className="plan-schedule-row" key={row.wardId}><span>{label(row.wardId)}</span><span>{n(row.litres)} / {n(row.floor)}</span><span className="plan-schedule-status"><span>{row.status === "FLOOR_NOT_MET" ? t.floorNotMet : row.status === "FLOOR_MET" ? t.floorMet : row.status ?? "—"}</span>{row.unrouted === "NEEDS_SERVICE_POINT" ? <small>{t.needsServicePoint}</small> : row.unrouted ? <small>{row.unrouted}</small> : null}</span></div>)}
        </div>
      </section>

      <section className="plan-panel" aria-labelledby="plan-outage-title"><div className="plan-panel-title"><div><p className="eyebrow">{tag}</p><h2 id="plan-outage-title">{t.liveOutage}</h2></div><span className="source-tag">DERIVED · ASSUMED</span></div>
        <dl className="plan-outage">
          <div><dt>{t.outageCritical}</dt><dd>{n(plan.outage.critical)}</dd></div>
          <div><dt>{t.outageAllocations}</dt><dd>{n(plan.outage.allocations)}</dd></div>
          <div><dt>{t.outageUnused}</dt><dd>{n(plan.outage.unusedLitres)}</dd></div>
          <div><dt>{t.outageDebt}</dt><dd>{plan.outage.countsTowardDebt === null ? "—" : plan.outage.countsTowardDebt ? t.yes : t.no}</dd></div>
        </dl>
        {Object.keys(plan.outage.basis).length > 0 && <ul className="plan-basis">{Object.entries(plan.outage.basis).map(([key, value]) => <li key={key}><strong>{key}</strong>: {value}</li>)}</ul>}
      </section>

      <section className="plan-approval"><div><p className="eyebrow">{t.reason}</p><label className="sr-only" htmlFor="plan-reason">{t.reason}</label><textarea id="plan-reason" value={approvalReason} maxLength={500} placeholder={t.reasonHint} disabled={plan.approved} onChange={(event) => setApprovalReason(event.target.value)} /></div>
        <div className="plan-approval-actions"><button className="button button-primary" disabled={blockedBy !== null || busy !== null} onClick={() => void approve()}>{busy === "approve" ? t.approving : t.approveLive}</button><small>{blockedBy ?? t.approveReady}</small>
          {approveNote && <p className={`plan-message ${approveNote.tone}`} role="alert">{approveNote.text}</p>}</div>
      </section>
      {plan.basis.plan && <p className="plan-footer-note">{plan.basis.plan} · {plan.basis.entitlement ?? "—"} · {plan.basis.flags ?? "—"}{plan.basis.weights ? ` · ${plan.basis.weights}` : ""}</p>}
    </>}
  </div>;
}

/** The labelled sample plan shown whenever live plans are not available (unchanged from before U7). */
function SamplePlan({ t, notice }: { t: Copy; notice: ReactNode }) {
  const [weights, setWeights] = useState({ need: 50, gap: 30, debt: 20 });
  const [reviewed, setReviewed] = useState(false);
  const [reason, setReason] = useState("");
  const [approved, setApproved] = useState(false);
  const weighted = useMemo(() => groups.map((group) => ({ ...group, score: (group.need * weights.need + group.gap * weights.gap + group.debt * weights.debt) / (weights.need + weights.gap + weights.debt || 1) })).sort((a, b) => b.score - a.score), [weights]);
  const ordered = [...weighted.filter((group) => group.confidence === "good"), ...weighted.filter((group) => group.confidence === "review")];
  const tripsFor = (id: string) => [6, 5, 4, 4][ordered.findIndex((group) => group.id === id)] ?? 0;
  const canApprove = reason.trim().length > 0 && reviewed;
  const updateWeight = (key: keyof typeof weights, value: number) => { setWeights((current) => ({ ...current, [key]: value })); setApproved(false); };

  return <div className="plan-page">
    <header className="plan-heading"><div><p className="eyebrow">{t.draft}</p><h1>{t.title}</h1><p className="muted">{t.intro}</p></div><span className="forecast-demo-badge">{t.demo}</span></header>
    {notice}
    <div className="plan-notice"><strong>{t.caveat}</strong></div>
    {approved && <div className="plan-approved" role="status"><strong>{t.approved}</strong><span>{t.approvedNote}</span></div>}
    <section className="plan-summary" aria-label={t.draft}><article><span>{t.trips}</span><strong>24</strong><small>SIMULATION</small></article><article><span>{t.reserve}</span><strong>3</strong><small>SIMULATION</small></article><article><span>{t.outage}</span><strong>2</strong><small>SIMULATION</small></article><article><span>{t.queue}</span><strong>19</strong><small>SIMULATION</small></article></section>

    <div className="plan-grid">
      <section className="plan-panel"><div className="plan-panel-title"><div><p className="eyebrow">{t.weights}</p><h2>{t.weightsHint}</h2></div><span className="source-tag">SIMULATION</span></div>
        {(["need", "gap", "debt"] as const).map((key) => <label className="plan-slider" key={key}><span>{t[key]} <output>{weights[key]}%</output></span><input type="range" min="0" max="100" step="5" value={weights[key]} onChange={(event) => updateWeight(key, Number(event.target.value))} aria-label={t[key]} /></label>)}
        <div className="plan-benefit"><h3>{t.beneficiaries}</h3><p>{t.equal}: 4.75 {t.allocation} {t.recipient.toLowerCase()}</p>{ordered.map((group) => <div className="plan-benefit-row" key={group.id}><span>{group.name}</span><strong>{tripsFor(group.id)} {t.allocation}</strong><small>{tripsFor(group.id) > 4.75 ? "+" : "−"}{Math.abs(tripsFor(group.id) - 4.75).toFixed(2)}</small></div>)}</div>
      </section>
      <section className="plan-panel"><div className="plan-panel-title"><div><p className="eyebrow">{t.confidence}</p><h2>{t.queueOrder}</h2></div><span className="source-tag">SIMULATION</span></div>
        <div className="plan-queue">{ordered.map((group, index) => <article className="plan-queue-row" key={group.id}><span className="plan-rank">{index + 1}</span><div className="plan-queue-copy"><strong>{group.name}</strong><span>{t.rank}: {Math.round(group.score)} · {tripsFor(group.id)} {t.allocation}</span><small>{t.need} {group.need} · {t.gap} {group.gap} · {t.debt} {group.debt}</small></div><span className={group.confidence === "review" && !reviewed ? "evidence-status candidate-status" : "evidence-status"}>{group.confidence === "review" && !reviewed ? t.flagged : t.confident}</span></article>)}</div>
        {!reviewed && <label className="plan-review-check"><input type="checkbox" checked={reviewed} onChange={(event) => { setReviewed(event.target.checked); setApproved(false); }} /><span><strong>{t.review}</strong><small>{t.reviewText}</small></span></label>}
        {reviewed && <div className="plan-reviewed-note" role="status">✓ {t.complete}: {groups.find((group) => group.confidence === "review")?.name}</div>}
      </section>
    </div>

    <section className="plan-panel plan-schedule"><div className="plan-panel-title"><div><p className="eyebrow">{t.schedule}</p><h2>{t.scheduleNote}</h2></div><span className="source-tag">SIMULATION</span></div><div className="plan-schedule-table"><div className="plan-schedule-row plan-schedule-head"><span>{t.time}</span><span>{t.stop}</span><span>{t.quantity}</span></div><div className="plan-schedule-row"><span>09:00–11:00</span><span>Sample service point A</span><span>2</span></div><div className="plan-schedule-row"><span>11:00–13:00</span><span>Sample outage area</span><span>2</span></div><div className="plan-schedule-row"><span>13:00–16:00</span><span>Sample service point B</span><span>1</span></div></div></section>

    <section className="plan-approval"><div><p className="eyebrow">{t.reason}</p><label className="sr-only" htmlFor="plan-reason">{t.reason}</label><textarea id="plan-reason" value={reason} maxLength={500} placeholder={t.reasonHint} onChange={(event) => { setReason(event.target.value); setApproved(false); }} /></div><div className="plan-approval-actions"><button className="button button-secondary" onClick={() => { setWeights({ need: 50, gap: 30, debt: 20 }); setReviewed(false); setReason(""); setApproved(false); }}>{t.reset}</button><button className="button button-primary" disabled={!canApprove} onClick={() => setApproved(true)}>{t.approve}</button><small>{!canApprove ? t.blocked : t.approvedNote}</small></div></section>
  </div>;
}
