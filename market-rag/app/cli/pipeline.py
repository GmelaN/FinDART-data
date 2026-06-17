from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.models.document import MarketDocument
from app.services.pages import TodayPageBuilder
from app.services.sources import (
    BokFetcher,
    FinanceDataReaderFetcher,
    OpenDartFetcher,
    PolicyBriefingRssFetcher,
    RssFetcher,
)
from app.services.sources.rss import RssFeed
from app.store.elastic_store import ElasticsearchDocumentStore
from app.store.postgres_store import PostgresStore
from app.store.qdrant_store import QdrantDocumentStore

logger = logging.getLogger(__name__)


def _custom_feeds(urls: list[str], *, source: str, category: str, source_type: str) -> list[RssFeed]:
    return [RssFeed(source, category, url, source_type) for url in urls]


def fetch_documents(window_start: datetime, *, limit_per_source: int | None = None) -> list[MarketDocument]:
    settings = get_settings()
    fetchers = []
    if settings.rss_feed_url_list:
        fetchers.append(
            RssFetcher(
                _custom_feeds(
                    settings.rss_feed_url_list,
                    source="RSS",
                    category="custom",
                    source_type="news",
                )
            )
        )
    else:
        fetchers.append(RssFetcher())

    if settings.policy_briefing_url_list:
        fetchers.append(
            PolicyBriefingRssFetcher(
                _custom_feeds(
                    settings.policy_briefing_url_list,
                    source="대한민국 정책브리핑",
                    category="custom",
                    source_type="policy",
                )
            )
        )
    else:
        fetchers.append(PolicyBriefingRssFetcher())

    fetchers.extend(
        [
            FinanceDataReaderFetcher(),
            BokFetcher(settings),
            OpenDartFetcher(settings),
        ]
    )

    docs: list[MarketDocument] = []
    seen: set[str] = set()
    for fetcher in fetchers:
        try:
            source_limit = None if fetcher.source_name in {"bok", "finance_data_reader"} else limit_per_source
            fetched = fetcher.fetch(since=window_start, limit=source_limit)
        except Exception:
            logger.warning("Source fetch failed: %s", fetcher.source_name, exc_info=True)
            continue
        logger.info("%s fetched %d documents", fetcher.source_name, len(fetched))
        for doc in fetched:
            key = doc.doc_id
            if key in seen:
                continue
            seen.add(key)
            docs.append(doc)
    return docs


def run_today(args: argparse.Namespace) -> int:
    settings = get_settings()
    window_hours = args.window_hours or settings.pipeline_default_window_hours
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    docs = fetch_documents(window_start, limit_per_source=args.limit_per_source)
    logger.info("Fetched %d unique documents", len(docs))

    chunks = []
    if not args.skip_qdrant and docs:
        qdrant_store = QdrantDocumentStore(settings)
        chunks = qdrant_store.upsert_documents(docs)
        logger.info("Qdrant upserted %d chunks", len(chunks))

    if not args.skip_elastic and chunks:
        indexed = ElasticsearchDocumentStore(settings).bulk_index_chunks(chunks)
        logger.info("Elasticsearch indexed %d chunks", indexed)

    if not args.skip_postgres:
        postgres = PostgresStore(settings)
        postgres.init_schema()
        postgres.upsert_documents(docs, chunks)
    else:
        postgres = None

    payload = TodayPageBuilder(settings).build(
        docs,
        chunks=chunks,
        window_start=window_start,
        window_end=window_end,
        market=args.market,
    )

    if postgres:
        page_id = postgres.upsert_today_page_payload(payload)
        logger.info("Serving page saved: %s", page_id)
    else:
        logger.info("PostgreSQL skipped; generated payload with %d headlines", len(payload["headlines"]))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli.pipeline")
    subparsers = parser.add_subparsers(dest="command")

    run_today_parser = subparsers.add_parser("run-today", help="Run the Today page PoC pipeline")
    run_today_parser.add_argument("--window-hours", type=int, default=None)
    run_today_parser.add_argument("--market", default="KR")
    run_today_parser.add_argument("--limit-per-source", type=int, default=None)
    run_today_parser.add_argument("--skip-qdrant", action="store_true")
    run_today_parser.add_argument("--skip-elastic", action="store_true")
    run_today_parser.add_argument("--skip-postgres", action="store_true")
    run_today_parser.set_defaults(func=run_today)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
