"""The model connector: the interface every model follows and a scripted fake."""

from typing import Protocol


class ModelClient(Protocol):
    """Any model: takes the system prompt and the user input, answers with text."""

    async def complete(self, system: str, user: str) -> str: ...


class FakeModel:
    """A scripted model for tests: answers in order and records every input."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
        self.received = []

    async def complete(self, system: str, user: str) -> str:
        """Return the next scripted response and record the input received."""
        response = self.responses[self.index]
        self.index = self.index + 1
        self.received.append(user)
        return response
