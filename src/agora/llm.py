from typing import Protocol


class ModelClient(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


class FakeModel:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
        self.received = []

    async def complete(self, system: str, user: str) -> str:
        response = self.responses[self.index]
        self.index = self.index + 1
        self.received.append(user)
        return response
