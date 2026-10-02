from dataclasses import dataclass

# --- contest (F16) -----------------------------------------------------------------------

# Source: docs/JALLEKHA_FINAL_SOLUTION.md F16 ("Residents or councillors can contest a ranking").
CONTEST_ROLES: tuple[str, ...] = ("resident", "councillor")
# Source: F16 ("For every ward and every booking").
CONTEST_TARGETS: tuple[str, ...] = ("ward", "booking")
# OPEN, owner to confirm: reason codes a contest is filed under (written for this project).
CONTEST_REASON_CODES: tuple[str, ...] = (
    "ranking_wrong",
    "need_data_wrong",
    "service_class_wrong",
    "delivery_not_received",
    "other",
)
# OPEN, owner to confirm: what the officer's reply decided (written for this project). The
# reply text with the reason is required whatever the outcome (F16).
REPLY_OUTCOME_CODES: tuple[str, ...] = (
    "ranking_stands",
    "ranking_changed",
    "data_corrected",
    "referred",
)

# --- explanation text (F16): template key -> language -> wording ------------------------
# Parameters are filled from real values only (no LLM). Wording: written for this project;
# OPEN, owner to confirm: native speakers and P4 (i18n) to review.
TEMPLATES: dict[str, dict[str, str]] = {
    "explain.ward.class": {
        "en": "{ward}: service class {service_class} ({class_basis}).",
        "te": "{ward}: సేవా తరగతి {service_class} ({class_basis}).",
        "hi": "{ward}: सेवा वर्ग {service_class} ({class_basis})।",
        "ur": "{ward}: سروس کی قسم {service_class} ({class_basis})۔",
    },
    "explain.ward.need": {
        "en": (
            "{ward}: need weight {need_weight} (WAD {wad}, CAD {cad}, hardship {hardship}); "
            "{households} households; entitlement {entitlement}. Source: {census_label}."
        ),
        "te": (
            "{ward}: అవసర భారం {need_weight} (WAD {wad}, CAD {cad}, కష్టం {hardship}); "
            "{households} కుటుంబాలు; హక్కు {entitlement}. ఆధారం: {census_label}."
        ),
        "hi": (
            "{ward}: आवश्यकता भार {need_weight} (WAD {wad}, CAD {cad}, कठिनाई {hardship}); "
            "{households} परिवार; हक़ {entitlement}। स्रोत: {census_label}।"
        ),
        "ur": (
            "{ward}: ضرورت کا وزن {need_weight} (WAD {wad}، CAD {cad}، مشکل {hardship})؛ "
            "{households} گھرانے؛ حق {entitlement}۔ ماخذ: {census_label}۔"
        ),
    },
    "explain.ward.no_census": {
        "en": (
            "{ward}: no Census data for this ward ({join_status}); its need cannot be "
            "computed, so no number is shown."
        ),
        "te": (
            "{ward}: ఈ వార్డుకు జనగణన సమాచారం లేదు ({join_status}); అవసరాన్ని లెక్కించలేము, కాబట్టి సంఖ్య చూపబడదు."
        ),
        "hi": (
            "{ward}: इस वार्ड के लिए जनगणना डेटा नहीं है ({join_status}); आवश्यकता की गणना नहीं "
            "हो सकती, इसलिए कोई संख्या नहीं दिखाई जाती।"
        ),
        "ur": (
            "{ward}: اس وارڈ کے لیے مردم شماری کا ڈیٹا نہیں ہے ({join_status})؛ ضرورت کا حساب "
            "نہیں ہو سکتا، اس لیے کوئی عدد نہیں دکھایا جاتا۔"
        ),
    },
    "explain.debt.amount": {
        "en": "Water debt: {debt} litres.",
        "te": "నీటి బాకీ: {debt} లీటర్లు.",
        "hi": "पानी का बकाया: {debt} लीटर।",
        "ur": "پانی کا بقایا: {debt} لیٹر۔",
    },
    "explain.debt.unavailable": {
        "en": "Water debt is not available yet.",
        "te": "నీటి బాకీ సమాచారం ఇంకా అందుబాటులో లేదు.",
        "hi": "पानी के बकाये की जानकारी अभी उपलब्ध नहीं है।",
        "ur": "پانی کے بقایا کی معلومات ابھی دستیاب نہیں ہیں۔",
    },
    "explain.booking.served": {
        "en": (
            "Booking {booking}: served today at place {position} ({reason}); place "
            "{arrival_rank} in arrival order."
        ),
        "te": (
            "బుకింగ్ {booking}: ఈరోజు {position}వ స్థానంలో సరఫరా ({reason}); రాక క్రమంలో "
            "{arrival_rank}వ స్థానం."
        ),
        "hi": (
            "बुकिंग {booking}: आज स्थान {position} पर सेवा ({reason}); आगमन क्रम में स्थान {arrival_rank}।"
        ),
        "ur": (
            "بکنگ {booking}: آج مقام {position} پر فراہمی ({reason})؛ آمد کی ترتیب میں مقام "
            "{arrival_rank}۔"
        ),
    },
    "explain.booking.waiting": {
        "en": "Booking {booking}: waiting at place {place}; today's capacity is {capacity} trips.",
        "te": "బుకింగ్ {booking}: {place}వ స్థానంలో వేచి ఉంది; ఈరోజు సామర్థ్యం {capacity} ట్రిప్పులు.",
        "hi": "बुकिंग {booking}: स्थान {place} पर प्रतीक्षा में; आज की क्षमता {capacity} फेरे।",
        "ur": "بکنگ {booking}: مقام {place} پر انتظار میں؛ آج کی گنجائش {capacity} پھیرے۔",
    },
    "explain.booking.rejected": {
        "en": "Booking {booking}: not accepted because of the booking limit {cap_reason}.",
        "te": "బుకింగ్ {booking}: బుకింగ్ పరిమితి {cap_reason} కారణంగా అంగీకరించలేదు.",
        "hi": "बुकिंग {booking}: बुकिंग सीमा {cap_reason} के कारण स्वीकार नहीं हुई।",
        "ur": "بکنگ {booking}: بکنگ کی حد {cap_reason} کی وجہ سے قبول نہیں ہوئی۔",
    },
    "explain.cf.arrival": {
        "en": (
            "Arriving {amount} minutes earlier would move it from place {before} to place {after}."
        ),
        "te": ("{amount} నిమిషాలు ముందుగా వచ్చి ఉంటే ఇది {before}వ స్థానం నుండి {after}వ స్థానానికి వస్తుంది."),
        "hi": "{amount} मिनट पहले आने पर यह स्थान {before} से स्थान {after} पर आ जाती।",
        "ur": "{amount} منٹ پہلے آنے پر یہ مقام {before} سے مقام {after} پر آ جاتی۔",
    },
    "explain.cf.tier": {
        "en": "As a tier {to} booking it would move from place {before} to place {after}.",
        "te": "శ్రేణి {to} బుకింగ్ అయితే ఇది {before}వ స్థానం నుండి {after}వ స్థానానికి వస్తుంది.",
        "hi": "श्रेणी {to} की बुकिंग होने पर यह स्थान {before} से स्थान {after} पर आ जाती।",
        "ur": "درجہ {to} کی بکنگ ہونے پر یہ مقام {before} سے مقام {after} پر آ جاتی۔",
    },
    "explain.cf.entitlement": {
        "en": (
            "If its group's entitlement were {amount}% higher it would move from place "
            "{before} to place {after}."
        ),
        "te": ("దీని సమూహపు హక్కు {amount}% ఎక్కువైతే ఇది {before}వ స్థానం నుండి {after}వ స్థానానికి వస్తుంది."),
        "hi": "इसके समूह का हक़ {amount}% अधिक होने पर यह स्थान {before} से स्थान {after} पर आ जाती।",
        "ur": (
            "اس کے گروپ کا حق {amount}% زیادہ ہونے پر یہ مقام {before} سے مقام {after} پر آ جاتی۔"
        ),
    },
    "explain.cf.deficit": {
        "en": (
            "With {amount} more carried-over turn credit for its group it would move from "
            "place {before} to place {after}."
        ),
        "te": (
            "దీని సమూహానికి {amount} అదనపు మిగులు వంతు ఉంటే ఇది {before}వ స్థానం నుండి {after}వ స్థానానికి వస్తుంది."
        ),
        "hi": (
            "इसके समूह को {amount} अतिरिक्त बची हुई बारी मिलने पर यह स्थान {before} से स्थान "
            "{after} पर आ जाती।"
        ),
        "ur": (
            "اس کے گروپ کو {amount} اضافی بچی ہوئی باری ملنے پر یہ مقام {before} سے مقام {after} "
            "پر آ جاتی۔"
        ),
    },
    "explain.cf.none": {
        "en": "No single change within the limits moves it up from place {before}.",
        "te": "పరిమితుల్లో ఏ ఒక్క మార్పు కూడా దీనిని {before}వ స్థానం నుండి పైకి తీసుకురాదు.",
        "hi": "सीमाओं के भीतर कोई एक बदलाव इसे स्थान {before} से ऊपर नहीं ले जाता।",
        "ur": "حدود کے اندر کوئی ایک تبدیلی اسے مقام {before} سے اوپر نہیں لے جاتی۔",
    },
    "explain.cf.first": {
        "en": "It is already first in the queue.",
        "te": "ఇది ఇప్పటికే వరుసలో మొదటిది.",
        "hi": "यह पहले से ही कतार में पहले स्थान पर है।",
        "ur": "یہ پہلے ہی قطار میں پہلے مقام پر ہے۔",
    },
    "explain.cf.not_input": {
        "en": (
            "Water debt is not part of today's ordering, so changing it would not move the booking."
        ),
        "te": "నీటి బాకీ ఈరోజు క్రమంలో భాగం కాదు, కాబట్టి దానిని మార్చినా బుకింగ్ స్థానం మారదు.",
        "hi": "पानी का बकाया आज के क्रम का हिस्सा नहीं है, इसलिए इसे बदलने से बुकिंग का स्थान नहीं बदलता।",
        "ur": (
            "پانی کا بقایا آج کی ترتیب کا حصہ نہیں ہے، اس لیے اسے بدلنے سے بکنگ کا مقام نہیں بدلتا۔"
        ),
    },
}


@dataclass(frozen=True)
class ExplainConfig:
    # Source: E2 (ward_evidence.csv: census_year 2011, geo_version GHMC_2016_150).
    census_label: str = "Census 2011 / historical 2016 geography"
    wording_basis: str = (
        "Written for this project; OPEN, owner to confirm: native speakers and P4 to review"
    )
    # Contest and reply text limits. Technical, ASSUMED.
    max_reason_chars: int = 2000
    # Counterfactual search (F16, Wachter et al. 2017): one input changed at a time, in these
    # steps, up to these limits. OPEN, owner to confirm: how far a "what would change it"
    # answer may reach. Arrival = waiting time (minutes earlier); entitlement = the group's
    # A2 entitlement x (1 + amount); deficit = the group's carried-over round-robin credit.
    arrival_step_minutes: int = 15
    arrival_max_minutes: int = 72 * 60
    entitlement_step_ratio: float = 0.05
    entitlement_max_ratio: float = 3.0  # at most 3 x today's entitlement
    deficit_step: float = 0.05
    deficit_max: float = 1.0  # at most one extra full turn
    try_tier_change: bool = True  # one tier closer to 0 (tier is a declared fact)


EXPLAIN_CONFIG = ExplainConfig()
