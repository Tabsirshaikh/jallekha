"""Read-only evidence endpoints (T10): atlas, facility candidates, equity, under-served, coverage,
ward report card, SMS summary and impact. Built from committed P1 / P2 files and A2's
`build_ward_needs`; shapes as in docs/api_shapes.md sections 2-5, 16 and 17."""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_roles
from app.config.api import SMS_SUMMARY_TEMPLATE_KEY, SMS_SUMMARY_TEMPLATES, ApiConfig
from app.config.env import REPO_ROOT
from app.config.report_cards import REPORT_CARD_CONFIG
from app.routers.common import (
    UNAVAILABLE,
    csv_rows,
    get_now,
    json_file,
    not_found,
    page,
    typed,
)
from app.routers.stores import (
    DebtStore,
    DeliveryStore,
    PlanRecord,
    PlanStore,
    get_debt_store,
    get_delivery_store,
    get_plan_store,
)
from app.services import day_close, ledger_store, plan_builder, report_card, service_models
from app.services.ledger_store import StoredLedger

router = APIRouter(tags=["evidence"])
logger = logging.getLogger(__name__)


def get_summary_ledger() -> StoredLedger:
    return ledger_store.get_ledger()


EVIDENCE = "data/derived/evidence/ward_evidence.csv"
GROWTH = "data/derived/growth/growth.csv"
EQUITY_SUMMARY = "data/derived/equity/summary.json"
EQUITY_SECTIONS = "data/derived/equity/sections.csv"
EQUITY_WARDS = "data/derived/equity/wards.csv"
EQUITY_MONTHLY = "data/derived/equity/monthly.csv"
FIELD_CHECKS = "data/derived/underserved/field_checks.json"
LAYERS = "data/derived/coverage/layers.json"
FACILITY_COUNTS = "data/derived/evidence/ward_facilities.csv"
FACILITY_POINTS = "data/derived/evidence/facility_points.csv"
FACILITY_CATEGORIES = ("hospitals", "clinics", "uphcs", "schools", "care_homes")
# Likeliest tier-0 stops first (F8 tier 0, F10); schools last.
CANDIDATE_ORDER = ("hospitals", "uphcs", "clinics", "care_homes", "schools")
IMPACT = "data/derived/sandbox/summary.json"

Officer = Depends(require_roles("officer"))
Reader = Depends(require_roles("officer", "resident", "councillor"))
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]
Plans = Annotated[PlanStore, Depends(get_plan_store)]
Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
Debts = Annotated[DebtStore, Depends(get_debt_store)]
Now = Annotated[datetime, Depends(get_now)]


def _ward(ward_id: str) -> dict[str, str]:
    row = next((r for r in csv_rows(EVIDENCE) if r["ward_id"] == ward_id), None)
    if row is None:
        raise not_found(f"Ward {ward_id}")
    return row


@lru_cache(maxsize=1)
def _needs(mtime: float) -> dict[str, service_models.WardNeed]:
    evidence = service_models.load_evidence(REPO_ROOT)
    return {n.ward_id: n for n in service_models.build_ward_needs(evidence, [])}


def _need(ward_id: str) -> service_models.WardNeed:
    return _needs((REPO_ROOT / EVIDENCE).stat().st_mtime)[ward_id]


# --- atlas -----------------------------------------------------------------------------------


@router.get("/atlas/wards", dependencies=[Officer])
def atlas_wards(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    return page([typed(r) for r in csv_rows(EVIDENCE)], offset, limit)


@router.get("/atlas/wards/{ward_id:path}", dependencies=[Officer])
def atlas_ward(ward_id: str) -> dict[str, Any]:
    growth = next((r for r in csv_rows(GROWTH) if r["ward_id"] == ward_id), None)
    return {"evidence": typed(_ward(ward_id)), "growth": typed(growth) if growth else None}


# --- facility candidates (D9, F10) ----------------------------------------------------------


def _candidate(row: dict[str, str]) -> dict[str, Any]:
    return {
        "osm_ref": row["osm_ref"],
        "osm_type": row["osm_type"],
        "osm_id": int(row["osm_id"]),
        "osm_url": f"https://www.openstreetmap.org/{row['osm_ref']}",
        "category": row["category"],
        "name": row["name"] or None,  # text even when it looks like a number
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "basis": "REAL",
        "ward_id": row["ward_id"],
        "ward_basis": row["ward_basis"],
    }


@router.get("/facilities/candidates", dependencies=[Officer])
def facility_candidates(
    ward_id: str, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    """OSM hospitals, health centres, clinics, care homes and schools placed in the ward: candidate
    critical (tier-0) stops. Read-only; each becomes a stop only when an officer registers it."""
    counts = next((r for r in csv_rows(FACILITY_COUNTS) if r["ward_id"] == ward_id), None)
    if counts is None:
        raise not_found(f"Ward {ward_id}")
    items = sorted(
        (_candidate(r) for r in csv_rows(FACILITY_POINTS) if r["ward_id"] == ward_id),
        key=lambda i: (CANDIDATE_ORDER.index(i["category"]), i["osm_type"], i["osm_id"]),
    )
    return {
        "ward_id": ward_id,
        "ward_name": counts["ward_name"],
        "status": "CANDIDATE_OFFICER_CONFIRMATION_REQUIRED",
        "counts": {c: int(counts[c]) for c in FACILITY_CATEGORIES},
        "counts_basis": counts["counts_basis"],
        "placement_basis": counts["placement_basis"],
        "note": "OpenStreetMap features placed on the 2016 wards by position; OSM is incomplete, "
        "so a ward may have facilities that are not listed. Register a stop to use one.",
        **page(items, offset, limit),
    }


# --- equity / under-served / coverage --------------------------------------------------------


@router.get("/equity/summary", dependencies=[Officer])
def equity_summary() -> dict[str, Any]:
    return json_file(EQUITY_SUMMARY)


@router.get("/equity/sections", dependencies=[Officer])
def equity_sections(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    return page([typed(r) for r in csv_rows(EQUITY_SECTIONS)], offset, limit)


@router.get("/equity/wards", dependencies=[Officer])
def equity_wards(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    return page([typed(r) for r in csv_rows(EQUITY_WARDS)], offset, limit)


@router.get("/underserved/field-checks", dependencies=[Officer])
def field_checks(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    e5 = json_file(FIELD_CHECKS)
    return {
        "schema_version": e5["schema_version"],
        "summary": e5["summary"],
        "limitations": e5["limitations"],
        "field_check_list": e5["field_check_list"],
        "rows": e5["rows"][offset : offset + limit],
        "rows_total": len(e5["rows"]),
    }


@router.get("/coverage/layers", dependencies=[Officer])
def coverage_layers() -> dict[str, Any]:
    return json_file(LAYERS)


@router.get("/coverage/layers/{layer_id}", dependencies=[Officer])
def coverage_layer(layer_id: str) -> dict[str, Any]:
    layer = next((x for x in json_file(LAYERS)["layers"] if x["layer_id"] == layer_id), None)
    if layer is None:
        raise not_found(f"Layer {layer_id}")
    return json_file(f"data/derived/coverage/{layer['file']}")


# --- ward report card and SMS summary --------------------------------------------------------


def _card_plan(plans: PlanStore) -> tuple[PlanRecord | None, str | None]:
    """The plan a card shows: built from supplied bookings before replay simulations, then the
    latest day, approved before draft, then the latest stored. (record, None) or (None, why)."""
    rows = plans.summaries()
    if not rows:
        return None, None
    best = max(
        rows,
        key=lambda r: (
            r["source"] == plan_builder.SUPPLIED,
            r["day"],
            r["status"] == "APPROVED",
            r["created_at"],
        ),
    )
    try:
        return plans.get(best["plan_id"]), None
    except plan_builder.PlanRebuildError:
        logger.warning("Report card: plan %s could not be rebuilt", best["plan_id"], exc_info=True)
        return None, "the latest plan could not be loaded; an officer has to check it"


def _live_blocks(
    ward_id: str, plans: PlanStore, deliveries: DeliveryStore, debts: DebtStore, now: datetime
) -> dict[str, Any]:
    stops = deliveries.list_stops(ward_id=ward_id)
    start, end = report_card.delivery_window(now)
    visits = deliveries.list_deliveries(
        stop_ids=[s.stop_id for s in stops], started_from=start, started_before=end
    )
    record, problem = _card_plan(plans)
    schedule = (
        report_card.schedule_block(record.plan, record.recipe, record.inputs, record.basis, ward_id)
        if record is not None
        else report_card.schedule_block(None, None, None, None, ward_id)
    )
    if problem:
        schedule = {"value": None, "basis": UNAVAILABLE, "reason": problem}
    return {
        "deliveries": report_card.deliveries_block(stops, visits, now),
        "debt": report_card.debt_block(
            debts.account(day_close.account_id(ward_id)), debts.ward_last_day(ward_id)
        ),
        "schedule": schedule,
    }


def _report_card(ward_id: str) -> dict[str, Any]:
    row, need = _ward(ward_id), _need(ward_id)
    eq = next((r for r in csv_rows(EQUITY_WARDS) if r["ward_id"] == ward_id), {})
    monthly = csv_rows(EQUITY_MONTHLY)
    observed = [r["month"] for r in monthly if r["basis"] == "REAL"]
    eq_typed = typed({"bookings": eq.get("bookings", ""), "per": eq.get("bookings_per_1000", "")})
    return {
        "ward_id": ward_id,
        "ward_name": row["ward_name"],
        "geography_version": row["geo_version"],
        "quality_flags": [f for f in row["quality_flags"].split(";") if f],
        "need": {
            "census_year": int(row["census_year"]),
            "households": need.households,
            "households_basis": row["households_basis"] or UNAVAILABLE,
            "wad": need.wad,
            "wad_basis": row["wad_basis"] or UNAVAILABLE,
            "cad": need.cad,
            "cad_basis": row["cad_basis"] or UNAVAILABLE,
            "hardship": need.hardship,
            "hardship_basis": row["hardship_basis"] or UNAVAILABLE,
            "need_weight": need.need_weight,
            "need_basis": need.need_basis,
            "entitlement": need.entitlement,
            "entitlement_basis": need.need_basis,
            "service_class": need.service_class,
            "class_basis": need.class_basis,
        },
        "bookings": {
            "period": {
                "from": observed[0],
                "to": observed[-1],
                "missing_months": [r["month"] for r in monthly if r["basis"] != "REAL"],
            },
            "bookings": eq_typed["bookings"],
            "bookings_per_1000": eq_typed["per"],
            "basis": eq.get("basis") or UNAVAILABLE,
            "mapping_status": eq.get("mapping_status"),
        },
    }


@router.get("/wards/{ward_id:path}/report-card", dependencies=[Reader])
def ward_report_card(
    ward_id: str, plans: Plans, deliveries: Deliveries, debts: Debts, now: Now
) -> dict[str, Any]:
    return {**_report_card(ward_id), **_live_blocks(ward_id, plans, deliveries, debts, now)}


def _sms_parts(card: dict[str, Any]) -> dict[str, str]:
    """The live blocks as short SMS phrases ("not available" when a block has no value)."""
    visits, debt, schedule = (card[k]["value"] for k in ("deliveries", "debt", "schedule"))
    if visits is None:
        deliveries = "not available"
    else:
        deliveries = f"{visits['started']} started, {visits['by_outcome']['Confirmed']} confirmed"
    owed = "not available" if debt is None else f"{debt['debt_loads']} tanker loads owed"
    if schedule is None:
        planned = "not available"
    else:
        loads = sum(s["loads"] for s in schedule["stops"])
        planned = (
            f"{schedule['day']} {schedule['status']}, {schedule['booked']['served']} booked trips, "
            f"{loads:g} loads to stops"
        )
    return {"deliveries": deliveries, "debt": owed, "schedule": planned}


@router.get("/wards/{ward_id:path}/sms-summary", dependencies=[Reader])
def sms_summary(
    ward_id: str,
    ledger: Annotated[StoredLedger, Depends(get_summary_ledger)],
    plans: Plans,
    deliveries: Deliveries,
    debts: Debts,
    now: Now,
    lang: str = "en",
) -> dict[str, Any]:
    card = ward_report_card(ward_id, plans, deliveries, debts, now)
    heads = ledger.heads()
    head = heads[-1].head_hash[:12] if heads else "not published yet"
    params = {
        "ward_name": card["ward_name"],
        "bookings": card["bookings"]["bookings"]
        if card["bookings"]["bookings"] is not None
        else "no",
        "period_from": card["bookings"]["period"]["from"],
        "period_to": card["bookings"]["period"]["to"],
        "service_class": card["need"]["service_class"],
        "window_days": REPORT_CARD_CONFIG.delivery_window_days,
        **_sms_parts(card),
        "ledger_head": head,
    }
    used = lang if lang in SMS_SUMMARY_TEMPLATES else "en"
    return {
        "ward_id": ward_id,
        "lang_requested": lang,
        "lang_used": used,
        "template_key": SMS_SUMMARY_TEMPLATE_KEY,
        "params": params,
        "text": SMS_SUMMARY_TEMPLATES[used].format(**params),
    }


# --- impact (A8) -------------------------------------------------------------------------------


@router.get("/impact", dependencies=[Officer])
def impact(replay: str = "main_2025", scenario: str = "tight") -> dict[str, Any]:
    a8 = json_file(IMPACT)
    results = a8["results"].get(replay, {}).get(scenario)
    if results is None:
        raise not_found(f"Replay {replay} / scenario {scenario}")
    return {
        "label": a8["label"],
        "seeds": a8["seeds"],
        "replay": replay,
        "scenario": scenario,
        "scenario_basis": results.get("basis"),
        "policies": a8["policies"],
        "results": {p: results["policies"][p] for p in sorted(results["policies"])},
        "jl_worse_than_b1": [
            r for r in a8["jl_worse_than_b1"] if r["replay"] == replay and r["scenario"] == scenario
        ],
        "real_baselines": a8["real_baselines"],
        "duplicate_merge_share": {
            "value": None,
            "basis": UNAVAILABLE,
            "reason": a8["duplicates"]["reason"],
        },
    }
