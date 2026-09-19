from fastapi import APIRouter, HTTPException
from app.schemas.quote import QuoteRequest, RerouteRequest
from app.services.metro_service import MetroService

router = APIRouter(tags=["quote"])

@router.post("/quote")
def post_quote(body: QuoteRequest):
    with MetroService() as s:
        return s.quote(body.start, body.end, body.persist)

@router.post("/quote/{run_id}/reroute")
def post_reroute(run_id: int, body: RerouteRequest):
    with MetroService() as s:
        try:
            return s.reroute(run_id, body.end)
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
