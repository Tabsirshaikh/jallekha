"""Read-only evidence endpoints (T10): atlas, equity, under-served, coverage, ward report card,
SMS summary and impact. Built from committed P1 / P2 files and A2's `build_ward_needs`; shapes
as in docs/api_shapes.md sections 2-5, 16 and 17."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_roles
from app.config.api import SMS_SUMMARY_TEMPLATE_KEY, SMS_SUMMARY_TEMPLATES, ApiConfig
from app.config.env import REPO_ROOT
from app.routers.common import (
    UNAVAILABLE,
    csv_rows,
    json_file,
    not_found,
    page,
    typed,
    unavailable,
)
from app.services import ledger_store, service_models
from app.services.ledger_store import StoredLedger

router = APIRouter(tags=["evidence"])


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
IMPACT = "data/derived/sandbox/summary.json"

Officer = Depends(require_roles("officer"))
Reader = Depends(require_roles("officer", "resident", "councillor"))
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]


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
        "deliveries": unavailable("no delivery store on main"),
        "debt": unavailable(
            "no debt accounts stored on main (A6 accounts are passed in by the caller)"
        ),
        "schedule": unavailable("no plan store on main"),
    }


@router.get("/wards/{ward_id:path}/report-card", dependencies=[Reader])
def report_card(ward_id: str) -> dict[str, Any]:
    return _report_card(ward_id)


@router.get("/wards/{ward_id:path}/sms-summary", dependencies=[Reader])
def sms_summary(
    ward_id: str,
    ledger: Annotated[StoredLedger, Depends(get_summary_ledger)],
    lang: str = "en",
) -> dict[str, Any]:
    card = _report_card(ward_id)
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
