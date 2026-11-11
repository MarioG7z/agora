import httpx
import pytest

from agora.errors import PermanentError, TransientError
from agora.search import TavilySearch

# Hand-recorded answer in the shape of Tavily's search API.
TAVILY_ANSWER = {
    "query": "python dataclasses",
    "results": [
        {
            "title": "dataclasses - Data Classes",
            "url": "https://docs.python.org/3/library/dataclasses.html",
            "content": "This module provides a decorator for generating special methods.",
            "score": 0.92,
        }
    ],
    "response_time": 0.8,
}


def scripted_client(answers):
    """Client that answers each request with the next item: a status code or "timeout"."""
    requests = []

    def handler(request):
        requests.append(request)
        answer = answers[len(requests) - 1]
        if answer == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if answer == 200:
            return httpx.Response(200, json=TAVILY_ANSWER)
        return httpx.Response(answer, text="error")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


@pytest.mark.asyncio
async def test_search_returns_results():
    client, requests = scripted_client([200])
    search = TavilySearch("test-key", client, base_delay=0)

    results = await search.search("python dataclasses")

    assert results[0].url == "https://docs.python.org/3/library/dataclasses.html"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert b"python dataclasses" in requests[0].content


@pytest.mark.asyncio
async def test_search_retries_after_server_error():
    client, requests = scripted_client([503, 200])
    search = TavilySearch("test-key", client, base_delay=0)

    results = await search.search("python dataclasses")

    assert len(results) == 1
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_search_retries_after_timeout():
    client, requests = scripted_client(["timeout", 200])
    search = TavilySearch("test-key", client, base_delay=0)

    results = await search.search("python dataclasses")

    assert len(results) == 1
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_search_gives_up_after_max_attempts():
    client, requests = scripted_client([500, 500, 500])
    search = TavilySearch("test-key", client, max_attempts=3, base_delay=0)

    with pytest.raises(TransientError):
        await search.search("python dataclasses")
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_search_fails_without_retry_on_unauthorized():
    client, requests = scripted_client([401, 200])
    search = TavilySearch("bad-key", client, base_delay=0)

    with pytest.raises(PermanentError):
        await search.search("python dataclasses")
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_search_stops_at_search_limit():
    client, requests = scripted_client([200, 200, 200])
    search = TavilySearch("test-key", client, max_searches=2, base_delay=0)

    await search.search("first")
    await search.search("second")
    with pytest.raises(PermanentError):
        await search.search("third")
    assert len(requests) == 2
