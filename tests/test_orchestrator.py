import pytest

from agora.agent import Agent
from agora.board import Board, Status, Task
from agora.contracts import Ask
from agora.llm import FakeModel
from agora.orchestrator import Orchestrator

VALID = '{"id": "ASK-1", "description": "listar productos"}'
BROKEN = '{"id": "ASK-1"}'


@pytest.mark.asyncio
async def test_orchestrator_runs_every_task_in_order():
    # PREPARAR: two tasks, the second depends on the first
    board = Board([Task("first"), Task("second", ["first"])])
    second_model = FakeModel([VALID])
    agents = {
        "first": Agent("first", FakeModel([VALID]), "You write asks.", Ask),
        "second": Agent("second", second_model, "You write asks.", Ask),
    }
    orchestrator = Orchestrator(board, agents)

    # ACTUAR: collect every event the run yields
    events = []
    async for event in orchestrator.run("una API de inventario"):
        events.append(event.kind)

    # COMPROBAR
    assert events == ["started", "approved", "started", "approved", "finished"]
    assert board.tasks["second"].status == Status.APPROVED
    assert "ASK-1" in second_model.received[0]  # the box from "first" reached "second"


@pytest.mark.asyncio
async def test_orchestrator_stops_when_an_agent_gives_up():
    # two tasks, the second depends on the first
    board = Board([Task("first"), Task("second", ["first"])])
    second_model = FakeModel([BROKEN, BROKEN, BROKEN])
    agents = {
        "first": Agent("first", FakeModel([VALID]), "You write asks.", Ask),
        "second": Agent("second", second_model, "You write asks.", Ask),
    }
    orchestrator = Orchestrator(board, agents)

    # collect every event the run yields
    events = []
    async for event in orchestrator.run("una API de inventario"):
        events.append(event.kind)

    # Validate
    assert events == ["started", "approved", "started", "failed"]
    assert board.tasks["second"].status == Status.FAILED
    assert "ASK-1" in second_model.received[0]  # the box from "first" reached "second"
