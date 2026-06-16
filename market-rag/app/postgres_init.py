from app.config import Settings, get_settings
from app.store.postgres_store import PostgresStore


def init_postgres(settings: Settings | None = None) -> None:
    store = PostgresStore(settings or get_settings())
    store.init_schema()
