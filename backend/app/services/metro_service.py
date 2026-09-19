import json

from app.db import connect
from app.engines.route_quote import quote_route
from app.repositories import edges as edges_repo
from app.repositories import fare_rules as rules_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import stations as stations_repo


def _to_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "created_at": row["created_at"],
        "input": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
    }


class MetroService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def stations(self):
        return stations_repo.list_all(self._conn)

    def station(self, code: str):
        return stations_repo.get_by_code(self._conn, code)

    def edges(self):
        return [{"a": a, "b": b} for a, b in edges_repo.list_pairs(self._conn)]

    def fare_rules(self):
        return rules_repo.list_ordered(self._conn)

    def settings(self):
        return settings_repo.get_map(self._conn)

    def quote(self, start: str, end: str, persist: bool):
        edges = edges_repo.list_pairs(self._conn)
        rules = rules_repo.as_calc_rules(self._conn)
        result = quote_route(edges, start, end, rules)
        run_id = None
        if persist and result.get("reachable"):
            run_id = runs_repo.insert(self._conn, "quote", {"start": start, "end": end}, result)
        return {"run_id": run_id, **result}

    def reroute(self, run_id: int, new_end: str):
        """Re-quote a persisted reachable run with a new destination on the current network.

        The original record is never modified; a new quote record referencing it is written.
        Raises LookupError if the run does not exist, ValueError on any rejected change.
        """
        row = runs_repo.get(self._conn, run_id)
        if row is None:
            raise LookupError(f"记录 #{run_id} 不存在")
        payload = json.loads(row["input_json"])
        prev = json.loads(row["result_json"])
        if row["kind"] != "quote" or "start" not in payload:
            raise ValueError("该记录不是询价，不能改终点")
        if not prev.get("reachable"):
            raise ValueError("原询价不可达，不能改终点")
        start = payload["start"]
        end = (new_end or "").strip()
        if not end or stations_repo.get_by_code(self._conn, end) is None:
            raise ValueError(f"未知终点：{new_end}")
        if end == start:
            raise ValueError("新终点不能与原起点相同")
        edges = edges_repo.list_pairs(self._conn)
        rules = rules_repo.as_calc_rules(self._conn)
        result = quote_route(edges, start, end, rules)
        if not result["reachable"]:
            raise ValueError(f"新终点 {end} 按现行线网不可达")
        result["reroute_of"] = row["id"]
        new_id = runs_repo.insert(
            self._conn,
            "quote",
            {"start": start, "end": end, "reroute_of": row["id"]},
            result,
        )
        return {"run_id": new_id, "reroute_of": row["id"], **result}

    def history(self, limit=50):
        return [_to_item(r) for r in runs_repo.list_recent(self._conn, limit)]

    def history_item(self, run_id: int):
        row = runs_repo.get(self._conn, run_id)
        return _to_item(row) if row else None

    def dashboard(self):
        st = stations_repo.list_all(self._conn)
        clean = [s for s in st if "种子" not in s["name"]]
        dirty = [s for s in st if "种子" in s["name"]]
        return {
            "station_count": len(st),
            "edge_count": len(edges_repo.list_pairs(self._conn)),
            "clean_stations": len(clean),
            "dirty_stations": len(dirty),
        }
