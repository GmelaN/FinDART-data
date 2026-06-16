from typing import Any

from app.config import Settings, get_settings
from app.normalize.tagger import tag_text
from app.search.keyword_search import KeywordSearch, infer_source_types
from app.search.semantic_search import SemanticSearch
from app.store.qdrant_store import EmbeddingService


def normalize_scores(results: list[dict[str, Any]]) -> dict[str, float]:
    if not results:
        return {}
    max_score = max(item["score"] for item in results) or 1.0
    return {item["point_id"]: item["score"] / max_score for item in results}


def intent_boost(query: str, payload: dict[str, Any]) -> float:
    inferred_tags = tag_text(query)
    inferred_source_types = set(infer_source_types(query))
    boost = 0.0

    if payload.get("source_type") in inferred_source_types:
        boost += 0.10
    boost += 0.08 * len(set(payload.get("sector_tags") or []) & set(inferred_tags["sector_tags"]))
    boost += 0.06 * len(set(payload.get("macro_tags") or []) & set(inferred_tags["macro_tags"]))
    boost += 0.06 * len(set(payload.get("risk_tags") or []) & set(inferred_tags["risk_tags"]))
    return min(boost, 0.30)


class HybridSearch:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        embedder = EmbeddingService(self.settings.embedding_model)
        self.semantic = SemanticSearch(self.settings, embedder=embedder)
        self.keyword = KeywordSearch(self.settings)

    def search(
        self,
        query: str,
        limit: int = 10,
        semantic_weight: float = 0.65,
        keyword_weight: float = 0.35,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        candidate_limit = max(limit * 3, 10)
        semantic_results = self.semantic.search(query, limit=candidate_limit, **filters)
        keyword_results = self.keyword.search(query, limit=candidate_limit, **filters)
        semantic_scores = normalize_scores(semantic_results)
        keyword_scores = normalize_scores(keyword_results)

        merged: dict[str, dict[str, Any]] = {}
        for item in semantic_results + keyword_results:
            point_id = item["point_id"]
            if point_id not in merged:
                merged[point_id] = {
                    "point_id": point_id,
                    "payload": item["payload"],
                    "semantic_score": semantic_scores.get(point_id, 0.0),
                    "keyword_score": keyword_scores.get(point_id, 0.0),
                }
            else:
                merged[point_id]["payload"].update(item["payload"])
                merged[point_id]["semantic_score"] = max(
                    merged[point_id]["semantic_score"], semantic_scores.get(point_id, 0.0)
                )
                merged[point_id]["keyword_score"] = max(
                    merged[point_id]["keyword_score"], keyword_scores.get(point_id, 0.0)
                )

        for item in merged.values():
            item["intent_boost"] = intent_boost(query, item["payload"])
            item["score"] = (
                semantic_weight * item["semantic_score"]
                + keyword_weight * item["keyword_score"]
                + item["intent_boost"]
            )

        ranked = sorted(merged.values(), key=lambda row: row["score"], reverse=True)
        deduped: list[dict[str, Any]] = []
        seen_doc_chunks: set[tuple[str, int]] = set()
        for item in ranked:
            payload = item["payload"]
            key = (payload.get("doc_id", item["point_id"]), payload.get("chunk_id", 0))
            if key in seen_doc_chunks:
                continue
            seen_doc_chunks.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped
