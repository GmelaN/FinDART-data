from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.models.document import DocumentChunk, MarketDocument, SourceType
from app.normalize.tagger import tag_text


def isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def source_type_value(doc: MarketDocument | DocumentChunk) -> str:
    return getattr(doc.source_type, "value", str(doc.source_type))


class TodayPageBuilder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def build(
        self,
        docs: list[MarketDocument],
        *,
        chunks: list[DocumentChunk] | None = None,
        window_start: datetime,
        window_end: datetime,
        market: str = "KR",
    ) -> dict[str, Any]:
        chunks_by_doc = self._first_chunks_by_doc(chunks or [])
        ranked_docs = sorted(docs, key=self._rank_doc, reverse=True)
        generated_at = datetime.now(timezone.utc)

        payload = {
            "page_type": "today",
            "page_date": window_end.date().isoformat(),
            "market": market,
            "generated_at": generated_at.isoformat(),
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "daily_indicators": self._daily_indicators(ranked_docs, chunks_by_doc),
            "market_regimes": self._market_regimes(ranked_docs, chunks_by_doc),
            "headlines": self._headlines(ranked_docs, chunks_by_doc),
            "issues": self._issues(ranked_docs, chunks_by_doc),
            "tracked_issues": self._tracked_issues(ranked_docs, chunks_by_doc),
            "events": self._events(ranked_docs, chunks_by_doc),
        }
        return payload

    def _first_chunks_by_doc(self, chunks: list[DocumentChunk]) -> dict[str, DocumentChunk]:
        first: dict[str, DocumentChunk] = {}
        for chunk in sorted(chunks, key=lambda item: item.chunk_id):
            first.setdefault(chunk.doc_id, chunk)
        return first

    def _rank_doc(self, doc: MarketDocument) -> tuple[float, float]:
        source_boost = {
            SourceType.policy.value: 0.2,
            SourceType.disclosure.value: 0.2,
            SourceType.news.value: 0.1,
            SourceType.market_summary.value: 0.1,
        }.get(source_type_value(doc), 0.0)
        published = doc.published_at.timestamp() if doc.published_at else 0.0
        return (float(doc.importance or 0.0) + source_boost, published)

    def _doc_tags(self, doc: MarketDocument, chunk: DocumentChunk | None) -> dict[str, list[str]]:
        if chunk:
            return {
                "macro_tags": chunk.macro_tags,
                "sector_tags": chunk.sector_tags,
                "asset_tags": chunk.asset_tags,
                "risk_tags": chunk.risk_tags,
            }
        tags = tag_text(f"{doc.title}\n{doc.text}")
        tags["risk_tags"] = sorted(set(tags["risk_tags"]) | set(doc.risk_tags))
        return tags

    def _evidence(
        self,
        doc: MarketDocument,
        chunk: DocumentChunk | None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "doc_id": doc.doc_id,
                "chunk_id": f"{doc.doc_id}:{chunk.chunk_id}" if chunk else None,
                "title": doc.title,
                "source_name": doc.source_name,
                "source_url": doc.source_url,
                "published_at": isoformat(doc.published_at),
            }
        ]

    def _summary(self, doc: MarketDocument) -> str:
        if doc.summary_kr:
            return doc.summary_kr
        text = " ".join(doc.text.split())
        return text[:220]

    def _one_sentence(self, doc: MarketDocument) -> str:
        summary = self._summary(doc).replace("\n", " ").strip()
        if not summary:
            return doc.title
        sentence = summary.split(". ")[0].strip()
        return sentence[:180]

    def _headlines(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> list[dict[str, Any]]:
        headlines = []
        for doc in ranked_docs[:5]:
            chunk = chunks_by_doc.get(doc.doc_id)
            headlines.append(
                {
                    "id": doc.doc_id,
                    "title": doc.title,
                    "sentence": self._one_sentence(doc),
                    "summary": self._summary(doc),
                    "source_type": source_type_value(doc),
                    "source_name": doc.source_name,
                    "news_url": doc.source_url,
                    "published_at": isoformat(doc.published_at),
                    "importance": doc.importance,
                    "sentiment": doc.sentiment,
                    "evidence": self._evidence(doc, chunk),
                }
            )
        return headlines

    def _issues(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> list[dict[str, Any]]:
        issues = []
        seen_keys: set[str] = set()
        for doc in ranked_docs:
            chunk = chunks_by_doc.get(doc.doc_id)
            tags = self._doc_tags(doc, chunk)
            key_parts = tags["risk_tags"] or tags["sector_tags"] or tags["macro_tags"] or [doc.title[:24]]
            key = "|".join(key_parts[:2])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            issues.append(
                {
                    "id": f"issue:{len(issues) + 1}",
                    "subscription_key": self._subscription_key(key),
                    "trackable": True,
                    "title": doc.title,
                    "sentence": self._one_sentence(doc),
                    "summary": self._summary(doc),
                    "issue_type": source_type_value(doc),
                    "news_url": doc.source_url,
                    "importance": doc.importance,
                    "sentiment": doc.sentiment,
                    "macro_tags": tags["macro_tags"],
                    "sector_tags": tags["sector_tags"],
                    "asset_tags": tags["asset_tags"],
                    "risk_tags": tags["risk_tags"],
                    "evidence": self._evidence(doc, chunk),
                }
            )
            if len(issues) >= 3:
                break
        return issues

    def _tracked_issues(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> list[dict[str, Any]]:
        tracked = []
        for keyword in self.settings.watch_issue_list:
            matched = [
                doc
                for doc in ranked_docs
                if keyword.lower() in f"{doc.title}\n{doc.text}".lower()
            ]
            if not matched:
                continue
            doc = matched[0]
            chunk = chunks_by_doc.get(doc.doc_id)
            tracked.append(
                {
                    "id": f"tracked:{self._subscription_key(keyword)}",
                    "keyword": keyword,
                    "subscription_key": self._subscription_key(keyword),
                    "is_subscribed": True,
                    "unsubscribe_action": {
                        "type": "unsubscribe_issue",
                        "subscription_key": self._subscription_key(keyword),
                    },
                    "title": doc.title,
                    "sentence": self._one_sentence(doc),
                    "summary": self._summary(doc),
                    "news_url": doc.source_url,
                    "match_count": len(matched),
                    "evidence": self._evidence(doc, chunk),
                }
            )
        return tracked

    def _events(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> list[dict[str, Any]]:
        events = []
        for doc in ranked_docs:
            source_type = source_type_value(doc)
            event_type = self._event_type(doc)
            if source_type == SourceType.news.value and event_type == "news":
                continue
            chunk = chunks_by_doc.get(doc.doc_id)
            events.append(
                {
                    "id": f"event:{doc.doc_id}",
                    "event_type": event_type,
                    "title": doc.title,
                    "summary": self._summary(doc),
                    "event_date": isoformat(doc.event_date) or isoformat(doc.published_at),
                    "source_type": source_type,
                    "source_name": doc.source_name,
                    "source_url": doc.source_url,
                    "importance": doc.importance,
                    "evidence": self._evidence(doc, chunk),
                }
            )
            if len(events) >= 12:
                break
        return events

    def _event_type(self, doc: MarketDocument) -> str:
        source_type = source_type_value(doc)
        text = f"{doc.title}\n{doc.text}"
        if source_type == SourceType.policy.value:
            return "policy"
        if source_type == SourceType.disclosure.value:
            return "dart_filing"
        if source_type in {SourceType.macro_indicator.value, SourceType.market_summary.value}:
            return "macro_indicator" if source_type == SourceType.macro_indicator.value else "market_move"
        if any(keyword in text for keyword in ["공시", "사업보고서", "분기보고서"]):
            return "dart_filing"
        if any(keyword in text for keyword in ["지표", "금리", "환율", "물가", "GDP"]):
            return "macro_indicator"
        return "news"

    def _subscription_key(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
        normalized = "-".join(part for part in normalized.split("-") if part)
        return normalized[:80] or "issue"

    def _empty_indicator(self, label: str, *, frequency: str = "daily") -> dict[str, Any]:
        return {
            "label": label,
            "value": None,
            "unit": None,
            "change": None,
            "change_pct": None,
            "trend": "unknown",
            "status": "unavailable",
            "frequency": frequency,
            "as_of": None,
            "source_name": None,
            "source_url": None,
            "evidence": [],
        }

    def _indicator_from_doc(
        self,
        label: str,
        doc: MarketDocument,
        chunk: DocumentChunk | None,
        *,
        unit: str | None = None,
    ) -> dict[str, Any]:
        metadata = doc.metadata or {}
        return {
            "label": label,
            "value": metadata.get("value"),
            "unit": unit,
            "change": metadata.get("change"),
            "change_pct": metadata.get("change_pct"),
            "trend": metadata.get("trend") or "unknown",
            "status": "available",
            "frequency": metadata.get("frequency") or "daily",
            "as_of": metadata.get("as_of") or isoformat(doc.published_at),
            "source_name": doc.source_name,
            "source_url": doc.source_url,
            "evidence": self._evidence(doc, chunk),
        }

    def _daily_indicators(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> dict[str, Any]:
        indicators = {
            "interest_rates": {
                "nominal": self._empty_indicator("명목 금리"),
                "real": self._empty_indicator("실질 금리"),
                "direction": "unknown",
                "summary": "일 단위 명목/실질 금리 데이터가 아직 연결되지 않았습니다.",
            },
            "fx": {
                "pairs": {
                    "USD/KRW": self._empty_indicator("USD/KRW"),
                    "JPY/KRW": self._empty_indicator("JPY/KRW"),
                    "CNY/KRW": self._empty_indicator("CNY/KRW"),
                },
                "krw_direction": "unknown",
                "summary": "일 단위 환율 데이터가 아직 충분하지 않습니다.",
            },
            "inflation": {
                "cpi": self._empty_indicator("소비자물가지수", frequency="monthly"),
                "inflation_rate": self._empty_indicator("물가상승률", frequency="monthly"),
                "direction": "unknown",
                "summary": "CPI/물가상승률은 통상 월 단위 지표라 일중에는 최신 발표값 기준으로 표시합니다.",
            },
            "growth": {
                "gdp": self._empty_indicator("GDP", frequency="quarterly"),
                "trade_balance": self._empty_indicator("무역수지"),
                "exports": self._empty_indicator("수출"),
                "imports": self._empty_indicator("수입"),
                "direction": "unknown",
                "summary": "GDP는 분기 단위, 무역수지/수출입은 발표 주기에 따라 최신값 기준으로 표시합니다.",
            },
        }

        fx_trends = []
        for doc in ranked_docs:
            metadata = doc.metadata or {}
            chunk = chunks_by_doc.get(doc.doc_id)
            if metadata.get("indicator_group") == "fx":
                symbol = metadata.get("symbol")
                if symbol in indicators["fx"]["pairs"]:
                    indicators["fx"]["pairs"][symbol] = self._indicator_from_doc(
                        symbol,
                        doc,
                        chunk,
                        unit="KRW",
                    )
                    fx_trends.append(metadata.get("trend"))
            elif metadata.get("indicator_kind") == "nominal_rate":
                indicators["interest_rates"]["nominal"] = self._indicator_from_doc(
                    "명목 금리",
                    doc,
                    chunk,
                    unit="%",
                )
            elif metadata.get("indicator_kind") == "real_rate":
                indicators["interest_rates"]["real"] = self._indicator_from_doc(
                    "실질 금리",
                    doc,
                    chunk,
                    unit="%",
                )
            elif metadata.get("indicator_kind") == "cpi":
                indicators["inflation"]["cpi"] = self._indicator_from_doc("소비자물가지수", doc, chunk)
                if metadata.get("yoy_change_pct") is not None:
                    indicators["inflation"]["inflation_rate"] = self._indicator_from_doc(
                        "물가상승률",
                        doc,
                        chunk,
                        unit="%",
                    )
                    indicators["inflation"]["inflation_rate"]["value"] = metadata.get("yoy_change_pct")
                    indicators["inflation"]["inflation_rate"]["change"] = None
                    indicators["inflation"]["inflation_rate"]["change_pct"] = None
            elif metadata.get("indicator_kind") == "inflation_rate":
                indicators["inflation"]["inflation_rate"] = self._indicator_from_doc(
                    "물가상승률",
                    doc,
                    chunk,
                    unit="%",
                )
            elif metadata.get("indicator_kind") in {"gdp", "trade_balance", "exports", "imports"}:
                indicators["growth"][metadata["indicator_kind"]] = self._indicator_from_doc(
                    indicators["growth"][metadata["indicator_kind"]]["label"],
                    doc,
                    chunk,
                )

        if fx_trends:
            up_count = fx_trends.count("up")
            down_count = fx_trends.count("down")
            if up_count > down_count:
                indicators["fx"]["krw_direction"] = "weakening"
                indicators["fx"]["summary"] = "주요 환율 상승으로 원화 약세 신호가 우세합니다."
            elif down_count > up_count:
                indicators["fx"]["krw_direction"] = "strengthening"
                indicators["fx"]["summary"] = "주요 환율 하락으로 원화 강세 신호가 우세합니다."
            else:
                indicators["fx"]["krw_direction"] = "mixed"
                indicators["fx"]["summary"] = "주요 환율 방향이 엇갈립니다."

        nominal = indicators["interest_rates"]["nominal"]
        real = indicators["interest_rates"]["real"]
        inflation_rate = indicators["inflation"]["inflation_rate"]
        if real["status"] == "unavailable" and nominal["status"] == "available" and inflation_rate["status"] == "available":
            nominal_value = nominal.get("value")
            inflation_value = inflation_rate.get("value")
            if nominal_value is not None and inflation_value is not None:
                indicators["interest_rates"]["real"] = {
                    **real,
                    "label": "실질 금리(명목금리-CPI 상승률)",
                    "value": float(nominal_value) - float(inflation_value),
                    "unit": "%",
                    "trend": "unknown",
                    "status": "available",
                    "frequency": "daily",
                    "as_of": nominal.get("as_of"),
                    "source_name": nominal.get("source_name"),
                    "source_url": nominal.get("source_url"),
                    "evidence": (nominal.get("evidence") or []) + (inflation_rate.get("evidence") or []),
                }
            real = indicators["interest_rates"]["real"]
        rate_trends = [item["trend"] for item in (nominal, real) if item["status"] == "available"]
        if rate_trends:
            indicators["interest_rates"]["direction"] = self._dominant_direction(rate_trends)
            indicators["interest_rates"]["summary"] = "명목/실질 금리 최신값 기준 방향을 표시합니다."

        inflation_trends = [
            indicators["inflation"]["cpi"]["trend"],
            indicators["inflation"]["inflation_rate"]["trend"],
        ]
        indicators["inflation"]["direction"] = self._dominant_direction(
            [trend for trend in inflation_trends if trend != "unknown"]
        )

        growth_trends = [
            indicators["growth"][key]["trend"]
            for key in ("gdp", "trade_balance", "exports", "imports")
            if indicators["growth"][key]["status"] == "available"
        ]
        indicators["growth"]["direction"] = self._dominant_direction(growth_trends)
        return indicators

    def _dominant_direction(self, trends: list[str]) -> str:
        if not trends:
            return "unknown"
        up_count = trends.count("up")
        down_count = trends.count("down")
        if up_count > down_count:
            return "rising"
        if down_count > up_count:
            return "falling"
        return "mixed"

    def _market_regimes(
        self,
        ranked_docs: list[MarketDocument],
        chunks_by_doc: dict[str, DocumentChunk],
    ) -> dict[str, dict[str, Any]]:
        regime_defs = {
            "interest_rate": ["rates"],
            "fx": ["fx"],
            "inflation": ["inflation"],
            "growth": ["growth", "exports", "employment"],
        }
        tag_counts: Counter[str] = Counter()
        evidence_docs: dict[str, MarketDocument] = {}
        evidence_chunks: dict[str, DocumentChunk | None] = {}
        for doc in ranked_docs:
            chunk = chunks_by_doc.get(doc.doc_id)
            tags = self._doc_tags(doc, chunk)
            for macro_tag in tags["macro_tags"]:
                tag_counts[macro_tag] += 1
                evidence_docs.setdefault(macro_tag, doc)
                evidence_chunks.setdefault(macro_tag, chunk)

        regimes: dict[str, dict[str, Any]] = {}
        for regime, macro_tags in regime_defs.items():
            best_tag = max(macro_tags, key=lambda tag: tag_counts[tag]) if macro_tags else ""
            count = tag_counts[best_tag]
            if not count:
                regimes[regime] = {
                    "label": "unknown",
                    "summary": "",
                    "confidence": 0.0,
                    "evidence": [],
                }
                continue
            doc = evidence_docs[best_tag]
            regimes[regime] = {
                "label": best_tag,
                "summary": self._summary(doc),
                "confidence": min(1.0, 0.3 + count * 0.15),
                "evidence": self._evidence(doc, evidence_chunks.get(best_tag)),
            }
        return regimes
