from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

@dataclass(frozen=True)
class FetchResult:
    url: str
    title: str | None
    text: str
    fetched_at: datetime | None = None
    query: str | None = None
    source_type: str = "fetch"
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.fetched_at is None:
            object.__setattr__(self, "fetched_at", datetime.now(timezone.utc))

class SearchProvider(Protocol):
    async def search_web(self, query: str) -> list[FetchResult]: ...

class WebFetcher(Protocol):
    async def fetch_url(self, url: str) -> FetchResult: ...
