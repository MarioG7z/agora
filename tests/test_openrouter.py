import httpx
import pytest

from agora.errors import PermanentError
from agora.openrouter import OpenRouterModel

# Hand-written answer in the shape of OpenRouter's chat completions API.
ANSWER = {"choices": [{"message": {"content": '{"id": "ASK-1"}'}}]}


def scripted_client(statuses):
    """A client whose answers follow a script of status codes, without touching the network."""
    requests = []

    def handler(request):
        requests.append(request)
        status = statuses[len(requests) - 1]
        if status == 200:
            return httpx.Response(200, json=ANSWER)
        return httpx.Response(status, text="error")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requests


@pytest.mark.asyncio
async def test_complete_returns_the_model_text():
    client, requests = scripted_client([200])
    model = OpenRouterModel("test-key", "test-model", client)

    text = await model.complete("system", "user")

    assert text == '{"id": "ASK-1"}'
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_transient_error_is_retried():
    client, requests = scripted_client([429, 200])
    model = OpenRouterModel("test-key", "test-model", client)

    text = await model.complete("system", "user")

    assert text == '{"id": "ASK-1"}'
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_permanent_error_is_not_retried():
    client, requests = scripted_client([401])
    model = OpenRouterModel("test-key", "test-model", client)

    with pytest.raises(PermanentError, match="401"):
        await model.complete("system", "user")

    assert len(requests) == 1
