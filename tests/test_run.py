"""Integration: the four experts, the auditor and the store working together on the demo."""

import json

import pytest

from agora.auditor import Auditor
from agora.board import Status
from agora.demo import DEMO_REQUEST, PRD_MISSING_ASK_2, demo_models, make_agents, make_board
from agora.eventlog import EventLog
from agora.llm import FakeModel
from agora.orchestrator import Orchestrator
from agora.store import BoardStore
from agora.workspace import Workspace


def build(tmp_path, models=None):
    workspace = Workspace(tmp_path / "workspace")
    store = BoardStore(tmp_path / "runs.db")
    orchestrator = Orchestrator(
        make_board(),
        make_agents(models or demo_models(), workspace),
        auditor=Auditor(workspace.root),
        store=store,
        run_id="run-1",
    )
    return orchestrator, store


async def collect(orchestrator):
    return [(event.kind, event.task) async for event in orchestrator.run(DEMO_REQUEST)]


@pytest.mark.asyncio
async def test_demo_run_rejects_the_first_prd_and_finishes(tmp_path):
    orchestrator, store = build(tmp_path)

    events = await collect(orchestrator)

    assert events == [
        ("started", "research"),
        ("approved", "research"),
        ("started", "prd"),
        ("rejected", "prd"),
        ("started", "prd"),
        ("approved", "prd"),
        ("started", "spec"),
        ("approved", "spec"),
        ("started", "implementation"),
        ("approved", "implementation"),
        ("finished", ""),
    ]
    saved = store.load("run-1")
    assert all(task.status == Status.APPROVED for task in saved.tasks.values())
    assert saved.tasks["prd"].attempts == 2
    assert len(store.versions("run-1", "prd")) == 2  # the rejected PRD stays in the history
    store.close()


@pytest.mark.asyncio
async def test_retry_carries_the_auditor_verdict(tmp_path):
    models = demo_models()
    orchestrator, store = build(tmp_path, models)

    await collect(orchestrator)

    assert "ASK-2" in models["prd"].received[1]
    store.close()


@pytest.mark.asyncio
async def test_task_fails_after_three_rejections(tmp_path):
    models = demo_models()
    models["prd"] = FakeModel([PRD_MISSING_ASK_2.model_dump_json()] * 3)
    orchestrator, store = build(tmp_path, models)

    events = await collect(orchestrator)

    assert events[-2:] == [("rejected", "prd"), ("failed", "prd")]
    assert orchestrator.board.tasks["prd"].status == Status.FAILED
    assert orchestrator.board.tasks["spec"].status == Status.PENDING
    store.close()


def test_event_log_writes_one_json_line_per_event(tmp_path):
    from agora.orchestrator import Event

    log = EventLog(tmp_path / "logs" / "run-1.jsonl")

    log.write("run-1", Event(kind="started", task="prd", attempt=1))
    log.write("run-1", Event(kind="approved", task="prd", attempt=1))

    lines = (tmp_path / "logs" / "run-1.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["started", "approved"]
    assert json.loads(lines[0])["run_id"] == "run-1"


class BrokenModel:
    """A model whose provider rejects the key: the error the client raises after a 401."""

    async def complete(self, system: str, user: str) -> str:
        from agora.errors import PermanentError

        raise PermanentError("OpenRouter answered 401: invalid key")


@pytest.mark.asyncio
async def test_model_failure_fails_the_task_instead_of_crashing(tmp_path):
    models = demo_models()
    models["research"] = BrokenModel()
    orchestrator, store = build(tmp_path, models)

    events = await collect(orchestrator)

    assert events == [("started", "research"), ("failed", "research")]
    assert orchestrator.board.tasks["research"].status == Status.FAILED
    store.close()
