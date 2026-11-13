"""Client for Tavily web search, capped per run, with retries for temporary failures."""

import asyncio

import httpx
from pydantic import BaseModel

from agora.errors import PermanentError, TransientError

TAVILY_URL = "https://api.tavily.com/search"


class SearchResult(BaseModel):
    """One result of a web search."""

    title: str
    url: str
    content: str


class TavilySearch:
    """Web search with Tavily, capped per run to protect the limited credits."""

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        max_searches: int = 5,
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ):
        self.api_key = api_key
        self.client = client
        self.max_searches = max_searches
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.searches_done = 0

    async def search(self, query: str) -> list[SearchResult]:
        # The cap protects the limited Tavily credits. The caller decides how to go on without it.
        """Search the web, retrying temporary failures with exponential backoff."""
        if self.searches_done >= self.max_searches:
            raise PermanentError(f"Search limit reached ({self.max_searches} per run)")
        self.searches_done = self.searches_done + 1

        for attempt in range(1, self.max_attempts + 1):
            try:
                return await self._search_once(query)
            except TransientError:
                if attempt == self.max_attempts:
                    raise
                # Exponential backoff: 1s, 2s, 4s... with the default base delay.
                await asyncio.sleep(self.base_delay * 2 ** (attempt - 1))

    async def _search_once(self, query: str) -> list[SearchResult]:
        """One request. Network errors, 429 and 5xx are temporary; other 4xx
        are permanent.
        """
        try:
            response = await self.client.post(
                TAVILY_URL,
                json={"query": query},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.TransportError as error:
            # Timeouts and dropped connections.
            raise TransientError(f"Tavily request failed: {error!r}") from error

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientError(f"Tavily answered {response.status_code}")
        if response.status_code >= 400:
            raise PermanentError(f"Tavily answered {response.status_code}: {response.text}")
        return [SearchResult.model_validate(item) for item in response.json()["results"]]
