# Market RAG

금융/경제 화면 생성을 위한 RAG 데이터 수집 및 검색 파이프라인입니다. 이번 버전은 Qdrant, Elasticsearch 저장 경로와 샘플 ingest, hybrid search를 실행 가능하게 구성하고, 외부 데이터 수집기는 skeleton으로 둡니다.

## 구성

- Qdrant: `market_docs_v1`, `entity_profiles_v1`, `portfolio_context_v1`
- Elasticsearch: `market_docs_v1`
- PostgreSQL: 원천 문서 메타데이터, chunk 매핑, retrieval/generation 로그, serving page 캐시
- Embedding: `BAAI/bge-m3`, dimension `1024`, cosine distance
- 정형 시계열 DB: `TimeSeriesStore` 인터페이스만 제공

개인 금융 원본과 숫자 시계열 원본은 Qdrant에 저장하지 않습니다. 포트폴리오는 익명화된 리스크 요약만, 금리/환율/CPI/OHLCV 등은 나중에 정형 DB로 저장하는 전제를 둡니다.

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

`.env` 기본값:

```env
QDRANT_HOST=10.1.0.200
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_PREFER_GRPC=false

ELASTICSEARCH_URL=http://10.0.0.200:9200

POSTGRESQL_HOST=10.1.0.200
POSTGRESQL_PORT=5432
POSTGRESQL_DB=findart
POSTGRESQL_USER=findart
POSTGRESQL_PASSWORD=

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

COLLECTION_MARKET_DOCS=market_docs_v1
COLLECTION_ENTITY_PROFILES=entity_profiles_v1
COLLECTION_PORTFOLIO_CONTEXT=portfolio_context_v1
```

## 실행

```bash
python scripts/init_qdrant.py
python scripts/init_elastic.py
python scripts/init_postgres.py
python scripts/ingest_sample_docs.py
python scripts/test_search.py
python scripts/update_today_snapshot.py
```

처음 `ingest_sample_docs.py`를 실행할 때 `sentence-transformers`가 `BAAI/bge-m3` 모델을 다운로드합니다.

## Qdrant

`scripts/init_qdrant.py`는 세 collection을 생성합니다.

- `market_docs_v1`
- `entity_profiles_v1`
- `portfolio_context_v1`

모두 vector size `1024`, cosine distance를 사용합니다. `market_docs_v1` 검색 필터에 필요한 payload index도 함께 생성합니다.

## Elasticsearch

`scripts/init_elastic.py`는 `market_docs_v1` index를 생성합니다. `title`, `text`, `summary_kr`는 full-text search 대상이고, `source_type`, `source_name`, `published_at`, `macro_tags`, `sector_tags`, `asset_tags`, `company_names`, `tickers`, `risk_tags`는 필터링에 사용합니다.


기존 `market_docs_v1` index를 새 analyzer mapping으로 다시 만들 때는 아래 명령을 사용합니다. 재생성 후 샘플 데이터를 다시 ingest해야 합니다.

```bash
python scripts/init_elastic.py --recreate
python scripts/ingest_sample_docs.py
```

## 샘플 ingest

`scripts/ingest_sample_docs.py`는 다음 5개 유형의 문서를 넣습니다.

- policy
- disclosure
- news
- macro_interpretation
- portfolio_snapshot

Qdrant point id와 Elasticsearch document id는 동일한 deterministic UUID입니다. PostgreSQL `document_chunks.qdrant_point_id`, `document_chunks.elastic_doc_id`도 같은 값을 저장합니다. `source_url` 또는 `source_id` 기반 dedup hash를 사용하므로 같은 문서를 다시 넣어도 같은 point/document가 upsert/index 됩니다.

## PostgreSQL

`scripts/init_postgres.py`는 초기 MVP 테이블을 생성합니다.

- `documents`, `document_chunks`
- `entities`, `document_entity_mentions`
- `retrieval_runs`, `generation_runs`, `evidence_links`
- `today_snapshots`, `today_issues`, `today_sector_impacts`
- `serving_pages`

`scripts/update_today_snapshot.py`는 현재 더미 검색 결과를 기반으로 rule-based Today 스냅샷과 `serving_pages(today)` 캐시를 갱신합니다. LLM 연결 전까지 화면/API 계약을 먼저 고정하기 위한 임시 생성기입니다.

## Today PoC 파이프라인

수동 실행 가능한 금융/경제 Today 페이지 PoC 파이프라인을 제공합니다.

```bash
python -m app.cli.pipeline run-today --window-hours 6
```

흐름은 RSS/정책브리핑/시장지표 fetch, `MarketDocument` 정규화, Qdrant upsert, Elasticsearch bulk index, PostgreSQL upsert, Today payload 생성, `serving_pages.payload` JSONB 저장 순서입니다. 외부 서비스 검증 없이 payload만 확인하려면 아래처럼 저장 단계를 건너뛸 수 있습니다.

```bash
python -m app.cli.pipeline run-today --window-hours 6 --skip-qdrant --skip-elastic --skip-postgres
```

추가 설정값:

```env
RSS_FEED_URLS=
POLICY_BRIEFING_URLS=
BOK_API_KEY=
BOK_INDICATORS=
OPENDART_API_KEY=
OPENDART_CORP_CODES=
OPENDART_CORP_CLS=Y,K
WATCH_ISSUES=환율,반도체,AI,금리
PIPELINE_DEFAULT_WINDOW_HOURS=6
```

`RSS_FEED_URLS`, `POLICY_BRIEFING_URLS`가 비어 있으면 기본 피드를 사용합니다. 뉴스 기본 피드는 매일경제, 한국경제, 경향신문, 동아일보의 경제/증권/IT RSS입니다. 정책브리핑 기본 피드는 대한민국 정책브리핑 RSS 서비스의 정책뉴스, 보도자료, 이슈인사이트, 재정경제부, 산업통상부, 국토교통부, 중소벤처기업부, 금융위원회 RSS입니다.

`BOK_API_KEY`가 있으면 한국은행 ECOS API를 호출합니다. 기본값은 `StatisticSearch`로 한국은행 기준금리, CD 91일 금리, 경제성장률을 조회하고, `KeyStatisticList`로 CPI/GDP/무역 관련 100대 지표를 보조 매핑합니다. `BOK_INDICATORS`에는 JSON 배열로 추가 지표를 지정할 수 있습니다.

`OPENDART_API_KEY`가 있으면 OpenDART 공시검색 API를 호출합니다. `OPENDART_CORP_CODES`가 비어 있으면 유가/코스닥 전체 공시를 조회하고, 값이 있으면 지정한 고유번호만 조회합니다. `OPENDART_CORP_CLS`는 기본 `Y,K`입니다.

Today payload 주요 섹션:

- `daily_indicators`: 금리, 환율, 물가, 성장 지표 표시 슬롯입니다. USD/KRW, JPY/KRW, CNY/KRW는 FinanceDataReader에서 일 단위 최신값을 가져오며, 환율 상승/하락으로 원화 약세/강세를 단순 판단합니다. 명목/실질 금리, CPI/물가상승률, GDP/무역수지는 BOK 또는 별도 지표 소스가 연결되면 같은 슬롯에 채워집니다.
- `headlines`: 이 시각 주요 헤드라인 3~5개를 담을 수 있으며, 각 항목은 한 문장 요약(`sentence`), 원문 링크(`news_url`), evidence를 포함합니다.
- `issues`: 오늘의 주요 이슈 3개를 담고, `subscription_key`와 `trackable=true`를 포함해 Issue Tracking에 넣을 수 있게 합니다.
- `tracked_issues`: `WATCH_ISSUES` 기반 후속 뉴스 섹션이며, 구독 해제를 위한 `unsubscribe_action`을 포함합니다.
- `events`: 정책브리핑, 공시, 거시 지표, 시장 변동 등 특이사항 후보를 담습니다.

주의: CPI와 GDP는 원천 지표 자체가 보통 월/분기 단위입니다. Today 화면에서는 “오늘 확인 가능한 최신 발표값”으로 표시할 수 있지만, 실제 지표의 관측 주기는 payload의 `frequency`에 `monthly` 또는 `quarterly`로 남깁니다.

PoC에서 의도적으로 제외한 항목:

- 복잡한 reranker, DBSCAN/클러스터링, agent workflow
- 분산 worker와 고급 스케줄러
- 한국은행/OpenDART의 완전 수집 구현
- 고급 경제 regime 판정과 개인화 추천

## 검색 테스트

`scripts/test_search.py`는 semantic search와 keyword search 결과를 단순 가중합으로 합칩니다.

- semantic weight: `0.7`
- keyword weight: `0.3`

테스트 쿼리:

```text
오늘 한국 증시에서 반도체와 전력기기에 영향을 줄 정책과 공시를 찾아줘
원화 약세가 포트폴리오에 줄 수 있는 리스크를 찾아줘
장기금리 상승이 성장주에 부담이 되는 근거를 찾아줘
AI 데이터센터 투자 확대와 관련된 수혜 산업을 찾아줘
반도체 수출 회복과 관련된 최근 근거를 찾아줘
```

## 외부 수집기

`app/ingest/` 아래 collector는 구조만 만들어져 있습니다. ECOS, KOSIS, 환율, 무역, KRX, OpenDART, KIND, 정책, 뉴스, 뱅크샐러드 export 연동을 이 위치에 붙이면 됩니다.
