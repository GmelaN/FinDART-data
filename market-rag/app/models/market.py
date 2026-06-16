from datetime import date

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    series_id: str
    date: date
    value: float
    unit: str | None = None
    source_name: str | None = None
    metadata: dict = {}


class MarketEvent(BaseModel):
    event_date: date
    title: str
    source_type: str
    importance: float = 0.0
    tags: list[str] = []

