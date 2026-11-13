"""Command line entry point: builds every piece, runs the orchestrator, shows the run."""

import argparse
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live

from agora.auditor import Auditor
from agora.board import Board
from agora.demo import DEMO_REQUEST, demo_models, make_agents, make_board
from agora.errors import InvalidTransition
from agora.eventlog import EventLog
from agora.llm import ModelClient
from agora.openrouter import OpenRouterModel
from agora.orchestrator import Orchestrator
from agora.store import BoardStore
from agora.terminal import LiveTree, delivery, phase_name
from agora.workspace import Workspace


def real_models(client: httpx.AsyncClient) -> dict[str, ModelClient]:
    """One OpenRouter model shared by the four experts, configured in .env."""
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model_name = os.environ.get("OPENROUTER_MODEL")
    if not api_key or not model_name:
        raise SystemExit("Faltan OPENROUTER_API_KEY u OPENROUTER_MODEL en .env (ver .env.example)")
    model = OpenRouterModel(api_key, model_name, client)
    return {name: model for name in ["research", "prd", "spec", "implementation"]}


def confirm_change(board: Board, phase: str, console: Console) -> bool:
    """Invalidate the phase and its dependents in memory, then ask before spending tokens.

    Nothing is saved until the run starts, so answering no leaves the stored run untouched.
    """
    if phase not in board.tasks:
        raise SystemExit(f"Fase desconocida: {phase}. Usa una de: {', '.join(board.order)}")
    try:
        redo = board.invalidate(phase)
    except InvalidTransition:
        raise SystemExit(f"La fase {phase} aún no tiene resultado: reanuda con --resume") from None
    names = ", ".join(phase_name(name) for name in redo)
    console.print(f"El cambio entra por {phase_name(phase)}; se rehacen: {names}.")
    return console.input("¿Continuar? (s/N) ").strip().lower() == "s"


async def run(
    request: str,
    run_id: str,
    resume: bool,
    real: bool,
    change: tuple[str, str] | None = None,
    console: Console | None = None,
    pause: float = 0,
) -> None:
    """One run: new, resumed or with a change, with the live tree and then the delivery."""
    console = console or Console()
    store = BoardStore(Path("workspace") / "agora.db")
    changes = {}
    if change:
        phase, text = change
        board = store.load(run_id)
        if not confirm_change(board, phase, console):
            console.print("Cambio cancelado; la ejecución queda como estaba.")
            store.close()
            return
        changes = {phase: text}
    elif resume:
        board = store.load(run_id)
        resumed = board.resume()
        console.print(f"Reanudando {run_id}; se repiten: {', '.join(resumed) or 'ninguna'}")
    else:
        board = make_board()
    workspace = Workspace(Path("workspace") / run_id)
    async with httpx.AsyncClient(timeout=120) as client:
        models = real_models(client) if real else demo_models(pause)
        orchestrator = Orchestrator(
            board,
            make_agents(models, workspace),
            auditor=Auditor(workspace.root),
            store=store,
            run_id=run_id,
            changes=changes,
        )
        log = EventLog(Path("logs") / f"{run_id}.jsonl")
        tree = LiveTree(board, run_id, request)
        started = time.monotonic()
        # The terminal is one more consumer of the events. Live calls tree.render on its own
        # several times per second, so the spinner and the clock move while a model call waits.
        with Live(console=console, get_renderable=tree.render, refresh_per_second=8):
            async for event in orchestrator.run(request):
                log.write(run_id, event)
                tree.update(event)
    store.close()
    console.print()
    console.print(delivery(board, workspace.root, log.path, int(time.monotonic() - started)))


def main() -> None:
    """Read the command line arguments and start the run."""
    parser = argparse.ArgumentParser(prog="agora", description="AGORA: equipo multiagente")
    parser.add_argument("request", nargs="?", default=DEMO_REQUEST, help="La tarea a construir")
    parser.add_argument(
        "--run-id",
        default=datetime.now().strftime("run-%Y%m%d-%H%M%S"),
        help="Nombre de la ejecución; por defecto, run- con la fecha y la hora",
    )
    parser.add_argument("--resume", action="store_true", help="Reanuda la ejecución --run-id")
    parser.add_argument("--real", action="store_true", help="Usa OpenRouter en vez del simulado")
    parser.add_argument(
        "--change",
        nargs=2,
        metavar=("FASE", "TEXTO"),
        help="Cambio a la ejecución terminada --run-id; FASE: research, prd, spec o implementation",
    )
    parser.add_argument(
        "--pausa",
        type=float,
        default=0,
        metavar="SEGUNDOS",
        help="Con el simulado, espera antes de cada respuesta, como un modelo real",
    )
    args = parser.parse_args()
    asyncio.run(
        run(args.request, args.run_id, args.resume, args.real, args.change, pause=args.pausa)
    )
