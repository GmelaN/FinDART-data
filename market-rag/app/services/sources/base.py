from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.document import MarketDocument


class SourceFetchError(RuntimeError):
    pass


class SourceFetcher(ABC):
    source_name: str

    @abstractmethod
    def fetch(self, *, since: datetime | None = None, limit: int | None = None) -> list[MarketDocument]:
        raise NotImplementedError
