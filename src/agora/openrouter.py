"""Client for OpenRouter chat completions, with retries for temporary failures."""

import asyncio

import httpx

from agora.errors import PermanentError, TransientError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterModel:
    """A model served by OpenRouter, asked to answer with one JSON object."""

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient):
        self.api_key = api_key
        self.model = model
        self.client = client

    async def complete(self, system: str, user: str) -> str:
        """Ask the model, retrying temporary failures up to 3 times with backoff."""
        for attempt in range(1, 4):  # attempts 1, 2 and 3
            try:
                return await self._complete_once(system, user)
            except TransientError:
                if attempt == 3:
                    raise  # out of attempts: let the error go up
                await asyncio.sleep(2 ** (attempt - 1))  # waits 1s, then 2s

    async def _complete_once(self, system: str, user: str) -> str:
        """One request. Network errors, 429 and 5xx are temporary; other 4xx
        are permanent.
        """
        try:
            response = await self.client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.TransportError as error:
            # Timeouts and dropped connections.
            raise TransientError(f"OpenRouter request failed: {error!r}") from error

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientError(f"OpenRouter answered {response.status_code}")
        if response.status_code >= 400:
            raise PermanentError(f"OpenRouter answered {response.status_code}: {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]
