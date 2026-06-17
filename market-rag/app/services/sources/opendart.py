from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from app.config import Settings, get_settings
from app.models.document import MarketDocument, SourceType
from app.services.sources.base import SourceFetcher
from app.services.sources.rss import stable_doc_id

logger = logging.getLogger(__name__)

OPENDART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"


class OpenDartFetcher(SourceFetcher):
    source_name = "opendart"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        timeout: int = 10,
        session: requests.Session | None = None,
    ):
        self.settings = settings or get_settings()
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch(self, *, since: datetime | None = None, limit: int | None = None) -> list[MarketDocument]:
        if not self.settings.opendart_api_key:
            logger.warning("OPENDART_API_KEY is not configured; skipping OpenDART fetch")
            return []
        end = datetime.now(timezone.utc)
        start = since or end
        docs: list[MarketDocument] = []
        corp_codes = self.settings.opendart_corp_code_list or [None]
        corp_cls_list = self.settings.opendart_corp_cls_list or [None]
        for corp_code in corp_codes:
            for corp_cls in corp_cls_list:
                try:
                    docs.extend(
                        self._fetch_page(
                            bgn_de=start.strftime("%Y%m%d"),
                            end_de=end.strftime("%Y%m%d"),
                            corp_code=corp_code,
                            corp_cls=corp_cls,
                            page_count=limit or 100,
                        )
                    )
                except Exception:
                    logger.warning("OpenDART list fetch failed", exc_info=True)
                    continue
        docs = self._dedupe(docs)
        return docs[:limit] if limit else docs

    def _fetch_page(
        self,
        *,
        bgn_de: str,
        end_de: str,
        corp_code: str | None,
        corp_cls: str | None,
        page_count: int,
    ) -> list[MarketDocument]:
        params: dict[str, Any] = {
            "crtfc_key": self.settings.opendart_api_key,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "last_reprt_at": "N",
            "sort": "date",
            "sort_mth": "desc",
            "page_no": 1,
            "page_count": min(page_count, 100),
        }
        if corp_code:
            params["corp_code"] = corp_code
        if corp_cls:
            params["corp_cls"] = corp_cls

        response = self.session.get(OPENDART_LIST_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        status = data.get("status")
        if status not in {"000", "013"}:
            logger.warning("OpenDART returned status=%s message=%s", status, data.get("message"))
            return []
        return [self._item_to_doc(item) for item in data.get("list") or []]

    def _item_to_doc(self, item: dict[str, Any]) -> MarketDocument:
        rcept_no = item.get("rcept_no") or ""
        corp_name = item.get("corp_name") or ""
        report_name = item.get("report_nm") or ""
        title = f"{corp_name} {report_name}".strip()
        source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else None
        published_at = self._parse_date(item.get("rcept_dt"))
        text = (
            f"{corp_name}가 {item.get('rcept_dt')}에 {report_name} 공시를 제출했습니다. "
            f"시장구분은 {item.get('corp_cls')}, 종목코드는 {item.get('stock_code') or 'N/A'}입니다."
        )
        return MarketDocument(
            doc_id=stable_doc_id("dart", rcept_no or title),
            title=title,
            text=text,
            source_name="OpenDART",
            source_type=SourceType.disclosure,
            source_url=source_url,
            source_id=rcept_no,
            published_at=published_at,
            event_date=published_at.date() if published_at else None,
            importance=self._importance(report_name),
            summary_kr=text,
            metadata={
                "corp_code": item.get("corp_code"),
                "corp_name": corp_name,
                "stock_code": item.get("stock_code"),
                "corp_cls": item.get("corp_cls"),
                "report_nm": report_name,
                "rcept_no": rcept_no,
                "rcept_dt": item.get("rcept_dt"),
                "flr_nm": item.get("flr_nm"),
                "rm": item.get("rm"),
            },
        )

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)

    def _importance(self, report_name: str) -> float:
        high_keywords = ["사업보고서", "분기보고서", "반기보고서", "주요사항", "유상증자", "합병", "영업정지"]
        if any(keyword in report_name for keyword in high_keywords):
            return 0.85
        return 0.7

    def _dedupe(self, docs: list[MarketDocument]) -> list[MarketDocument]:
        seen: set[str] = set()
        deduped: list[MarketDocument] = []
        for doc in docs:
            if doc.doc_id in seen:
                continue
            seen.add(doc.doc_id)
            deduped.append(doc)
        return deduped
