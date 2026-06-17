from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.models.document import DocumentChunk, MarketDocument, SourceType
from app.services.pages import TodayPageBuilder
from app.services.sources.bok import BokFetcher
from app.services.sources.opendart import OpenDartFetcher
from app.services.sources.rss import RssFeed, RssFetcher
from app.store.postgres_store import PostgresStore


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample</title>
    <item>
      <title>환율 상승에 반도체 수출주 주목</title>
      <link>https://example.com/news/1</link>
      <description>원화 약세와 AI 수요가 국내 반도체 업종에 영향을 주고 있다.</description>
      <pubDate>Wed, 17 Jun 2026 01:00:00 +0000</pubDate>
      <guid>news-1</guid>
    </item>
  </channel>
</rss>
"""


class FakeResponse:
    text = RSS_SAMPLE

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {}


class JsonResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


class TodayPipelineSmokeTest(unittest.TestCase):
    def test_rss_sample_to_market_document(self) -> None:
        session = MagicMock()
        session.get.return_value = FakeResponse()
        fetcher = RssFetcher(
            [RssFeed("테스트뉴스", "경제", "https://example.com/rss.xml")],
            session=session,
        )

        docs = fetcher.fetch()

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].source_type, SourceType.news.value)
        self.assertIn("환율", docs[0].title)
        self.assertIn("krw_weakness", docs[0].risk_tags)

    def test_today_builder_empty_input(self) -> None:
        now = datetime.now(timezone.utc)
        payload = TodayPageBuilder().build(
            [],
            window_start=now - timedelta(hours=6),
            window_end=now,
        )

        self.assertEqual(payload["page_type"], "today")
        self.assertEqual(payload["headlines"], [])
        self.assertEqual(payload["market_regimes"]["fx"]["label"], "unknown")
        self.assertIn("daily_indicators", payload)
        self.assertEqual(
            payload["daily_indicators"]["fx"]["pairs"]["USD/KRW"]["status"],
            "unavailable",
        )

    def test_today_builder_with_documents(self) -> None:
        now = datetime.now(timezone.utc)
        doc = MarketDocument(
            doc_id="news:1",
            title="환율 상승에 반도체 수출주 주목",
            text="원화 약세와 AI 수요가 국내 반도체 업종에 영향을 주고 있다.",
            source_name="테스트뉴스",
            source_type=SourceType.news,
            source_url="https://example.com/news/1",
            published_at=now,
            importance=0.8,
            risk_tags=["krw_weakness"],
        )
        chunk = DocumentChunk(
            point_id="point-1",
            doc_id="news:1",
            chunk_id=0,
            title=doc.title,
            text=doc.text,
            source_name=doc.source_name,
            source_type=SourceType.news.value,
            source_url=doc.source_url,
            published_at=now,
            collected_at=now,
            macro_tags=["fx"],
            sector_tags=["semiconductor"],
            asset_tags=["fx"],
            risk_tags=["krw_weakness"],
            hash="hash-1",
            embedding_model="test",
        )

        payload = TodayPageBuilder().build(
            [doc],
            chunks=[chunk],
            window_start=now - timedelta(hours=6),
            window_end=now,
        )

        self.assertEqual(payload["headlines"][0]["evidence"][0]["doc_id"], "news:1")
        self.assertEqual(payload["headlines"][0]["news_url"], "https://example.com/news/1")
        self.assertIn("sentence", payload["headlines"][0])
        self.assertEqual(payload["market_regimes"]["fx"]["label"], "fx")
        self.assertEqual(payload["issues"][0]["sector_tags"], ["semiconductor"])
        self.assertTrue(payload["issues"][0]["trackable"])
        self.assertIn("subscription_key", payload["issues"][0])

    def test_today_builder_daily_fx_indicators(self) -> None:
        now = datetime.now(timezone.utc)
        doc = MarketDocument(
            doc_id="market_indicator:usdkrw",
            title="USD/KRW 최신 시장 지표",
            text="USD/KRW 최근 종가는 1,380.00, 등락률 0.25%입니다.",
            source_name="FinanceDataReader",
            source_type=SourceType.market_summary,
            published_at=now,
            importance=0.7,
            metadata={
                "symbol": "USD/KRW",
                "indicator_group": "fx",
                "indicator_kind": "exchange_rate",
                "value": 1380.0,
                "change": 0.0025,
                "change_pct": 0.25,
                "trend": "up",
                "frequency": "daily",
                "as_of": now.date().isoformat(),
            },
        )

        payload = TodayPageBuilder().build(
            [doc],
            window_start=now - timedelta(hours=6),
            window_end=now,
        )

        usdkrw = payload["daily_indicators"]["fx"]["pairs"]["USD/KRW"]
        self.assertEqual(usdkrw["status"], "available")
        self.assertEqual(usdkrw["value"], 1380.0)
        self.assertEqual(payload["daily_indicators"]["fx"]["krw_direction"], "weakening")

    def test_serving_pages_payload_save(self) -> None:
        now = datetime.now(timezone.utc)
        payload = TodayPageBuilder().build(
            [
                MarketDocument(
                    doc_id="policy:1",
                    title="금융위 정책 발표",
                    text="금리와 금융시장 관련 정책 발표",
                    source_name="금융위원회",
                    source_type=SourceType.policy,
                    published_at=now,
                    importance=0.9,
                )
            ],
            window_start=now - timedelta(hours=6),
            window_end=now,
        )
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        conn.cursor.return_value = cursor

        with patch.object(PostgresStore, "connect", return_value=conn):
            page_id = PostgresStore().upsert_today_page_payload(payload)

        self.assertTrue(page_id.startswith("page:today:KR:"))
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("INSERT INTO serving_pages" in statement for statement in statements))

    def test_bok_fetcher_maps_statistic_to_macro_document(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            JsonResponse(
                {
                    "StatisticSearch": {
                        "row": [
                            {"TIME": "20260616", "DATA_VALUE": "3.50"},
                            {"TIME": "20260617", "DATA_VALUE": "3.55"},
                        ]
                    }
                }
            ),
            JsonResponse({"KeyStatisticList": {"row": []}}),
        ]
        settings = MagicMock()
        settings.bok_api_key = "test-key"
        settings.bok_indicators = (
            '[{"label":"테스트 금리","stat_code":"TEST","cycle":"D",'
            '"item_code":"001","indicator_kind":"nominal_rate","unit":"%",'
            '"frequency":"daily"}]'
        )

        docs = BokFetcher(settings, session=session).fetch(limit=1)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["indicator_kind"], "nominal_rate")
        self.assertEqual(docs[0].metadata["trend"], "up")

    def test_opendart_fetcher_maps_list_to_disclosure_document(self) -> None:
        session = MagicMock()
        session.get.return_value = JsonResponse(
            {
                "status": "000",
                "message": "정상",
                "list": [
                    {
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "stock_code": "005930",
                        "corp_cls": "Y",
                        "report_nm": "분기보고서",
                        "rcept_no": "20260617000001",
                        "rcept_dt": "20260617",
                        "flr_nm": "삼성전자",
                        "rm": "",
                    }
                ],
            }
        )
        settings = MagicMock()
        settings.opendart_api_key = "test-key"
        settings.opendart_corp_code_list = []
        settings.opendart_corp_cls_list = ["Y"]

        docs = OpenDartFetcher(settings, session=session).fetch(limit=1)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].source_type, SourceType.disclosure)
        self.assertIn("dart.fss.or.kr", docs[0].source_url)


if __name__ == "__main__":
    unittest.main()
