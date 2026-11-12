"""User changes: a change enters through one phase and redoes it and every phase after it."""

import pytest

from agora.auditor import Auditor
from agora.board import Status
from agora.demo import DEMO_REQUEST, demo_models, make_agents, make_board
from agora.orchestrator import Orchestrator
from agora.store import BoardStore
from agora.workspace import Workspace

CHANGE = "Agrega una prueba para una categoria con acentos"


def test_invalidate_redoes_the_phase_and_everything_after_it():
    board = make_board()
    for task in board.tasks.values():
        task.status = Status.APPROVED  # a finished run

    redo = board.invalidate("prd")

    assert redo == ["prd", "spec", "implementation"]
    assert board.tasks["research"].status == Status.APPROVED
    assert board.tasks["implementation"].status == Status.INVALIDATED


def build(board, workspace, store, changes):
    """An orchestrator over a stored run, with a fresh set of scripted answers."""
    models = demo_models()
    orchestrator = Orchestrator(
        board,
        make_agents(models, workspace),
        auditor=Auditor(workspace.root),
        store=store,
        run_id="run-1",
        changes=changes,
    )
    return orchestrator, models


async def finished_run(tmp_path):
    """Run the demo to the end and return its workspace and store."""
    workspace = Workspace(tmp_path / "workspace")
    store = BoardStore(tmp_path / "runs.db")
    orchestrator, _ = build(make_board(), workspace, store, changes=None)
    async for _ in orchestrator.run(DEMO_REQUEST):
        pass
    return workspace, store


@pytest.mark.asyncio
async def test_change_redoes_spec_and_implementation_and_keeps_earlier_phases(tmp_path):
    workspace, store = await finished_run(tmp_path)
    board = store.load("run-1")
    before = {name: (task.artifact, task.attempts) for name, task in board.tasks.items()}
    board.invalidate("spec")
    orchestrator, models = build(board, workspace, store, changes={"spec": CHANGE})

    events = [(event.kind, event.task) async for event in orchestrator.run(DEMO_REQUEST)]

    assert events == [
        ("started", "spec"),
        ("approved", "spec"),
        ("started", "implementation"),
        ("approved", "implementation"),
        ("finished", ""),
    ]
    assert CHANGE in models["spec"].received[0]  # the changed phase gets the user's text
    assert CHANGE not in models["implementation"].received[0]  # the next ones get artifacts
    saved = store.load("run-1")
    for name in ["research", "prd"]:  # earlier phases untouched
        assert (saved.tasks[name].artifact, saved.tasks[name].attempts) == before[name]
    assert all(task.status == Status.APPROVED for task in saved.tasks.values())
    assert saved.tasks["spec"].attempts == 1  # a change opens a new round of attempts
    store.close()


@pytest.mark.asyncio
async def test_changed_phase_gets_its_full_attempts_again(tmp_path):
    # The demo PRD already used 2 of 3 attempts. After a change the scripted PRD is rejected
    # once more; with the attempts kept from before, that rejection would fail the task.
    workspace, store = await finished_run(tmp_path)
    board = store.load("run-1")
    board.invalidate("prd")
    orchestrator, _ = build(board, workspace, store, changes={"prd": CHANGE})

    kinds = [event.kind async for event in orchestrator.run(DEMO_REQUEST)]

    assert "failed" not in kinds
    assert board.tasks["prd"].status == Status.APPROVED
    assert board.tasks["prd"].attempts == 2
    store.close()
