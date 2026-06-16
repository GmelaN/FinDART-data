from elasticsearch import Elasticsearch

from app.config import Settings, get_settings


def get_elasticsearch_client(settings: Settings | None = None) -> Elasticsearch:
    settings = settings or get_settings()
    return Elasticsearch(settings.elasticsearch_url)


MARKET_DOCS_MAPPING = {
    "settings": {
        "index": {"max_ngram_diff": 18},
        "analysis": {
            "tokenizer": {
                "ko_ngram_tokenizer": {
                    "type": "ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"],
                }
            },
            "analyzer": {
                "ko_text": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase"],
                },
                "ko_ngram": {
                    "type": "custom",
                    "tokenizer": "ko_ngram_tokenizer",
                    "filter": ["lowercase"],
                },
            },
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "chunk_id": {"type": "integer"},
            "title": {
                "type": "text",
                "analyzer": "ko_text",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "ngram": {"type": "text", "analyzer": "ko_ngram", "search_analyzer": "ko_text"},
                },
            },
            "text": {
                "type": "text",
                "analyzer": "ko_text",
                "fields": {
                    "ngram": {"type": "text", "analyzer": "ko_ngram", "search_analyzer": "ko_text"}
                },
            },
            "source_name": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "source_url": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "collected_at": {"type": "date"},
            "country": {"type": "keyword"},
            "language": {"type": "keyword"},
            "macro_tags": {"type": "keyword"},
            "sector_tags": {"type": "keyword"},
            "asset_tags": {"type": "keyword"},
            "company_names": {"type": "keyword"},
            "tickers": {"type": "keyword"},
            "event_date": {"type": "date"},
            "impact_horizon": {"type": "keyword"},
            "importance": {"type": "float"},
            "sentiment": {"type": "keyword"},
            "summary_kr": {
                "type": "text",
                "analyzer": "ko_text",
                "fields": {
                    "ngram": {"type": "text", "analyzer": "ko_ngram", "search_analyzer": "ko_text"}
                },
            },
            "extracted_facts": {"type": "object", "enabled": True},
            "risk_tags": {"type": "keyword"},
            "hash": {"type": "keyword"},
            "embedding_model": {"type": "keyword"},
        }
    },
}


def init_elastic(settings: Settings | None = None, recreate: bool = False) -> None:
    settings = settings or get_settings()
    client = get_elasticsearch_client(settings)
    index_name = settings.collection_market_docs
    if client.indices.exists(index=index_name):
        if not recreate:
            print(f"Elasticsearch index exists: {index_name}")
            return
        client.indices.delete(index=index_name)
        print(f"Elasticsearch index deleted: {index_name}")
    client.indices.create(index=index_name, body=MARKET_DOCS_MAPPING)
    print(f"Elasticsearch index created: {index_name}")


if __name__ == "__main__":
    init_elastic()
