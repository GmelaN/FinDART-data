from pydantic import BaseModel


class PortfolioRiskSummary(BaseModel):
    snapshot_id: str
    summary_kr: str
    asset_tags: list[str] = []
    sector_tags: list[str] = []
    risk_tags: list[str] = []
    total_value_band: str | None = None

