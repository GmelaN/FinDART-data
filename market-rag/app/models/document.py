from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    macro_indicator = "macro_indicator"
    macro_interpretation = "macro_interpretation"
    policy = "policy"
    disclosure = "disclosure"
    news = "news"
    market_summary = "market_summary"
    calendar = "calendar"
    sector_thesis = "sector_thesis"
    portfolio_snapshot = "portfolio_snapshot"


class MarketDocument(BaseModel):
    doc_id: str
    title: str
    text: str
    source_name: str
    source_type: SourceType | str
    source_url: str | None = None
    source_id: str | None = None
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    country: str = "KR"
    language: str = "ko"
    event_date: date | None = None
    impact_horizon: Literal["today", "weekly", "quarterly", "half_year"] | None = None
    importance: float = 0.0
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    summary_kr: str | None = None
    extracted_facts: list[dict[str, Any]] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    point_id: str
    doc_id: str
    chunk_id: int
    title: str
    text: str
    source_name: str
    source_type: str
    source_url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    country: str = "KR"
    language: str = "ko"
    macro_tags: list[str] = Field(default_factory=list)
    sector_tags: list[str] = Field(default_factory=list)
    asset_tags: list[str] = Field(default_factory=list)
    company_names: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    event_date: date | None = None
    impact_horizon: str | None = None
    importance: float = 0.0
    sentiment: str = "neutral"
    summary_kr: str | None = None
    extracted_facts: list[dict[str, Any]] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    hash: str
    embedding_model: str

    def payload(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"point_id"}, mode="json")
        return data

