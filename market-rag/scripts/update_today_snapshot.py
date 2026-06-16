from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.search.hybrid_search import HybridSearch
from app.store.postgres_store import PostgresStore


TODAY_QUERY = "오늘 한국 증시에서 반도체, 전력기기, 금리, 환율에 영향을 줄 핵심 이슈를 찾아줘"


if __name__ == "__main__":
    search = HybridSearch()
    results = search.search(TODAY_QUERY, limit=5)
    store = PostgresStore()
    retrieval_id = store.record_retrieval_run(TODAY_QUERY, results, top_k=5)
    snapshot_id = store.upsert_today_from_search_results(results)
    print(f"Recorded retrieval_run={retrieval_id}")
    print(f"Updated today_snapshot={snapshot_id}")
