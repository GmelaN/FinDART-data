from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.models.document import MarketDocument, SourceType
from app.services.sources.base import SourceFetcher
from app.services.sources.rss import stable_doc_id

logger = logging.getLogger(__name__)


DEFAULT_MARKET_SYMBOLS = {
    "KS11": "KOSPI",
    "KQ11": "KOSDAQ",
    "USD/KRW": "USD/KRW",
    "JPY/KRW": "JPY/KRW",
    "CNY/KRW": "CNY/KRW",
}


FX_SYMBOLS = {"USD/KRW", "JPY/KRW", "CNY/KRW"}


class FinanceDataReaderFetcher(SourceFetcher):
    source_name = "finance_data_reader"

    def __init__(self, symbols: dict[str, str] | None = None):
        self.symbols = symbols or DEFAULT_MARKET_SYMBOLS

    def fetch(self, *, since: datetime | None = None, limit: int | None = None) -> list[MarketDocument]:
        try:
            import FinanceDataReader as fdr
        except ImportError:
            logger.warning("FinanceDataReader is not installed; skipping market indicator fetch")
            return []

        end = datetime.now(timezone.utc).date()
        start = (since.date() if since else end - timedelta(days=7))
        docs: list[MarketDocument] = []
        for symbol, name in self.symbols.items():
            try:
                frame = fdr.DataReader(symbol, start, end)
                if frame.empty:
                    continue
                latest = frame.tail(1).iloc[0]
                close = float(latest.get("Close", latest.iloc[-1]))
                change = latest.get("Change")
                change_pct = float(change) * 100 if change is not None else None
                trend = self._trend(change_pct)
                change_text = f", 등락률 {float(change) * 100:.2f}%" if change is not None else ""
                title = f"{name} 최신 시장 지표"
                text = f"{name}({symbol}) 최근 종가는 {close:,.2f}{change_text}입니다."
                metadata = {
                    "symbol": symbol,
                    "value": close,
                    "change": change,
                    "change_pct": change_pct,
                    "trend": trend,
                    "frequency": "daily",
                    "as_of": end.isoformat(),
                }
                if symbol in FX_SYMBOLS:
                    base, quote = symbol.split("/")
                    metadata.update(
                        {
                            "indicator_group": "fx",
                            "indicator_kind": "exchange_rate",
                            "base_currency": base,
                            "quote_currency": quote,
                        }
                    )
                else:
                    metadata.update(
                        {
                            "indicator_group": "market",
                            "indicator_kind": "equity_index",
                        }
                    )
                docs.append(
                    MarketDocument(
                        doc_id=stable_doc_id("market_indicator", f"{symbol}:{end.isoformat()}"),
                        title=title,
                        text=text,
                        source_name="FinanceDataReader",
                        source_type=SourceType.market_summary,
                        source_id=symbol,
                        published_at=datetime.now(timezone.utc),
                        importance=0.65,
                        summary_kr=text,
                        metadata=metadata,
                    )
                )
            except Exception:
                logger.warning("FinanceDataReader fetch failed: %s", symbol, exc_info=True)
        return docs[:limit] if limit else docs

    def _trend(self, change_pct: float | None) -> str:
        if change_pct is None:
            return "unknown"
        if change_pct > 0.05:
            return "up"
        if change_pct < -0.05:
            return "down"
        return "flat"
