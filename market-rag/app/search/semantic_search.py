from datetime import datetime
from typing import Any

from qdrant_client.http import models as qm

from app.config import Settings, get_settings
from app.qdrant_init import get_rest_qdrant_client
from app.store.qdrant_store import EmbeddingService


def _match_any(field: str, values: list[str] | None) -> qm.FieldCondition | None:
    if not values:
        return None
    return qm.FieldCondition(key=field, match=qm.MatchAny(any=values))


def _date_range(field: str, gte: str | None, lte: str | None) -> qm.FieldCondition | None:
    if not gte and not lte:
        return None
    return qm.FieldCondition(key=field, range=qm.DatetimeRange(gte=gte, lte=lte))


def build_filter(
    source_type: list[str] | None = None,
    sector_tags: list[str] | None = None,
    macro_tags: list[str] | None = None,
    published_from: datetime | str | None = None,
    published_to: datetime | str | None = None,
) -> qm.Filter | None:
    conditions = [
        _match_any("source_type", source_type),
        _match_any("sector_tags", sector_tags),
        _match_any("macro_tags", macro_tags),
        _date_range(
            "published_at",
            published_from.isoformat() if hasattr(published_from, "isoformat") else published_from,
            published_to.isoformat() if hasattr(published_to, "isoformat") else published_to,
        ),
    ]
    must = [condition for condition in conditions if condition is not None]
    return qm.Filter(must=must) if must else None


class SemanticSearch:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: EmbeddingService | None = None,
    ):
        self.settings = settings or get_settings()
        self.client = get_rest_qdrant_client(self.settings)
        self.embedder = embedder or EmbeddingService(self.settings.embedding_model)
        self.collection_name = self.settings.collection_market_docs

    def search(self, query: str, limit: int = 10, **filters: Any) -> list[dict[str, Any]]:
        vector = self.embedder.encode([query])[0]
        query_filter = build_filter(**filters)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        hits = getattr(response, "points", response)
        return [
            {
                "point_id": str(hit.id),
                "score": float(hit.score),
                "payload": hit.payload or {},
                "source": "semantic",
            }
            for hit in hits
        ]

