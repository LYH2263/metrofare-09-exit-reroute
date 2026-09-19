from pydantic import BaseModel


class QuoteRequest(BaseModel):
    start: str
    end: str
    persist: bool = True


class RerouteRequest(BaseModel):
    end: str
