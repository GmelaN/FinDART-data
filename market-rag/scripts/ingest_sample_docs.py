from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.document import MarketDocument
from app.store.elastic_store import ElasticsearchDocumentStore
from app.store.qdrant_store import QdrantDocumentStore


def sample_documents() -> list[MarketDocument]:
    now = datetime.now(timezone.utc)
    return [
        MarketDocument(
            doc_id="sample-policy-001",
            title="AI 데이터센터 전력망 확충 정책 발표",
            text="정부는 AI 데이터센터 투자 확대에 대응해 전력망, 변압기, 전선 설비 투자를 앞당기겠다고 밝혔다. 전력기기와 전선 산업은 수혜가 예상되며 반도체 인프라 투자와도 연결된다.",
            source_name="정책브리핑",
            source_type="policy",
            source_url="https://example.com/policy/ai-grid",
            published_at=now,
            impact_horizon="quarterly",
            importance=0.85,
            sentiment="positive",
            summary_kr="AI 데이터센터 확대에 따른 전력망 투자 정책.",
        ),
        MarketDocument(
            doc_id="sample-disclosure-001",
            title="HD현대일렉트릭 대형 변압기 공급계약 공시",
            text="HD현대일렉트릭은 북미 전력망 투자 증가에 따라 대형 변압기 단일판매공급계약을 체결했다고 공시했다. 장기 수주잔고 확대는 전력기기 업종 실적에 긍정적이다.",
            source_name="DART",
            source_type="disclosure",
            source_url="https://example.com/dart/267260-contract",
            published_at=now,
            impact_horizon="half_year",
            importance=0.9,
            sentiment="positive",
        ),
        MarketDocument(
            doc_id="sample-news-001",
            title="반도체 수출 회복세 지속",
            text="최근 반도체 수출은 메모리 가격 반등과 HBM 수요 증가로 회복 흐름을 보였다. 무역수지 개선과 코스피 대형주 실적 기대에도 영향을 주고 있다.",
            source_name="샘플뉴스",
            source_type="news",
            source_url="https://example.com/news/semiconductor-export",
            published_at=now,
            impact_horizon="weekly",
            importance=0.75,
            sentiment="positive",
            summary_kr="반도체 수출 회복과 HBM 수요 증가.",
        ),
        MarketDocument(
            doc_id="sample-macro-001",
            title="장기금리 상승과 성장주 밸류에이션 부담",
            text="미국채 10년물과 국고채 장기금리 상승은 미래 현금흐름 할인율을 높여 성장주 밸류에이션에 부담이 된다. 금리 상승은 채권 매력도를 높이고 고PER 주식의 변동성을 키울 수 있다.",
            source_name="시장해설",
            source_type="macro_interpretation",
            source_url="https://example.com/macro/rates-growth",
            published_at=now,
            impact_horizon="quarterly",
            importance=0.8,
            sentiment="negative",
            risk_tags=["rate_up"],
        ),
        MarketDocument(
            doc_id="sample-portfolio-001",
            title="익명화 포트폴리오 원화 약세 리스크 요약",
            text="포트폴리오가 원화자산과 국내주식에 집중되어 있고 달러 현금 비중이 낮다면 원화 약세와 환율 상승 국면에서 해외 구매력과 방어력이 낮아질 수 있다. 환율, 외국인 수급, 미국 금리를 관찰해야 한다.",
            source_name="portfolio-anonymized",
            source_type="portfolio_snapshot",
            source_url="portfolio://anonymous/sample-001",
            published_at=now,
            impact_horizon="weekly",
            importance=0.7,
            sentiment="mixed",
            risk_tags=["krw_weakness"],
        ),
    ]


if __name__ == "__main__":
    qdrant_store = QdrantDocumentStore()
    elastic_store = ElasticsearchDocumentStore()
    chunks = qdrant_store.upsert_documents(sample_documents())
    count = elastic_store.bulk_index_chunks(chunks)
    print(f"Upserted {len(chunks)} chunks into Qdrant and indexed {count} docs into Elasticsearch.")

