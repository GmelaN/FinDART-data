from typing import Iterable

from elasticsearch.helpers import bulk

from app.config import Settings, get_settings
from app.elastic_init import get_elasticsearch_client
from app.models.document import DocumentChunk


class ElasticsearchDocumentStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = get_elasticsearch_client(self.settings)
        self.index_name = self.settings.collection_market_docs

    def bulk_index_chunks(self, chunks: Iterable[DocumentChunk]) -> int:
        actions = [
            {
                "_op_type": "index",
                "_index": self.index_name,
                "_id": chunk.point_id,
                "_source": chunk.payload(),
            }
            for chunk in chunks
        ]
        if not actions:
            return 0
        success, _ = bulk(self.client, actions)
        self.client.indices.refresh(index=self.index_name)
        return success

