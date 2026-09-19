import pytest

import app.db as db
from app import seed
from app.repositories import runs as runs_repo
from app.services.metro_service import MetroService


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    seed.init_db()
    service = MetroService()
    yield service
    service.close()


def _count() -> int:
    conn = db.connect()
    try:
        return conn.execute("SELECT COUNT(*) c FROM calc_runs").fetchone()["c"]
    finally:
        conn.close()


def _persist_quote(svc, start="A1", end="A3") -> int:
    res = svc.quote(start, end, persist=True)
    assert res["reachable"] and res["run_id"]
    return res["run_id"]


def test_reroute_success_writes_new_record_and_keeps_original(svc):
    rid = _persist_quote(svc)
    before = _count()
    out = svc.reroute(rid, "B2")
    assert _count() == before + 1
    assert out["run_id"] and out["run_id"] != rid
    assert out["reroute_of"] == rid
    assert out["start"] == "A1" and out["end"] == "B2"
    assert out["hops"] == 3 and out["fare"] == 4.0
    assert out["path"] == ["A1", "A2", "B1", "B2"]

    orig = svc.history_item(rid)
    assert orig["result"]["end"] == "A3"
    assert orig["result"]["hops"] == 2
    assert orig["result"]["fare"] == 3.0
    assert orig["result"]["path"] == ["A1", "A2", "A3"]

    new = svc.history_item(out["run_id"])
    assert new["input"]["reroute_of"] == rid
    assert new["result"]["reroute_of"] == rid
    assert new["result"]["end"] == "B2"
    assert new["result"]["path"] == ["A1", "A2", "B1", "B2"]


def test_reroute_unknown_end_rejected(svc):
    rid = _persist_quote(svc)
    before = _count()
    with pytest.raises(ValueError):
        svc.reroute(rid, "Z9")
    assert _count() == before


def test_reroute_same_as_start_rejected(svc):
    rid = _persist_quote(svc)
    before = _count()
    with pytest.raises(ValueError):
        svc.reroute(rid, "A1")
    assert _count() == before


def test_reroute_unreachable_end_rejected(svc):
    conn = db.connect()
    conn.execute("INSERT INTO stations(code, name) VALUES ('C1', '孤岛')")
    conn.commit()
    conn.close()
    rid = _persist_quote(svc)
    before = _count()
    with pytest.raises(ValueError):
        svc.reroute(rid, "C1")
    assert _count() == before


def test_reroute_missing_run(svc):
    before = _count()
    with pytest.raises(LookupError):
        svc.reroute(99999, "B2")
    assert _count() == before


def test_reroute_from_unreachable_record_rejected(svc):
    conn = db.connect()
    bad_id = runs_repo.insert(
        conn,
        "quote",
        {"start": "A1", "end": "ZZ"},
        {"start": "A1", "end": "ZZ", "hops": None, "fare": None, "path": None, "reachable": False},
    )
    conn.close()
    before = _count()
    with pytest.raises(ValueError):
        svc.reroute(bad_id, "B2")
    assert _count() == before


def test_reroute_chain_references_direct_predecessor(svc):
    rid1 = _persist_quote(svc)  # A1 -> A3
    before = _count()
    out2 = svc.reroute(rid1, "B1")  # A1 -> B1
    out3 = svc.reroute(out2["run_id"], "B2")  # A1 -> B2
    assert _count() == before + 2

    rec1 = svc.history_item(rid1)
    rec2 = svc.history_item(out2["run_id"])
    rec3 = svc.history_item(out3["run_id"])
    assert rec1 and rec2 and rec3  # all three openable by id

    assert rec2["input"]["reroute_of"] == rid1
    assert rec3["input"]["reroute_of"] == out2["run_id"]

    # hops recomputed from the new shortest path, not inherited
    assert rec2["result"]["hops"] == 2
    assert rec2["result"]["path"] == ["A1", "A2", "B1"]
    assert rec3["result"]["hops"] == 3
    assert rec3["result"]["path"] == ["A1", "A2", "B1", "B2"]

    # original untouched
    assert rec1["result"]["hops"] == 2
    assert rec1["result"]["fare"] == 3.0
    assert rec1["result"]["path"] == ["A1", "A2", "A3"]


def test_reroute_twice_from_same_original(svc):
    rid1 = _persist_quote(svc)
    before = _count()
    out2 = svc.reroute(rid1, "B1")
    out3 = svc.reroute(rid1, "B2")
    assert _count() == before + 2
    assert svc.history_item(out2["run_id"])["input"]["reroute_of"] == rid1
    assert svc.history_item(out3["run_id"])["input"]["reroute_of"] == rid1
