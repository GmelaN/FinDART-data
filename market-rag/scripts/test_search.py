from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.search.hybrid_search import HybridSearch


QUERIES = [
    "오늘 한국 증시에서 반도체와 전력기기에 영향을 줄 정책과 공시를 찾아줘",
    "원화 약세가 포트폴리오에 줄 수 있는 리스크를 찾아줘",
    "장기금리 상승이 성장주에 부담이 되는 근거를 찾아줘",
    "AI 데이터센터 투자 확대와 관련된 수혜 산업을 찾아줘",
    "반도체 수출 회복과 관련된 최근 근거를 찾아줘",
]


if __name__ == "__main__":
    search = HybridSearch()
    for query in QUERIES:
        print("\n" + "=" * 100)
        print(f"QUERY: {query}")
        for idx, result in enumerate(search.search(query, limit=5), start=1):
            payload = result["payload"]
            print(
                f"{idx}. score={result['score']:.4f} "
                f"sem={result['semantic_score']:.4f} kw={result['keyword_score']:.4f}"
            )
            print(f"   title={payload.get('title')}")
            print(f"   source={payload.get('source_name')} type={payload.get('source_type')}")
            print(f"   tags macro={payload.get('macro_tags')} sector={payload.get('sector_tags')} risk={payload.get('risk_tags')}")
            print(f"   text={payload.get('text', '')[:180]}")

