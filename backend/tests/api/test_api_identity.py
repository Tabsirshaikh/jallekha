"""Token-bound identity, the councillor role, /auth/me and contest filing / reading by role.
All tokens and ids here are obviously fake."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.api import ROLES, _tokens

BOUND = {
    "officer": ("t-off", "officer-demo-01"),
    "resident-a": ("t-res-a", "resident-demo-a"),
    "resident-b": ("t-res-b", "resident-demo-b"),
    "councillor": ("t-coun", "councillor-demo-01"),
    "driver": ("t-drv", None),
    "field_worker": ("t-fld", None),
    "resident-anon": ("t-res-anon", None),
}
ROLE_OF = {
    "officer": "officer",
    "resident-a": "resident",
    "resident-b": "resident",
    "councillor": "councillor",
    "driver": "driver",
    "field_worker": "field_worker",
    "resident-anon": "resident",
}
GATEWAY = "t-gateway"
WARD = "relation/7848824"


def _env() -> str:
    pairs = []
    for name, (token, user) in BOUND.items():
        pairs.append(f"{ROLE_OF[name]}:{token}" + (f":{user}" if user else ""))
    return ",".join(pairs)


def h(name: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {BOUND[name][0]}"}


@pytest.fixture
def bound(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The shared `client` with tokens that carry user ids and a councillor token."""
    monkeypatch.setenv("API_TOKENS", _env())
    return client


def _contest(**over: Any) -> dict[str, Any]:
    body = {
        "filed_by": "resident-demo-a",
        "role": "resident",
        "target_type": "ward",
        "target_id": WARD,
        "reason_code": "need_data_wrong",
        "reason_text": "Our lane has no tap connection; the ward figure looks too low.",
    }
    body.update(over)
    return body


def _file(client: TestClient, who: str, **over: Any) -> Any:
    body = {k: v for k, v in _contest(**over).items() if v is not None}
    return client.post("/contests", json=body, headers=h(who))


def _reply() -> dict[str, str]:
    return {
        "officer_id": "officer-demo-01",
        "outcome_code": "ranking_stands",
        "reason_text": "Census households checked against the field visit.",
    }


# --- token parsing -----------------------------------------------------------------------------


def test_councillor_is_a_role() -> None:
    assert "councillor" in ROLES


def test_tokens_parse_with_and_without_a_user_id() -> None:
    config = _tokens("officer:aaa, resident:bbb:resident-demo-a ,councillor:ccc:cllr.1")
    assert config.roles == {"aaa": "officer", "bbb": "resident", "ccc": "councillor"}
    assert config.users == {"bbb": "resident-demo-a", "ccc": "cllr.1"}


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "officer",  # no token
        "officer:",  # empty token
        "boss:abc",  # unknown role
        "officer:abc:",  # empty user id: ignored, not silently unbound
        "resident:abc:9876543210",  # a phone-like id is not an id
        "resident:abc:has space",
        ":abc",
    ],
)
def test_malformed_token_pairs_are_ignored(raw: str) -> None:
    config = _tokens(raw)
    assert config.roles == {} and config.users == {}


def test_a_bad_pair_does_not_hide_a_good_one() -> None:
    config = _tokens("boss:x,officer:good:officer-demo-01")
    assert config.roles == {"good": "officer"} and config.users == {"good": "officer-demo-01"}


# --- /auth/me ----------------------------------------------------------------------------------


def test_me_returns_role_and_user_id_and_never_the_token(bound: TestClient) -> None:
    me = bound.get("/auth/me", headers=h("resident-a"))
    assert me.status_code == 200
    assert me.json() == {"role": "resident", "user_id": "resident-demo-a", "open": False}
    assert BOUND["resident-a"][0] not in me.text
    assert bound.get("/auth/me", headers=h("councillor")).json() == {
        "role": "councillor",
        "user_id": "councillor-demo-01",
        "open": False,
    }
    assert bound.get("/auth/me", headers=h("driver")).json() == {
        "role": "driver",
        "user_id": None,
        "open": False,
    }


@pytest.mark.parametrize("who", list(BOUND))
def test_me_is_open_to_every_user_role(bound: TestClient, who: str) -> None:
    response = bound.get("/auth/me", headers=h(who))
    assert response.status_code == 200 and response.json()["role"] == ROLE_OF[who]


def test_me_needs_a_valid_token(bound: TestClient) -> None:
    assert bound.get("/auth/me").status_code == 401
    assert bound.get("/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    # The gateway credential is not a user.
    assert bound.get("/auth/me", headers={"X-Gateway-Token": GATEWAY}).status_code == 401


def test_me_for_the_dev_token(bound: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_DEV_TOKEN", "dev-fake")
    me = bound.get("/auth/me", headers={"Authorization": "Bearer dev-fake"})
    assert me.status_code == 200 and me.json() == {"role": "dev", "user_id": None, "open": False}


# --- councillor access -------------------------------------------------------------------------


def test_councillor_reads_what_residents_read(bound: TestClient) -> None:
    for path in (
        f"/wards/{WARD}/report-card",
        f"/wards/{WARD}/sms-summary",
        f"/explain/wards/{WARD}",
    ):
        for who in ("resident-a", "councillor", "officer"):
            assert bound.get(path, headers=h(who)).status_code == 200, (path, who)
        assert bound.get(path, headers=h("driver")).status_code == 403, path
        assert bound.get(path).status_code == 401, path


def test_councillor_cannot_use_officer_routes(bound: TestClient) -> None:
    councillor = h("councillor")
    assert bound.get("/atlas/wards", headers=councillor).status_code == 403
    assert bound.get("/ledger/entries", headers=councillor).status_code == 403
    assert bound.post("/notices", json={}, headers=councillor).status_code == 403
    assert bound.get("/plans/plan-test-1", headers=councillor).status_code == 403
    approve = bound.post(
        "/plans/plan-test-1/approve",
        json={"officer_id": "officer-demo-01", "reason": "ok"},
        headers=councillor,
    )
    assert approve.status_code == 403
    assert bound.get("/forecast", headers=councillor).status_code == 403


# --- filing identity ---------------------------------------------------------------------------


def test_filed_by_defaults_to_the_token_user_id(bound: TestClient) -> None:
    filed = _file(bound, "resident-a", filed_by=None)
    assert filed.status_code == 200, filed.text
    detail = bound.get(f"/contests/{filed.json()['contest_id']}", headers=h("officer")).json()
    assert detail["filed_by"] == "resident-demo-a" and detail["role"] == "resident"


def test_a_different_filed_by_is_forbidden(bound: TestClient) -> None:
    response = _file(bound, "resident-a", filed_by="resident-demo-b")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert bound.get("/contests", headers=h("officer")).json()["total"] == 0


def test_the_stored_role_is_the_callers_role(bound: TestClient) -> None:
    by_resident = _file(bound, "resident-a", role="councillor")  # supplied role is ignored
    by_councillor = _file(bound, "councillor", filed_by=None, role="resident")
    assert by_resident.status_code == by_councillor.status_code == 200
    officer = h("officer")
    one = bound.get(f"/contests/{by_resident.json()['contest_id']}", headers=officer).json()
    two = bound.get(f"/contests/{by_councillor.json()['contest_id']}", headers=officer).json()
    assert (one["role"], two["role"]) == ("resident", "councillor")
    assert two["filed_by"] == "councillor-demo-01"


def test_a_token_without_a_user_id_keeps_todays_behaviour(bound: TestClient) -> None:
    filed = _file(bound, "resident-anon", filed_by="resident-demo-z")
    assert filed.status_code == 200, filed.text
    missing = _file(bound, "resident-anon", filed_by=None)
    assert missing.status_code == 422


def test_the_dev_token_files_as_supplied(
    bound: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_DEV_TOKEN", "dev-fake")
    dev = {"Authorization": "Bearer dev-fake"}
    filed = bound.post("/contests", json=_contest(role="councillor", filed_by="x-dev"), headers=dev)
    assert filed.status_code == 200
    detail = bound.get(f"/contests/{filed.json()['contest_id']}", headers=dev).json()
    assert detail["role"] == "councillor" and detail["filed_by"] == "x-dev"


@pytest.mark.parametrize("who", ["driver", "field_worker"])
def test_other_roles_cannot_file(bound: TestClient, who: str) -> None:
    assert _file(bound, who).status_code == 403
    assert bound.post("/contests", json=_contest()).status_code == 401


def test_councillor_files_but_cannot_reply(bound: TestClient) -> None:
    filed = _file(bound, "councillor", filed_by=None)
    assert filed.status_code == 200
    cid = filed.json()["contest_id"]
    for who in ("councillor", "resident-a", "driver", "field_worker"):
        denied = bound.post(f"/contests/{cid}/reply", json=_reply(), headers=h(who))
        assert denied.status_code == 403, who
    assert bound.post(f"/contests/{cid}/reply", json=_reply()).status_code == 401
    assert (
        bound.post(f"/contests/{cid}/reply", json=_reply(), headers=h("officer")).status_code == 200
    )


# --- reading contests --------------------------------------------------------------------------


def test_read_routes_need_a_user_token(bound: TestClient) -> None:
    assert bound.get("/contests").status_code == 401
    assert bound.get("/contests/anything").status_code == 401
    for who in ("driver", "field_worker"):
        assert bound.get("/contests", headers=h(who)).status_code == 403
        assert bound.get("/contests/anything", headers=h(who)).status_code == 403


def test_residents_see_only_their_own_contests(bound: TestClient) -> None:
    mine = _file(bound, "resident-a", filed_by=None).json()["contest_id"]
    theirs = _file(bound, "resident-b", filed_by=None).json()["contest_id"]
    council = _file(bound, "councillor", filed_by=None).json()["contest_id"]

    listed = bound.get("/contests", headers=h("resident-a")).json()
    assert [c["contest_id"] for c in listed["items"]] == [mine] and listed["total"] == 1
    councillors = bound.get("/contests", headers=h("councillor")).json()
    assert [c["contest_id"] for c in councillors["items"]] == [council]

    assert bound.get(f"/contests/{mine}", headers=h("resident-a")).status_code == 200
    other = bound.get(f"/contests/{theirs}", headers=h("resident-a"))
    assert other.status_code == 404 and other.json()["error"]["code"] == "not_found"
    assert bound.get(f"/contests/{mine}", headers=h("resident-b")).status_code == 404
    assert bound.get(f"/contests/{council}", headers=h("resident-a")).status_code == 404
    # `filed_by` is not a way around the scope: it is not a query parameter of this route.
    scoped = bound.get("/contests", params={"filed_by": "resident-demo-b"}, headers=h("resident-a"))
    assert [c["contest_id"] for c in scoped.json()["items"]] == [mine]


def test_a_resident_token_without_a_user_id_cannot_list_or_read(bound: TestClient) -> None:
    filed = _file(bound, "resident-anon", filed_by="resident-demo-z").json()["contest_id"]
    assert bound.get("/contests", headers=h("resident-anon")).status_code == 403
    assert bound.get(f"/contests/{filed}", headers=h("resident-anon")).status_code == 403


def test_officer_lists_all_and_filters(bound: TestClient) -> None:
    a = _file(bound, "resident-a", filed_by=None).json()["contest_id"]
    b = _file(bound, "resident-b", filed_by=None, target_type="booking", target_id="B-1").json()[
        "contest_id"
    ]
    c = _file(bound, "councillor", filed_by=None).json()["contest_id"]
    officer = h("officer")
    assert bound.post(f"/contests/{b}/reply", json=_reply(), headers=officer).status_code == 200

    everything = bound.get("/contests", headers=officer).json()
    assert everything["total"] == 3 and {i["contest_id"] for i in everything["items"]} == {a, b, c}
    assert set(everything) == {"total", "offset", "limit", "items"}

    def ids(**params: Any) -> set[str]:
        response = bound.get("/contests", params=params, headers=officer)
        assert response.status_code == 200, response.text
        return {i["contest_id"] for i in response.json()["items"]}

    assert ids(status="open") == {a, c}
    assert ids(status="replied") == {b}
    assert ids(target_type="booking") == {b}
    assert ids(target_id=WARD) == {a, c}
    assert ids(target_type="ward", target_id=WARD, status="open") == {a, c}
    assert bound.get("/contests", params={"status": "closed"}, headers=officer).status_code == 422
    assert bound.get("/contests", params={"target_type": "x"}, headers=officer).status_code == 422


def test_contest_list_pages_with_offset_limit_total(bound: TestClient) -> None:
    created = [_file(bound, "resident-a", filed_by=None).json()["contest_id"] for _ in range(3)]
    officer = h("officer")
    first = bound.get("/contests", params={"offset": 0, "limit": 2}, headers=officer).json()
    second = bound.get("/contests", params={"offset": 2, "limit": 2}, headers=officer).json()
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    seen = [i["contest_id"] for i in first["items"] + second["items"]]
    assert sorted(seen) == sorted(created)
    assert bound.get("/contests", params={"limit": 0}, headers=officer).status_code == 422
    assert bound.get("/contests", params={"offset": -1}, headers=officer).status_code == 422


def test_contest_detail_has_the_reply_and_no_phone_number(bound: TestClient) -> None:
    text = "Call me on 9876543210 about this ward."
    cid = _file(bound, "resident-a", filed_by=None, reason_text=text).json()["contest_id"]
    officer = h("officer")

    open_one = bound.get(f"/contests/{cid}", headers=officer)
    assert open_one.status_code == 200
    body = open_one.json()
    assert body["reply"] is None and body["status"] == "open" and body["contest_id"] == cid
    assert "9876543210" not in open_one.text and "[number removed]" in body["reason_text"]
    assert {"filed_by", "role", "target_type", "target_id", "reason_code", "created_at"} <= set(
        body
    )

    assert bound.post(f"/contests/{cid}/reply", json=_reply(), headers=officer).status_code == 200
    for who in ("officer", "resident-a"):
        done = bound.get(f"/contests/{cid}", headers=h(who)).json()
        assert done["status"] == "replied"
        assert done["reply"]["outcome_code"] == "ranking_stands"
        assert done["reply"]["reason_text"] == _reply()["reason_text"]
        assert done["reply"]["officer_id"] == "officer-demo-01" and done["reply"]["reply_id"]
    assert bound.get("/contests/no-such-id", headers=officer).status_code == 404


def test_the_dev_token_reads_every_contest(
    bound: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _file(bound, "resident-a", filed_by=None)
    _file(bound, "resident-b", filed_by=None)
    monkeypatch.setenv("API_DEV_TOKEN", "dev-fake")
    listed = bound.get("/contests", headers={"Authorization": "Bearer dev-fake"})
    assert listed.status_code == 200 and listed.json()["total"] == 2
