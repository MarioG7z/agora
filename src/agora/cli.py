import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from agora.auditor import Auditor
from agora.demo import DEMO_REQUEST, demo_models, make_agents, make_board
from agora.eventlog import EventLog
from agora.llm import ModelClient
from agora.openrouter import OpenRouterModel
from agora.orchestrator import Event, Orchestrator
from agora.store import BoardStore
from agora.workspace import Workspace

LABELS = {
    "started": "▶ inicia",
    "approved": "✔ aprobada",
    "rejected": "✘ rechazada",
    "failed": "■ fallida",
    "finished": "● ejecución terminada",
}


def show(event: Event) -> None:
    label = LABELS.get(event.kind, event.kind)
    attempt = f" (intento {event.attempt})" if event.attempt else ""
    print(f"{label} {event.task}{attempt}")
    if event.detail:
        for line in event.detail.splitlines():
            print(f"    {line}")


def real_models(client: httpx.AsyncClient) -> dict[str, ModelClient]:
    """One OpenRouter model shared by the four experts, configured in .env."""
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model_name = os.environ.get("OPENROUTER_MODEL")
    if not api_key or not model_name:
        raise SystemExit("Faltan OPENROUTER_API_KEY u OPENROUTER_MODEL en .env (ver .env.example)")
    model = OpenRouterModel(api_key, model_name, client)
    return {name: model for name in ["research", "prd", "spec", "implementation"]}


async def run(request: str, run_id: str, resume: bool, real: bool) -> None:
    store = BoardStore(Path("workspace") / "agora.db")
    if resume:
        board = store.load(run_id)
        resumed = board.resume()
        print(f"Reanudando {run_id}; se repiten: {', '.join(resumed) or 'ninguna'}")
    else:
        board = make_board()
    workspace = Workspace(Path("workspace") / run_id)
    async with httpx.AsyncClient(timeout=120) as client:
        models = real_models(client) if real else demo_models()
        orchestrator = Orchestrator(
            board,
            make_agents(models, workspace),
            auditor=Auditor(workspace.root),
            store=store,
            run_id=run_id,
        )
        log = EventLog(Path("logs") / f"{run_id}.jsonl")
        async for event in orchestrator.run(request):
            log.write(run_id, event)
            show(event)
    store.close()
    print(f"\nCódigo generado en {workspace.root}")
    print(f"Registro de eventos en {log.path}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="agora", description="AGORA: equipo multiagente")
    parser.add_argument("request", nargs="?", default=DEMO_REQUEST, help="La tarea a construir")
    parser.add_argument("--run-id", default=datetime.now().strftime("run-%Y%m%d-%H%M%S"))
    parser.add_argument("--resume", action="store_true", help="Reanuda la ejecución --run-id")
    parser.add_argument("--real", action="store_true", help="Usa OpenRouter en vez del simulado")
    args = parser.parse_args()
    asyncio.run(run(args.request, args.run_id, args.resume, args.real))
