class FakeModel:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0

    async def complete(self, system: str, user: str) -> str:
        response = self.responses[self.index]
        self.index = self.index + 1
        return response
