"""The terminal: the live tree and the delivery, drawn over the scripted demo."""

import io

import pytest
from rich.console import Console

from agora import cli


def recording_console() -> Console:
    return Console(file=io.StringIO(), width=120)


@pytest.mark.asyncio
async def test_demo_run_draws_the_tree_with_the_rejected_prd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # workspace/ and logs/ are created under the test folder
    console = recording_console()

    await cli.run(cli.DEMO_REQUEST, "run-1", resume=False, real=False, console=console)

    output = console.file.getvalue()
    assert "Ejecución run-1" in output
    assert "✓ Implementation" in output
    assert "✗ intento 1:" in output  # the rejected PRD stays under its task, with its reason
    assert "ASK-2" in output
    assert "Último rechazo del auditor · PRD, intento 1" in output
    # The delivery: one row per phase, the traceability chain and where everything was left.
    assert "Entrega" in output
    assert "ASK-2 Filtrar productos por categoria" in output
    assert "✓ pasa" in output
    assert "Registro de eventos en logs" in output


def test_working_task_shows_how_long_it_has_been_waiting():
    from agora.board import Status
    from agora.demo import make_board
    from agora.orchestrator import Event
    from agora.terminal import LiveTree

    now = [100.0]  # a fake clock the test moves by hand
    board = make_board()
    tree = LiveTree(board, "run-1", "tarea", clock=lambda: now[0])
    board.tasks["research"].move_to(Status.RUNNING)
    tree.update(Event(kind="started", task="research", attempt=1))

    now[0] = 112.0  # twelve seconds waiting for the model
    console = recording_console()
    console.print(tree.render())

    assert "12 s" in console.file.getvalue()
