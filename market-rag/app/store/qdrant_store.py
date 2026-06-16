import hashlib
import uuid
from typing import Iterable

from qdrant_client.http import models as qm
from sentence_transformers import SentenceTransformer

from app.config import Settings, get_settings
from app.models.document import DocumentChunk, MarketDocument
from app.normalize.chunker import chunk_text
from app.normalize.entity_extractor import EntityExtractor
from app.normalize.tagger import tag_text
from app.normalize.text_cleaner import clean_text, is_too_short
from app.qdrant_init import get_rest_qdrant_client


def dedup_hash(doc: MarketDocument) -> str:
    key = doc.source_url or doc.source_id or doc.doc_id
    raw = f"{key}|{doc.title}|{clean_text(doc.text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def point_id_for(doc_hash: str, chunk_id: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_hash}:{chunk_id}"))


class EmbeddingService:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]


class QdrantDocumentStore:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: EmbeddingService | None = None,
        entity_extractor: EntityExtractor | None = None,
    ):
        self.settings = settings or get_settings()
        self.client = get_rest_qdrant_client(self.settings)
        self.embedder = embedder or EmbeddingService(self.settings.embedding_model)
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.collection_name = self.settings.collection_market_docs

    def build_chunks(self, doc: MarketDocument) -> list[DocumentChunk]:
        if is_too_short(doc.text):
            return []

        doc_hash = dedup_hash(doc)
        chunks: list[DocumentChunk] = []
        for idx, text in enumerate(chunk_text(doc.text)):
            combined_text = f"{doc.title}\n{text}"
            tags = tag_text(combined_text)
            entities = self.entity_extractor.extract(combined_text)
            risk_tags = sorted(set(doc.risk_tags) | set(tags["risk_tags"]))
            chunks.append(
                DocumentChunk(
                    point_id=point_id_for(doc_hash, idx),
                    doc_id=doc.doc_id,
                    chunk_id=idx,
                    title=doc.title,
                    text=text,
                    source_name=doc.source_name,
                    source_type=getattr(doc.source_type, "value", str(doc.source_type)),
                    source_url=doc.source_url,
                    published_at=doc.published_at,
                    collected_at=doc.collected_at,
                    country=doc.country,
                    language=doc.language,
                    macro_tags=tags["macro_tags"],
                    sector_tags=tags["sector_tags"],
                    asset_tags=tags["asset_tags"],
                    company_names=entities["company_names"],
                    tickers=entities["tickers"],
                    event_date=doc.event_date,
                    impact_horizon=doc.impact_horizon,
                    importance=doc.importance,
                    sentiment=doc.sentiment,
                    summary_kr=doc.summary_kr,
                    extracted_facts=doc.extracted_facts,
                    risk_tags=risk_tags,
                    hash=doc_hash,
                    embedding_model=self.settings.embedding_model,
                )
            )
        return chunks

    def upsert_documents(self, docs: Iterable[MarketDocument]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for doc in docs:
            chunks.extend(self.build_chunks(doc))
        if not chunks:
            return []

        vectors = self.embedder.encode([chunk.text for chunk in chunks])
        points = [
            qm.PointStruct(
                id=chunk.point_id,
                vector=vector,
                payload=chunk.payload(),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        return chunks

