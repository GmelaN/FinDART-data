from datetime import datetime
from typing import Any

from app.config import Settings, get_settings
from app.elastic_init import get_elasticsearch_client
from app.normalize.tagger import tag_text


SOURCE_TYPE_HINTS = {
    "policy": ["정책", "정부", "부처", "보도자료", "브리핑"],
    "disclosure": ["공시", "계약", "공급계약", "투자", "dart"],
    "news": ["뉴스", "기사", "최근"],
    "macro_interpretation": ["금리", "환율", "물가", "성장", "근거", "부담"],
    "portfolio_snapshot": ["포트폴리오", "자산", "리스크", "비중"],
}


def infer_source_types(query: str) -> list[str]:
    lower = query.lower()
    return [
        source_type
        for source_type, hints in SOURCE_TYPE_HINTS.items()
        if any(hint.lower() in lower for hint in hints)
    ]


class KeywordSearch:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = get_elasticsearch_client(self.settings)
        self.index_name = self.settings.collection_market_docs

    def search(
        self,
        query: str,
        limit: int = 10,
        source_type: list[str] | None = None,
        sector_tags: list[str] | None = None,
        macro_tags: list[str] | None = None,
        published_from: datetime | str | None = None,
        published_to: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = []
        if source_type:
            filters.append({"terms": {"source_type": source_type}})
        if sector_tags:
            filters.append({"terms": {"sector_tags": sector_tags}})
        if macro_tags:
            filters.append({"terms": {"macro_tags": macro_tags}})
        if published_from or published_to:
            date_range: dict[str, str] = {}
            if published_from:
                date_range["gte"] = (
                    published_from.isoformat()
                    if hasattr(published_from, "isoformat")
                    else str(published_from)
                )
            if published_to:
                date_range["lte"] = (
                    published_to.isoformat()
                    if hasattr(published_to, "isoformat")
                    else str(published_to)
                )
            filters.append({"range": {"published_at": date_range}})

        inferred_tags = tag_text(query)
        inferred_source_types = infer_source_types(query)
        boost_sector_tags = sector_tags or inferred_tags["sector_tags"]
        boost_macro_tags = macro_tags or inferred_tags["macro_tags"]

        should: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^6", "summary_kr^3", "text^1.5", "source_name"],
                    "type": "best_fields",
                    "operator": "or",
                }
            },
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title.ngram^2.5", "summary_kr.ngram^1.6", "text.ngram"],
                    "type": "best_fields",
                    "operator": "or",
                }
            },
            {"match_phrase": {"title": {"query": query, "boost": 4}}},
            {"match_phrase": {"text": {"query": query, "boost": 1.5}}},
        ]
        if boost_sector_tags:
            should.append({"terms": {"sector_tags": boost_sector_tags, "boost": 4}})
        if boost_macro_tags:
            should.append({"terms": {"macro_tags": boost_macro_tags, "boost": 3}})
        if inferred_tags["risk_tags"]:
            should.append({"terms": {"risk_tags": inferred_tags["risk_tags"], "boost": 3}})
        if inferred_source_types:
            should.append({"terms": {"source_type": inferred_source_types, "boost": 2.5}})

        body = {
            "size": limit,
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "should": should,
                            "minimum_should_match": 1,
                            "filter": filters,
                        }
                    },
                    "functions": [
                        {"field_value_factor": {"field": "importance", "factor": 0.15, "missing": 0}},
                    ],
                    "score_mode": "sum",
                    "boost_mode": "sum",
                }
            },
            "highlight": {
                "fields": {
                    "title": {},
                    "text": {"fragment_size": 160, "number_of_fragments": 2},
                    "summary_kr": {},
                }
            },
        }
        response = self.client.search(index=self.index_name, body=body)
        hits = response.get("hits", {}).get("hits", [])
        return [
            {
                "point_id": hit["_id"],
                "score": float(hit.get("_score") or 0.0),
                "payload": hit.get("_source", {}),
                "highlight": hit.get("highlight", {}),
                "source": "keyword",
            }
            for hit in hits
        ]
