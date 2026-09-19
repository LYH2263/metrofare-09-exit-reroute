import json

from app.db import connect
from app.engines.route_quote import quote_route
from app.repositories import edges as edges_repo
from app.repositories import fare_rules as rules_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import stations as stations_repo


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
        """Re-quote an existing reachable record with a new destination.

        The original record is never modified; on success a new quote record
        referencing the original via parent_id is inserted. Raises LookupError
        if the record is missing, ValueError if the reroute is not allowed.
        """
        row = runs_repo.get(self._conn, run_id)
        if row is None:
            raise LookupError(f"记录 #{run_id} 不存在")
        item = self._row_to_item(row)
        if not item["reachable"]:
            raise ValueError(f"记录 #{run_id} 不可达，不能改终点")
        start = item["start"]
        if new_end == start:
            raise ValueError("新终点不能与原起点相同")
        if stations_repo.get_by_code(self._conn, new_end) is None:
            raise ValueError(f"未知终点编码 {new_end}")
        edges = edges_repo.list_pairs(self._conn)
        rules = rules_repo.as_calc_rules(self._conn)
        result = quote_route(edges, start, new_end, rules)
        if not result["reachable"]:
            raise ValueError(f"新终点 {new_end} 按现行线网不可达")
        new_id = runs_repo.insert(
            self._conn,
            "quote",
            {"start": start, "end": new_end, "parent_id": run_id},
            result,
        )
        return {"run_id": new_id, "parent_id": run_id, **result}

    def history(self, limit=50):
        return [self._row_to_item(r) for r in runs_repo.list_recent(self._conn, limit)]

    def run(self, run_id: int):
        row = runs_repo.get(self._conn, run_id)
        return self._row_to_item(row) if row else None

    @staticmethod
    def _row_to_item(row: dict) -> dict:
        payload = json.loads(row["input_json"])
        result = json.loads(row["result_json"])
        return {
            "id": row["id"],
            "kind": row["kind"],
            "created_at": row["created_at"],
            "start": payload.get("start"),
            "end": payload.get("end"),
            "parent_id": payload.get("parent_id"),
            "hops": result.get("hops"),
            "fare": result.get("fare"),
            "path": result.get("path"),
            "reachable": result.get("reachable"),
        }

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
