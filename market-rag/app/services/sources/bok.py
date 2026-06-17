from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from app.config import Settings, get_settings
from app.models.document import MarketDocument, SourceType
from app.services.sources.base import SourceFetcher
from app.services.sources.rss import stable_doc_id

logger = logging.getLogger(__name__)

BOK_BASE_URL = "https://ecos.bok.or.kr/api"


@dataclass(frozen=True)
class BokIndicator:
    label: str
    stat_code: str
    cycle: str
    item_code: str
    indicator_kind: str
    unit: str | None = None
    frequency: str = "daily"


DEFAULT_BOK_INDICATORS = [
    BokIndicator(
        label="한국은행 기준금리",
        stat_code="722Y001",
        cycle="D",
        item_code="0101000",
        indicator_kind="nominal_rate",
        unit="%",
        frequency="daily",
    ),
    BokIndicator(
        label="CD 91일 금리",
        stat_code="817Y002",
        cycle="D",
        item_code="010502000",
        indicator_kind="nominal_rate",
        unit="%",
        frequency="daily",
    ),
    BokIndicator(
        label="소비자물가지수",
        stat_code="901Y009",
        cycle="M",
        item_code="0",
        indicator_kind="cpi",
        unit="index",
        frequency="monthly",
    ),
]


def _trend(value: float | None, previous: float | None = None) -> str:
    if value is None or previous is None:
        return "unknown"
    if value > previous:
        return "up"
    if value < previous:
        return "down"
    return "flat"


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _date_range(cycle: str, since: datetime | None) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    if cycle == "D":
        default_start = now - timedelta(days=45)
        start = min(since, default_start) if since else default_start
        return start.strftime("%Y%m%d"), now.strftime("%Y%m%d")
    if cycle == "M":
        default_start = now - timedelta(days=550)
        start = min(since, default_start) if since else default_start
        return start.strftime("%Y%m"), now.strftime("%Y%m")
    if cycle == "Q":
        default_start = now - timedelta(days=1500)
        start = min(since, default_start) if since else default_start
        return _quarter(start), _quarter(now)
    default_start = now - timedelta(days=3650)
    start = min(since, default_start) if since else default_start
    return start.strftime("%Y"), now.strftime("%Y")


def _quarter(value: datetime) -> str:
    return f"{value.year}Q{((value.month - 1) // 3) + 1}"

class BokFetcher(SourceFetcher):
    source_name = "bok"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        timeout: int = 10,
        session: requests.Session | None = None,
    ):
        self.settings = settings or get_settings()
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, *, since: datetime | None = None, limit: int | None = None) -> list[MarketDocument]:
        if not self.settings.bok_api_key:
            logger.warning("BOK_API_KEY is not configured; skipping BOK fetch")
            return []
        docs: list[MarketDocument] = []
        for indicator in self._indicators():
            try:
                doc = self._fetch_statistic(indicator, since=since)
            except Exception:
                logger.warning("BOK StatisticSearch failed: %s", indicator.label, exc_info=True)
                continue
            if doc:
                docs.append(doc)

        try:
            docs.extend(self._fetch_key_statistics())
        except Exception:
            logger.warning("BOK KeyStatisticList failed", exc_info=True)

        deduped: list[MarketDocument] = []
        seen: set[str] = set()
        for doc in docs:
            if doc.doc_id in seen:
                continue
            seen.add(doc.doc_id)
            deduped.append(doc)
        return deduped[:limit] if limit else deduped

    def _indicators(self) -> list[BokIndicator]:
        if not self.settings.bok_indicators:
            return DEFAULT_BOK_INDICATORS
        data = json.loads(self.settings.bok_indicators)
        return [
            BokIndicator(
                label=item["label"],
                stat_code=item["stat_code"],
                cycle=item["cycle"],
                item_code=item["item_code"],
                indicator_kind=item["indicator_kind"],
                unit=item.get("unit"),
                frequency=item.get("frequency", "daily"),
            )
            for item in data
        ]

    def _fetch_statistic(self, indicator: BokIndicator, *, since: datetime | None) -> MarketDocument | None:
        start, end = _date_range(indicator.cycle, since)
        url = (
            f"{BOK_BASE_URL}/StatisticSearch/{self.settings.bok_api_key}"
            f"/json/kr/1/100/{indicator.stat_code}/{indicator.cycle}/{start}/{end}/{indicator.item_code}"
        )
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        rows = data.get("StatisticSearch", {}).get("row") or []
        if not rows:
            logger.warning("BOK returned no rows for %s: %s", indicator.label, data)
            return None
        rows = sorted(rows, key=lambda row: row.get("TIME", ""))
        latest = rows[-1]
        previous = rows[-2] if len(rows) > 1 else {}
        value = _float_or_none(latest.get("DATA_VALUE"))
        previous_value = _float_or_none(previous.get("DATA_VALUE"))
        trend = _trend(value, previous_value)
        yoy_change_pct = self._yoy_change_pct(rows, latest) if indicator.indicator_kind == "cpi" else None
        as_of = latest.get("TIME")
        title = f"{indicator.label} 최신 지표"
        text = f"{indicator.label} 최신값은 {value}{indicator.unit or ''}입니다. 기준 시점은 {as_of}입니다."
        if yoy_change_pct is not None:
            text = f"{text} 전년동월 대비 상승률은 {yoy_change_pct:.2f}%입니다."
        return MarketDocument(
            doc_id=stable_doc_id("bok", f"{indicator.stat_code}:{indicator.item_code}:{as_of}"),
            title=title,
            text=text,
            source_name="한국은행 ECOS",
            source_type=SourceType.macro_indicator,
            source_url="https://ecos.bok.or.kr/api/",
            source_id=f"{indicator.stat_code}:{indicator.item_code}",
            published_at=datetime.now(timezone.utc),
            importance=0.75,
            summary_kr=text,
            metadata={
                "indicator_group": self._indicator_group(indicator.indicator_kind),
                "indicator_kind": indicator.indicator_kind,
                "label": indicator.label,
                "stat_code": indicator.stat_code,
                "item_code": indicator.item_code,
                "cycle": indicator.cycle,
                "frequency": indicator.frequency,
                "value": value,
                "previous_value": previous_value,
                "change": value - previous_value if value is not None and previous_value is not None else None,
                "change_pct": None,
                "yoy_change_pct": yoy_change_pct,
                "trend": trend,
                "unit": indicator.unit,
                "as_of": as_of,
            },
        )

    def _fetch_key_statistics(self) -> list[MarketDocument]:
        url = f"{BOK_BASE_URL}/KeyStatisticList/{self.settings.bok_api_key}/json/kr/1/100"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        rows = data.get("KeyStatisticList", {}).get("row") or []
        docs: list[MarketDocument] = []
        for row in rows:
            name = row.get("KEYSTAT_NAME") or ""
            mapping = self._key_stat_mapping(name)
            if not mapping:
                continue
            indicator_kind, indicator_group, frequency = mapping
            value = _float_or_none(row.get("DATA_VALUE"))
            unit = row.get("UNIT_NAME")
            as_of = row.get("CYCLE")
            title = f"{name} 최신 지표"
            text = f"{name} 최신값은 {value}{unit or ''}입니다. 기준 시점은 {as_of}입니다."
            docs.append(
                MarketDocument(
                    doc_id=stable_doc_id("bok_key", f"{name}:{as_of}"),
                    title=title,
                    text=text,
                    source_name="한국은행 ECOS",
                    source_type=SourceType.macro_indicator,
                    source_url="https://ecos.bok.or.kr/api/",
                    source_id=name,
                    published_at=datetime.now(timezone.utc),
                    importance=0.7,
                    summary_kr=text,
                    metadata={
                        "indicator_group": indicator_group,
                        "indicator_kind": indicator_kind,
                        "label": name,
                        "frequency": frequency,
                        "value": value,
                        "change": None,
                        "change_pct": None,
                        "trend": "unknown",
                        "unit": unit,
                        "as_of": as_of,
                    },
                )
            )
        return docs

    def _yoy_change_pct(self, rows: list[dict[str, Any]], latest: dict[str, Any]) -> float | None:
        latest_time = latest.get("TIME") or ""
        latest_value = _float_or_none(latest.get("DATA_VALUE"))
        if len(latest_time) < 6 or latest_value is None:
            return None
        target_time = f"{int(latest_time[:4]) - 1}{latest_time[4:6]}"
        previous_year_row = next((row for row in rows if row.get("TIME") == target_time), None)
        previous_year_value = _float_or_none(previous_year_row.get("DATA_VALUE")) if previous_year_row else None
        if not previous_year_value:
            return None
        return (latest_value / previous_year_value - 1.0) * 100

    def _key_stat_mapping(self, name: str) -> tuple[str, str, str] | None:
        if name in {"소비자물가지수", "농산물 및 석유류제외 소비자물가지수"}:
            return "cpi", "inflation", "monthly"
        if "물가상승률" in name:
            return "inflation_rate", "inflation", "monthly"
        if name.startswith("경제성장률") or name.startswith("GDP"):
            return "gdp", "growth", "quarterly"
        if "무역수지" in name or "경상수지" in name:
            return "trade_balance", "growth", "monthly"
        if name in {"재화의 수출 증감률(실질, 계절조정 전기대비)", "수출금액지수"}:
            return "exports", "growth", "monthly"
        if name == "수입금액지수":
            return "imports", "growth", "monthly"
        return None

    def _indicator_group(self, indicator_kind: str) -> str:
        if indicator_kind in {"nominal_rate", "real_rate"}:
            return "interest_rates"
        if indicator_kind in {"cpi", "inflation_rate"}:
            return "inflation"
        if indicator_kind in {"gdp", "trade_balance", "exports", "imports"}:
            return "growth"
        return "macro"
