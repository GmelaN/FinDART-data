from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    qdrant_host: str = Field(default="10.1.0.200", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")
    qdrant_prefer_grpc: bool = Field(default=False, alias="QDRANT_PREFER_GRPC")

    elasticsearch_url: str = Field(
        default="http://10.0.0.200:9200", alias="ELASTICSEARCH_URL"
    )

    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1024, alias="EMBEDDING_DIM")

    collection_market_docs: str = Field(
        default="market_docs_v1", alias="COLLECTION_MARKET_DOCS"
    )
    collection_entity_profiles: str = Field(
        default="entity_profiles_v1", alias="COLLECTION_ENTITY_PROFILES"
    )
    collection_portfolio_context: str = Field(
        default="portfolio_context_v1", alias="COLLECTION_PORTFOLIO_CONTEXT"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

