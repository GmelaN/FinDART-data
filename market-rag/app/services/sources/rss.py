from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from dateutil.parser import parse as parse_datetime

from app.models.document import MarketDocument, SourceType
from app.normalize.tagger import tag_text
from app.normalize.text_cleaner import clean_text
from app.services.sources.base import SourceFetcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RssFeed:
    source: str
    category: str
    url: str
    source_type: str = SourceType.news.value


DEFAULT_NEWS_FEEDS = [
    RssFeed("매일경제", "경제", "https://www.mk.co.kr/rss/30100041/"),
    RssFeed("매일경제", "기업·경영", "https://www.mk.co.kr/rss/50100032/"),
    RssFeed("매일경제", "증권", "https://www.mk.co.kr/rss/50200011/"),
    RssFeed("한국경제", "경제", "https://www.hankyung.com/feed/economy"),
    RssFeed("한국경제", "증권", "https://www.hankyung.com/feed/finance"),
    RssFeed("한국경제", "IT", "https://www.hankyung.com/feed/it"),
    RssFeed("경향신문", "경제", "https://www.khan.co.kr/rss/rssdata/economy_news.xml"),
    RssFeed("동아일보", "경제", "https://rss.donga.com/economy.xml"),
]


def stable_doc_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def parse_rss_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, AttributeError):
        try:
            parsed = parse_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def child_text(element: ET.Element, names: list[str]) -> str | None:
    for child in list(element):
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in names and child.text:
            return child.text.strip()
    return None


def rss_items(xml_text: str) -> list[ET.Element]:
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    if items:
        return items
    return [entry for entry in root.findall(".//{*}entry")]


def item_link(item: ET.Element) -> str | None:
    link = child_text(item, ["link"])
    if link:
        return link
    for child in list(item):
        if child.tag.rsplit("}", 1)[-1].lower() == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


class RssFetcher(SourceFetcher):
    source_name = "rss"

    def __init__(
        self,
        feeds: list[RssFeed] | None = None,
        *,
        timeout: int = 10,
        session: requests.Session | None = None,
    ):
        self.feeds = feeds or DEFAULT_NEWS_FEEDS
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, *, since: datetime | None = None, limit: int | None = None) -> list[MarketDocument]:
        docs: list[MarketDocument] = []
        seen: set[str] = set()
        for feed in self.feeds:
            try:
                docs.extend(self._fetch_feed(feed, since=since, limit=limit, seen=seen))
            except Exception:
                logger.warning("RSS fetch failed: %s", feed.url, exc_info=True)
        return docs[:limit] if limit else docs

    def _fetch_feed(
        self,
        feed: RssFeed,
        *,
        since: datetime | None,
        limit: int | None,
        seen: set[str],
    ) -> list[MarketDocument]:
        response = self.session.get(
            feed.url,
            timeout=self.timeout,
            headers={"User-Agent": "FinDART-data/0.1 RSS PoC"},
        )
        response.raise_for_status()
        docs = []
        for item in rss_items(response.text):
            doc = self._item_to_doc(feed, item)
            if not doc:
                continue
            if since and doc.published_at and doc.published_at < since:
                continue
            key = doc.source_url or doc.doc_id
            if key in seen:
                continue
            seen.add(key)
            docs.append(doc)
            if limit and len(docs) >= limit:
                break
        return docs

    def _item_to_doc(self, feed: RssFeed, item: ET.Element) -> MarketDocument | None:
        title = clean_text(child_text(item, ["title"]) or "")
        link = item_link(item)
        description = clean_text(
            child_text(item, ["description", "summary", "content", "encoded"]) or ""
        )
        if not title and not description:
            return None

        guid = child_text(item, ["guid", "id"]) or link or title
        published_at = parse_rss_datetime(
            child_text(item, ["pubdate", "published", "updated", "date"])
        )
        text = clean_text(f"{title}\n{description}")
        tags = tag_text(text)
        metadata: dict[str, Any] = {
            "feed_url": feed.url,
            "category": feed.category,
            "macro_tags": tags["macro_tags"],
            "sector_tags": tags["sector_tags"],
            "asset_tags": tags["asset_tags"],
        }
        return MarketDocument(
            doc_id=stable_doc_id(feed.source_type, link or guid),
            title=title or description[:80],
            text=text,
            source_name=feed.source,
            source_type=feed.source_type,
            source_url=link,
            source_id=guid,
            published_at=published_at,
            importance=0.6 if feed.source_type == SourceType.news.value else 0.75,
            summary_kr=description[:240] or None,
            risk_tags=tags["risk_tags"],
            metadata=metadata,
        )
