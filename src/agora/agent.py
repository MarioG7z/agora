"""The base agent: asks the model, validates the answer against a contract and retries."""

from pydantic import BaseModel, ValidationError

from agora.errors import SchemaValidationError
from agora.llm import ModelClient


class Agent:
    """An expert that turns an input into an artifact validated against its schema."""

    def __init__(self, name: str, model: ModelClient, system: str, schema: type[BaseModel]):
        self.name = name
        self.model = model
        self.system = system
        self.schema = schema

    async def run(self, user: str) -> BaseModel:
        """Ask the model for an artifact and validate it against the schema.

        An invalid answer is retried, up to 3 times, with the validation error added to the input.
        """
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
