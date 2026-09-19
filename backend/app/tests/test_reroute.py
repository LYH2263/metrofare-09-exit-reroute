import pytest

import app.db as db
from app import seed
from app.services.metro_service import MetroService


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    seed.init_db()
    with MetroService() as s:
        yield s


def _count(svc):
    return len(svc.history(limit=1000))


def test_reroute_success_writes_new_record_and_keeps_original(svc):
    before = _count(svc)
    out = svc.reroute(1, "B2")
    assert out["parent_id"] == 1
    assert out["start"] == "A1" and out["end"] == "B2"
    assert out["path"] == ["A1", "A2", "B1", "B2"]
    assert out["hops"] == 3 and out["fare"] == 4.0
    assert _count(svc) == before + 1

    orig = svc.run(1)
    assert orig["end"] == "A3" and orig["hops"] == 2 and orig["fare"] == 3.0
    assert orig["path"] == ["A1", "A2", "A3"]

    new = svc.run(out["run_id"])
    assert new["parent_id"] == 1
    assert new["end"] == "B2"
    assert new["path"] == ["A1", "A2", "B1", "B2"]


def test_reroute_recomputes_hops_not_inherited(svc):
    out = svc.reroute(1, "B2")  # original A1->A3 is 2 hops
    assert out["hops"] == 3
    assert svc.run(1)["hops"] == 2


def test_reroute_unknown_end_rejected(svc):
    before = _count(svc)
    with pytest.raises(ValueError):
        svc.reroute(1, "ZZ")
    assert _count(svc) == before


def test_reroute_same_as_start_rejected(svc):
    before = _count(svc)
    with pytest.raises(ValueError):
        svc.reroute(1, "A1")
    assert _count(svc) == before


def test_reroute_unreachable_end_rejected(svc):
    svc._conn.execute("INSERT INTO stations(code, name) VALUES ('Z9', '孤岛')")
    svc._conn.commit()
    before = _count(svc)
    with pytest.raises(ValueError):
        svc.reroute(1, "Z9")
    assert _count(svc) == before


def test_reroute_missing_record(svc):
    before = _count(svc)
    with pytest.raises(LookupError):
        svc.reroute(999, "B2")
    assert _count(svc) == before


def test_reroute_chain_leaves_three_records_with_direct_predecessors(svc):
    r2 = svc.reroute(1, "B2")
    r3 = svc.reroute(r2["run_id"], "A3")
    items = {i["id"]: i for i in svc.history(limit=1000)}
    assert len(items) == 3
    assert items[r2["run_id"]]["parent_id"] == 1
    assert items[r3["run_id"]]["parent_id"] == r2["run_id"]
    assert items[1]["parent_id"] is None
    # original untouched by the chain
    assert items[1]["end"] == "A3" and items[1]["fare"] == 3.0
