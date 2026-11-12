from pydantic import BaseModel, ValidationError

from agora.errors import SchemaValidationError
from agora.llm import ModelClient


class Agent:
    def __init__(self, name: str, model: ModelClient, system: str, schema: type[BaseModel]):
        self.name = name
        self.model = model
        self.system = system
        self.schema = schema

    async def run(self, user: str) -> BaseModel:
        message = user  # first attempt: the original input
        for _attempt in range(3):  # up to 3 attempts
            text = await self.model.complete(self.system, message)
            try:
                artifact = self.schema.model_validate_json(text)
                return artifact
            except ValidationError as error:
                last_error = str(error)  # ← copy it while it exists
                message = user + "\n\nYour previous answer was invalid:\n" + str(error)
        raise SchemaValidationError(
            f"Agent {self.name} failed after 3 attempts. Last error:\n{last_error}"
        )
