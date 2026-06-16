from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import Settings, get_settings


PAYLOAD_INDEXES: dict[str, qm.PayloadSchemaType] = {
    "source_type": qm.PayloadSchemaType.KEYWORD,
    "source_name": qm.PayloadSchemaType.KEYWORD,
    "published_at": qm.PayloadSchemaType.DATETIME,
    "event_date": qm.PayloadSchemaType.DATETIME,
    "country": qm.PayloadSchemaType.KEYWORD,
    "language": qm.PayloadSchemaType.KEYWORD,
    "macro_tags": qm.PayloadSchemaType.KEYWORD,
    "sector_tags": qm.PayloadSchemaType.KEYWORD,
    "asset_tags": qm.PayloadSchemaType.KEYWORD,
    "company_names": qm.PayloadSchemaType.KEYWORD,
    "tickers": qm.PayloadSchemaType.KEYWORD,
    "impact_horizon": qm.PayloadSchemaType.KEYWORD,
    "importance": qm.PayloadSchemaType.FLOAT,
    "sentiment": qm.PayloadSchemaType.KEYWORD,
    "risk_tags": qm.PayloadSchemaType.KEYWORD,
}


def get_qdrant_client(
    settings: Settings | None = None, prefer_grpc: bool | None = None
) -> QdrantClient:
    settings = settings or get_settings()
    use_grpc = settings.qdrant_prefer_grpc if prefer_grpc is None else prefer_grpc
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        grpc_port=settings.qdrant_grpc_port,
        prefer_grpc=use_grpc,
    )


def get_rest_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    return get_qdrant_client(settings, prefer_grpc=False)


def ensure_collection(
    client: QdrantClient, collection_name: str, vector_size: int
) -> None:
    if client.collection_exists(collection_name):
        print(f"Qdrant collection exists: {collection_name}")
    else:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qm.VectorParams(
                size=vector_size,
                distance=qm.Distance.COSINE,
            ),
        )
        print(f"Qdrant collection created: {collection_name}")

    for field_name, schema_type in PAYLOAD_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" not in message and "409" not in message:
                raise


def init_qdrant(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    client = get_qdrant_client(settings)
    collections = (
        settings.collection_market_docs,
        settings.collection_entity_profiles,
        settings.collection_portfolio_context,
    )
    try:
        for collection in collections:
            ensure_collection(client, collection, settings.embedding_dim)
    except Exception as exc:
        if not settings.qdrant_prefer_grpc:
            raise
        print(f"Qdrant gRPC failed, retrying with REST on port {settings.qdrant_port}: {exc}")
        client = get_rest_qdrant_client(settings)
        for collection in collections:
            ensure_collection(client, collection, settings.embedding_dim)


if __name__ == "__main__":
    init_qdrant()

