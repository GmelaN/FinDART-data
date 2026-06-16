from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings, get_settings
from app.models.document import DocumentChunk, MarketDocument


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    source_name TEXT,
    source_url TEXT,
    title TEXT,
    summary_kr TEXT,
    raw_text TEXT,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_date DATE,
    country TEXT,
    language TEXT DEFAULT 'ko',
    hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_published_at ON documents(published_at);
CREATE INDEX IF NOT EXISTS idx_documents_event_date ON documents(event_date);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT,
    qdrant_collection TEXT NOT NULL DEFAULT 'market_docs_v1',
    qdrant_point_id TEXT,
    elastic_index TEXT NOT NULL DEFAULT 'market_docs_v1',
    elastic_doc_id TEXT,
    embedding_model TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_qdrant_point_id ON document_chunks(qdrant_point_id);
CREATE INDEX IF NOT EXISTS idx_chunks_elastic_doc_id ON document_chunks(elastic_doc_id);

CREATE TABLE IF NOT EXISTS entities (
    id BIGSERIAL PRIMARY KEY,
    entity_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    aliases TEXT[] NOT NULL DEFAULT '{}',
    ticker TEXT,
    market TEXT,
    country TEXT,
    sector TEXT,
    profile_summary TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_ticker ON entities(ticker);

CREATE TABLE IF NOT EXISTS document_entity_mentions (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_id TEXT REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    mention_text TEXT,
    confidence NUMERIC(5,4),
    role TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(doc_id, chunk_id, entity_id, role)
);

CREATE INDEX IF NOT EXISTS idx_doc_entity_doc_id ON document_entity_mentions(doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_entity_entity_id ON document_entity_mentions(entity_id);

CREATE TABLE IF NOT EXISTS retrieval_runs (
    id BIGSERIAL PRIMARY KEY,
    retrieval_id TEXT NOT NULL UNIQUE,
    query_text TEXT NOT NULL,
    query_plan JSONB NOT NULL,
    qdrant_collection TEXT,
    elastic_index TEXT,
    top_k INT,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_doc_ids TEXT[] NOT NULL DEFAULT '{}',
    result_chunk_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id BIGSERIAL PRIMARY KEY,
    generation_id TEXT NOT NULL UNIQUE,
    target_type TEXT NOT NULL,
    target_id TEXT,
    retrieval_id TEXT REFERENCES retrieval_runs(retrieval_id) ON DELETE SET NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_hash TEXT,
    prompt_tokens INT,
    completion_tokens INT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence_links (
    id BIGSERIAL PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    section_key TEXT,
    doc_id TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    chunk_id TEXT REFERENCES document_chunks(chunk_id) ON DELETE SET NULL,
    qdrant_score NUMERIC(10,6),
    elastic_score NUMERIC(10,6),
    rerank_score NUMERIC(10,6),
    final_rank INT,
    evidence_text TEXT,
    reasoning_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_target ON evidence_links(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_evidence_doc_id ON evidence_links(doc_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chunk_id ON evidence_links(chunk_id);

CREATE TABLE IF NOT EXISTS today_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL UNIQUE,
    snapshot_date DATE NOT NULL,
    snapshot_type TEXT NOT NULL DEFAULT 'daily',
    market TEXT NOT NULL DEFAULT 'KR',
    interest_rate_regime TEXT,
    fx_regime TEXT,
    inflation_regime TEXT,
    growth_regime TEXT,
    headline TEXT,
    abstract TEXT,
    generated_by TEXT,
    prompt_version TEXT,
    model_name TEXT,
    data_start_at TIMESTAMPTZ,
    data_end_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(snapshot_date, market)
);

CREATE TABLE IF NOT EXISTS today_issues (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES today_snapshots(snapshot_id) ON DELETE CASCADE,
    issue_rank INT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    issue_type TEXT,
    importance INT,
    sentiment TEXT,
    impact_horizon TEXT,
    macro_tags TEXT[] NOT NULL DEFAULT '{}',
    sector_tags TEXT[] NOT NULL DEFAULT '{}',
    asset_tags TEXT[] NOT NULL DEFAULT '{}',
    risk_tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS today_sector_impacts (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES today_snapshots(snapshot_id) ON DELETE CASCADE,
    sector_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    reason TEXT,
    confidence NUMERIC(5,4),
    impact_horizon TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS serving_pages (
    id BIGSERIAL PRIMARY KEY,
    page_id TEXT NOT NULL UNIQUE,
    page_type TEXT NOT NULL,
    page_date DATE NOT NULL,
    market TEXT DEFAULT 'KR',
    user_id TEXT NOT NULL DEFAULT '',
    title TEXT,
    status TEXT NOT NULL DEFAULT 'ready',
    payload JSONB NOT NULL,
    source_report_ids TEXT[] NOT NULL DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(page_type, page_date, market, user_id)
);

CREATE INDEX IF NOT EXISTS idx_serving_pages_type_date ON serving_pages(page_type, page_date);
"""


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def chunk_key(chunk: DocumentChunk) -> str:
    return f"{chunk.doc_id}:{chunk.chunk_id}"


def entity_id(entity_type: str, value: str) -> str:
    normalized = value.strip().lower().replace(" ", "-")
    return f"{entity_type}:{normalized}"


class PostgresStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.postgresql_dsn, row_factory=dict_row)

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(SCHEMA_SQL)

    def upsert_documents(self, docs: Iterable[MarketDocument], chunks: Iterable[DocumentChunk]) -> None:
        docs_by_id = {doc.doc_id: doc for doc in docs}
        chunks_list = list(chunks)
        hashes_by_doc: dict[str, str] = {}
        for chunk in chunks_list:
            hashes_by_doc.setdefault(chunk.doc_id, chunk.hash)

        with self.connect() as conn:
            with conn.cursor() as cur:
                for doc in docs_by_id.values():
                    cur.execute(
                        """
                        INSERT INTO documents (
                            doc_id, source_type, source_name, source_url, title, summary_kr,
                            raw_text, published_at, collected_at, event_date, country,
                            language, hash, metadata, updated_at
                        )
                        VALUES (
                            %(doc_id)s, %(source_type)s, %(source_name)s, %(source_url)s,
                            %(title)s, %(summary_kr)s, %(raw_text)s, %(published_at)s,
                            %(collected_at)s, %(event_date)s, %(country)s, %(language)s,
                            %(hash)s, %(metadata)s::jsonb, now()
                        )
                        ON CONFLICT (doc_id) DO UPDATE SET
                            source_type = EXCLUDED.source_type,
                            source_name = EXCLUDED.source_name,
                            source_url = EXCLUDED.source_url,
                            title = EXCLUDED.title,
                            summary_kr = EXCLUDED.summary_kr,
                            raw_text = EXCLUDED.raw_text,
                            published_at = EXCLUDED.published_at,
                            collected_at = EXCLUDED.collected_at,
                            event_date = EXCLUDED.event_date,
                            country = EXCLUDED.country,
                            language = EXCLUDED.language,
                            hash = EXCLUDED.hash,
                            metadata = EXCLUDED.metadata,
                            updated_at = now()
                        """,
                        {
                            "doc_id": doc.doc_id,
                            "source_type": getattr(doc.source_type, "value", str(doc.source_type)),
                            "source_name": doc.source_name,
                            "source_url": doc.source_url,
                            "title": doc.title,
                            "summary_kr": doc.summary_kr,
                            "raw_text": doc.text,
                            "published_at": doc.published_at,
                            "collected_at": doc.collected_at,
                            "event_date": doc.event_date,
                            "country": doc.country,
                            "language": doc.language,
                            "hash": hashes_by_doc.get(doc.doc_id),
                            "metadata": json_dumps(doc.metadata),
                        },
                    )

                for chunk in chunks_list:
                    metadata = chunk.model_dump(
                        exclude={
                            "point_id",
                            "doc_id",
                            "chunk_id",
                            "text",
                            "embedding_model",
                        },
                        mode="json",
                    )
                    cur.execute(
                        """
                        INSERT INTO document_chunks (
                            chunk_id, doc_id, chunk_index, text, token_count,
                            qdrant_collection, qdrant_point_id, elastic_index,
                            elastic_doc_id, embedding_model, metadata
                        )
                        VALUES (
                            %(chunk_id)s, %(doc_id)s, %(chunk_index)s, %(text)s,
                            %(token_count)s, %(qdrant_collection)s, %(qdrant_point_id)s,
                            %(elastic_index)s, %(elastic_doc_id)s, %(embedding_model)s,
                            %(metadata)s::jsonb
                        )
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            text = EXCLUDED.text,
                            token_count = EXCLUDED.token_count,
                            qdrant_collection = EXCLUDED.qdrant_collection,
                            qdrant_point_id = EXCLUDED.qdrant_point_id,
                            elastic_index = EXCLUDED.elastic_index,
                            elastic_doc_id = EXCLUDED.elastic_doc_id,
                            embedding_model = EXCLUDED.embedding_model,
                            metadata = EXCLUDED.metadata
                        """,
                        {
                            "chunk_id": chunk_key(chunk),
                            "doc_id": chunk.doc_id,
                            "chunk_index": chunk.chunk_id,
                            "text": chunk.text,
                            "token_count": len(chunk.text.split()),
                            "qdrant_collection": self.settings.collection_market_docs,
                            "qdrant_point_id": chunk.point_id,
                            "elastic_index": self.settings.collection_market_docs,
                            "elastic_doc_id": chunk.point_id,
                            "embedding_model": chunk.embedding_model,
                            "metadata": json_dumps(metadata),
                        },
                    )
                    self._upsert_chunk_entities(cur, chunk)

    def _upsert_chunk_entities(self, cur: psycopg.Cursor, chunk: DocumentChunk) -> None:
        for company_name in chunk.company_names:
            eid = entity_id("company", company_name)
            cur.execute(
                """
                INSERT INTO entities (entity_id, name, entity_type, country)
                VALUES (%s, %s, 'company', %s)
                ON CONFLICT (entity_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    country = EXCLUDED.country,
                    updated_at = now()
                """,
                (eid, company_name, chunk.country),
            )
            cur.execute(
                """
                INSERT INTO document_entity_mentions (
                    doc_id, chunk_id, entity_id, mention_text, confidence, role
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_id, chunk_id, entity_id, role) DO UPDATE SET
                    mention_text = EXCLUDED.mention_text,
                    confidence = EXCLUDED.confidence
                """,
                (chunk.doc_id, chunk_key(chunk), eid, company_name, 0.8, "mentioned"),
            )

        for ticker in chunk.tickers:
            eid = entity_id("ticker", ticker)
            cur.execute(
                """
                INSERT INTO entities (entity_id, name, entity_type, ticker, country)
                VALUES (%s, %s, 'ticker', %s, %s)
                ON CONFLICT (entity_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    ticker = EXCLUDED.ticker,
                    country = EXCLUDED.country,
                    updated_at = now()
                """,
                (eid, ticker, ticker, chunk.country),
            )
            cur.execute(
                """
                INSERT INTO document_entity_mentions (
                    doc_id, chunk_id, entity_id, mention_text, confidence, role
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_id, chunk_id, entity_id, role) DO UPDATE SET
                    mention_text = EXCLUDED.mention_text,
                    confidence = EXCLUDED.confidence
                """,
                (chunk.doc_id, chunk_key(chunk), eid, ticker, 0.8, "mentioned"),
            )

    def record_retrieval_run(
        self,
        query_text: str,
        results: list[dict[str, Any]],
        *,
        top_k: int,
        filters: dict[str, Any] | None = None,
        query_plan: dict[str, Any] | None = None,
    ) -> str:
        retrieval_id = f"retrieval:{uuid.uuid4()}"
        result_doc_ids = []
        result_chunk_ids = []
        for item in results:
            payload = item.get("payload") or {}
            if payload.get("doc_id"):
                result_doc_ids.append(payload["doc_id"])
                result_chunk_ids.append(f"{payload['doc_id']}:{payload.get('chunk_id', 0)}")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO retrieval_runs (
                    retrieval_id, query_text, query_plan, qdrant_collection,
                    elastic_index, top_k, filters, result_doc_ids, result_chunk_ids
                )
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    retrieval_id,
                    query_text,
                    json_dumps(query_plan or {"strategy": "hybrid"}),
                    self.settings.collection_market_docs,
                    self.settings.collection_market_docs,
                    top_k,
                    json_dumps(filters or {}),
                    result_doc_ids,
                    result_chunk_ids,
                ),
            )
        return retrieval_id

    def upsert_today_from_search_results(
        self,
        results: list[dict[str, Any]],
        *,
        page_date: date | None = None,
        market: str = "KR",
    ) -> str:
        today = page_date or datetime.now(timezone.utc).date()
        snapshot_id = f"today:{market}:{today.isoformat()}"
        page_id = f"page:today:{market}:{today.isoformat()}"
        issues = []
        sector_scores: dict[str, float] = {}
        risk_tags: set[str] = set()
        macro_tags: set[str] = set()

        for rank, item in enumerate(results, start=1):
            payload = item.get("payload") or {}
            issues.append(
                {
                    "rank": rank,
                    "title": payload.get("title"),
                    "summary": payload.get("summary_kr") or payload.get("text"),
                    "source_type": payload.get("source_type"),
                    "sentiment": payload.get("sentiment"),
                    "score": item.get("score"),
                }
            )
            for sector in payload.get("sector_tags") or []:
                sector_scores[sector] = sector_scores.get(sector, 0.0) + float(item.get("score") or 0.0)
            risk_tags.update(payload.get("risk_tags") or [])
            macro_tags.update(payload.get("macro_tags") or [])

        headline = issues[0]["title"] if issues else "생성된 이슈 없음"
        payload = {
            "page_type": "today",
            "page_date": today.isoformat(),
            "market": market,
            "headline": headline,
            "regimes": {
                "interest_rate": "금리상승 부담" if "rate_up" in risk_tags else None,
                "fx": "원화 약세 리스크" if "krw_weakness" in risk_tags else None,
                "inflation": None,
                "growth": "수출 회복" if "export" in macro_tags else None,
            },
            "key_issues": issues,
            "sector_impacts": [
                {"sector": sector, "direction": "mixed", "score": score}
                for sector, score in sorted(sector_scores.items(), key=lambda row: row[1], reverse=True)
            ],
        }

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO today_snapshots (
                        snapshot_id, snapshot_date, market, headline, abstract,
                        generated_by, prompt_version, model_name
                    )
                    VALUES (%s, %s, %s, %s, %s, 'script', 'rule_based_v1', 'none')
                    ON CONFLICT (snapshot_date, market) DO UPDATE SET
                        headline = EXCLUDED.headline,
                        abstract = EXCLUDED.abstract,
                        generated_by = EXCLUDED.generated_by,
                        prompt_version = EXCLUDED.prompt_version,
                        model_name = EXCLUDED.model_name
                    """,
                    (snapshot_id, today, market, headline, "Hybrid search 결과 기반 Today 더미 스냅샷"),
                )
                cur.execute("DELETE FROM today_issues WHERE snapshot_id = %s", (snapshot_id,))
                cur.execute("DELETE FROM today_sector_impacts WHERE snapshot_id = %s", (snapshot_id,))
                for issue in issues:
                    cur.execute(
                        """
                        INSERT INTO today_issues (
                            snapshot_id, issue_rank, title, summary, issue_type,
                            sentiment
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            snapshot_id,
                            issue["rank"],
                            issue["title"] or "",
                            issue["summary"],
                            issue["source_type"],
                            issue["sentiment"],
                        ),
                    )
                for sector, score in sorted(sector_scores.items(), key=lambda row: row[1], reverse=True):
                    cur.execute(
                        """
                        INSERT INTO today_sector_impacts (
                            snapshot_id, sector_name, direction, reason, confidence
                        )
                        VALUES (%s, %s, 'mixed', %s, %s)
                        """,
                        (snapshot_id, sector, "검색 결과에서 반복 언급됨", min(score, 1.0)),
                    )
                cur.execute(
                    """
                    INSERT INTO serving_pages (
                        page_id, page_type, page_date, market, user_id, title, status,
                        payload, source_report_ids, generated_at
                    )
                    VALUES (%s, 'today', %s, %s, '', %s, 'ready', %s::jsonb, %s, now())
                    ON CONFLICT (page_type, page_date, market, user_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        payload = EXCLUDED.payload,
                        source_report_ids = EXCLUDED.source_report_ids,
                        generated_at = now()
                    """,
                    (page_id, today, market, headline, json_dumps(payload), [snapshot_id]),
                )
        return snapshot_id
