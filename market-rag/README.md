# Market RAG

금융/경제 화면 생성을 위한 RAG 데이터 수집 및 검색 파이프라인입니다. 이번 버전은 Qdrant, Elasticsearch 저장 경로와 샘플 ingest, hybrid search를 실행 가능하게 구성하고, 외부 데이터 수집기는 skeleton으로 둡니다.

## 구성

- Qdrant: `market_docs_v1`, `entity_profiles_v1`, `portfolio_context_v1`
- Elasticsearch: `market_docs_v1`
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
python scripts/ingest_sample_docs.py
python scripts/test_search.py
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

Qdrant point id와 Elasticsearch document id는 동일한 deterministic UUID입니다. `source_url` 또는 `source_id` 기반 dedup hash를 사용하므로 같은 문서를 다시 넣어도 같은 point/document가 upsert/index 됩니다.

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

