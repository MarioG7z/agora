import pytest

from agora.agent import Agent
from agora.contracts import Ask
from agora.errors import SchemaValidationError
from agora.llm import FakeModel

VALID = '{"id": "ASK-1", "description": "listar productos"}'
BROKEN = '{"id": "ASK-1"}'  # missing description → ValidationError


@pytest.mark.asyncio
async def test_agent_returns_artifact_when_first_answer_is_valid():
    model = FakeModel([VALID])
    agent = Agent("asker", model, "You write asks.", Ask)

    artifact = await agent.run("listar productos")

    assert artifact.id == "ASK-1"


@pytest.mark.asyncio
async def test_agent_retries_after_invalid_answer():
    model = FakeModel([BROKEN, VALID])
    agent = Agent("asker", model, "You write asks.", Ask)

    artifact = await agent.run("listar productos")

    assert artifact.id == "ASK-1"
    assert model.index == 2


@pytest.mark.asyncio
async def test_agent_gives_up_after_three_invalid_answers():
    model = FakeModel([BROKEN, BROKEN, BROKEN])
    agent = Agent("asker", model, "You write asks.", Ask)

    with pytest.raises(SchemaValidationError, match="asker"):
        await agent.run("listar productos")
