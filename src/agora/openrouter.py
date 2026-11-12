import asyncio

import httpx

from agora.errors import PermanentError, TransientError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterModel:
    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient):
        self.api_key = api_key
        self.model = model
        self.client = client

    async def complete(self, system: str, user: str) -> str:
        for attempt in range(1, 4):  # attempts 1, 2 and 3
            try:
                return await self._complete_once(system, user)
            except TransientError:
                if attempt == 3:
                    raise  # out of attempts: let the error go up
                await asyncio.sleep(2 ** (attempt - 1))  # waits 1s, then 2s

    async def _complete_once(self, system: str, user: str) -> str:
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
