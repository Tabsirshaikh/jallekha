from dataclasses import dataclass

from app.config.env import REPO_ROOT

# Where a notice came from. docs/research/P3.md F15: HMWSSB notices are press releases with area
# lists and hours; there is no structured feed, so every notice is entered by an officer.
NOTICE_SOURCES: tuple[str, ...] = (
    "hmwssb_press_release",
    "hmwssb_website",
    "hmwssb_sms",
    "officer_report",
)

# Resident alerts: template key -> language -> wording, with {areas}, {start}, {end}, {hours}.
# Basis: written for this project. OPEN, owner to confirm: native speakers and P4 (i18n) to
# review the wording before real use. Messages carry the key and parameters; no personal data.
ALERT_TEMPLATES: dict[str, dict[str, str]] = {
    "notice.supply_interruption": {
        "en": (
            "HMWSSB notice: water supply will be interrupted in {areas} from {start} to {end} "
            "({hours} hours). Please store water in advance."
        ),
        "te": (
            "HMWSSB సమాచారం: {areas} ప్రాంతాల్లో {start} నుండి {end} వరకు ({hours} గంటలు) "
            "నీటి సరఫరా నిలిచిపోతుంది. దయచేసి ముందుగానే నీటిని నిల్వ చేసుకోండి."
        ),
        "hi": (
            "HMWSSB सूचना: {areas} में {start} से {end} तक ({hours} घंटे) पानी की आपूर्ति बंद "
            "रहेगी। कृपया पहले से पानी जमा कर लें।"
        ),
        "ur": (
            "HMWSSB اطلاع: {areas} میں {start} سے {end} تک ({hours} گھنٹے) پانی کی فراہمی بند "
            "رہے گی۔ براہ کرم پہلے سے پانی جمع کر لیں۔"
        ),
    },
}


@dataclass(frozen=True)
class NoticeConfig:
    # P1's area tables (E1 / A3-FIX / SEC-FIX #39). section_to_ward_2016: 221 sections, 161
    # placed on a 2016 ward (counts change when P1 updates the file); ward geojson: 145 GHMC
    # 2016 wards; ward_evidence: Census 2011 population per ward.
    sections_path: str = str(REPO_ROOT / "data/derived/crosswalk/section_to_ward_2016.csv")
    wards_path: str = str(REPO_ROOT / "data/raw/geography/datameet/ghmc-wards.geojson")
    evidence_path: str = str(REPO_ROOT / "data/derived/evidence/ward_evidence.csv")
    # OPEN, owner to confirm: the lowest confidence accepted without an officer. Proposal 1.0:
    # only exact names (after case and punctuation are normalised) are matched automatically;
    # near misses are flagged with a suggestion, never used. Confidence: difflib ratio.
    area_match_min_confidence: float = 1.0
    # A suggestion is shown to the officer only above this similarity. ASSUMED.
    area_suggestion_min_similarity: float = 0.6
    # OPEN, owner to confirm: people affected = the officer's figure; without it, the Census 2011
    # population of the matched wards (DERIVED, HISTORICAL, whole wards), flagged for review.
    people_affected_rule: str = "officer_else_census_ward_population"
    # Code passed to A5's create_outage as its reason, so no free text reaches the ledger.
    outage_reason_code: str = "hmwssb_supply_notice"
    # Local time shown in alerts (Hyderabad, UTC+05:30). ASSUMED.
    display_utc_offset_minutes: int = 330
    alert_template_key: str = "notice.supply_interruption"
    alert_wording_basis: str = (
        "Written for this project; OPEN, owner to confirm: native speakers and P4 to review"
    )
    # Input limits. Technical, ASSUMED.
    max_area_names: int = 50
    max_raw_text_chars: int = 10_000


NOTICE_CONFIG = NoticeConfig()
