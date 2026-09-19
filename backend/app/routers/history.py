from fastapi import APIRouter, HTTPException
from app.services.metro_service import MetroService

router = APIRouter(tags=["history"])

@router.get("/history")
def history(limit: int = 50):
    with MetroService() as s:
        return {"items": s.history(limit)}

@router.get("/history/{run_id}")
def history_item(run_id: int):
    with MetroService() as s:
        item = s.run(run_id)
        if item is None:
            raise HTTPException(404)
        return item
