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

    postgresql_host: str = Field(default="10.1.0.200", alias="POSTGRESQL_HOST")
    postgresql_port: int = Field(default=5432, alias="POSTGRESQL_PORT")
    postgresql_db: str = Field(default="findart", alias="POSTGRESQL_DB")
    postgresql_user: str = Field(default="findart", alias="POSTGRESQL_USER")
    postgresql_password: str = Field(default="", alias="POSTGRESQL_PASSWORD")

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

    rss_feed_urls: str = Field(default="", alias="RSS_FEED_URLS")
    policy_briefing_urls: str = Field(default="", alias="POLICY_BRIEFING_URLS")
    bok_api_key: str = Field(default="", alias="BOK_API_KEY")
    bok_indicators: str = Field(default="", alias="BOK_INDICATORS")
    opendart_api_key: str = Field(default="", alias="OPENDART_API_KEY")
    opendart_corp_codes: str = Field(default="", alias="OPENDART_CORP_CODES")
    opendart_corp_cls: str = Field(default="Y,K", alias="OPENDART_CORP_CLS")
    watch_issues: str = Field(default="환율,반도체,AI,금리", alias="WATCH_ISSUES")
    pipeline_default_window_hours: int = Field(
        default=6, alias="PIPELINE_DEFAULT_WINDOW_HOURS"
    )

    @property
    def postgresql_dsn(self) -> str:
        return (
            f"host={self.postgresql_host} "
            f"port={self.postgresql_port} "
            f"dbname={self.postgresql_db} "
            f"user={self.postgresql_user} "
            f"password={self.postgresql_password}"
        )

    def csv_values(self, value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def rss_feed_url_list(self) -> list[str]:
        return self.csv_values(self.rss_feed_urls)

    @property
    def policy_briefing_url_list(self) -> list[str]:
        return self.csv_values(self.policy_briefing_urls)

    @property
    def watch_issue_list(self) -> list[str]:
        return self.csv_values(self.watch_issues)

    @property
    def opendart_corp_code_list(self) -> list[str]:
        return self.csv_values(self.opendart_corp_codes)

    @property
    def opendart_corp_cls_list(self) -> list[str]:
        return self.csv_values(self.opendart_corp_cls)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
