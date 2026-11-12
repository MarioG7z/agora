"""What the user sees in the terminal: the live tree while a run works, then the delivery."""

import json
import time
from collections.abc import Callable
from pathlib import Path

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from agora.board import Board, Status
from agora.contracts import PRD, Implementation, ResearchBrief, Spec
from agora.orchestrator import MAX_PHASE_ATTEMPTS, Event

# Task name -> (phase shown to the user, agent that works on it).
PHASES = {
    "research": ("Planning", "Investigador"),
    "prd": ("PRD", "Producto"),
    "spec": ("Spec", "Arquitecto"),
    "implementation": ("Implementation", "Desarrollador"),
}

# Status -> (symbol, text, style).
STATUS = {
    Status.PENDING: ("○", "pendiente", "dim"),
    Status.RUNNING: ("⟳", "en curso", "yellow"),
    Status.IN_AUDIT: ("⟳", "en auditoría", "yellow"),
    Status.APPROVED: ("✓", "aprobada", "green"),
    Status.FAILED: ("✗", "fallida", "red"),
    Status.INVALIDATED: ("↺", "invalidada", "magenta"),
    Status.WAITING_USER: ("?", "esperando al usuario", "cyan"),
}


# Task name -> what its agent works on, shown while the first attempt runs.
OBJECTIVES = {
    "research": "extrae los pedidos del usuario",
    "prd": "escribe requisitos con criterios de aceptación",
    "spec": "planea interfaces, archivos y pruebas",
    "implementation": "escribe el código y ejecuta pytest",
}


def phase_name(task_name: str) -> str:
    return PHASES.get(task_name, (task_name, ""))[0]


def delivered(task_name: str, artifact: str) -> str:
    """What an approved task delivered, counted from its artifact."""
    data = json.loads(artifact)
    if task_name == "research":
        return f"{len(data['asks'])} pedidos"
    if task_name == "prd":
        return f"{len(data['requirements'])} requisitos"
    if task_name == "spec":
        return f"{len(data['files'])} archivos · {len(data['tests'])} pruebas"
    if task_name == "implementation":
        results = data["test_results"]
        passed = sum(1 for result in results if result["passed"])
        return f"{passed}/{len(results)} pruebas pasan"
    return "entregada"


class LiveTree:
    """The board drawn as a tree. The state comes from the board; the events add the history.

    The board only knows the current state of each task, so the rejected attempts and their
    reasons are collected from the events as they arrive.
    """

    def __init__(
        self,
        board: Board,
        run_id: str,
        request: str,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.board = board
        self.title = f'Ejecución {run_id} · "{request}"'
        self.history: dict[str, list[str]] = {name: [] for name in board.tasks}
        self.last_problem: Event | None = None  # last rejection or failure, shown in full
        self.clock = clock
        self.started_at: dict[str, float] = {}  # when each task started its current attempt
        self.last_reason: dict[str, str] = {}  # first problem of the last rejection of each task

    def update(self, event: Event) -> None:
        if event.kind == "started":
            self.started_at[event.task] = self.clock()
        if event.kind in {"rejected", "failed"}:
            first_line = event.detail.splitlines()[0].removeprefix("- ") if event.detail else ""
            self.history[event.task].append(f"✗ intento {event.attempt}: {first_line}")
            self.last_reason[event.task] = first_line
            self.last_problem = event

    def activity(self, name: str) -> str:
        """What the task is doing right now, in words. Every phrase comes from the board."""
        task = self.board.tasks[name]
        if task.status == Status.PENDING:
            waiting = [
                dep for dep in task.depends_on if self.board.tasks[dep].status != Status.APPROVED
            ]
            if waiting:
                return "espera a " + ", ".join(phase_name(dep) for dep in waiting)
            return "lista para empezar"
        if task.status == Status.RUNNING:
            if task.attempts > 1 and name in self.last_reason:
                return "corrige: " + self.last_reason[name]
            return OBJECTIVES.get(name, "trabajando")
        if task.status == Status.IN_AUDIT:
            return "el auditor revisa la entrega"
        if task.status == Status.APPROVED and task.artifact:
            return delivered(name, task.artifact)
        if task.status == Status.FAILED:
            return f"detenida tras {task.attempts} intentos"
        if task.status == Status.INVALIDATED:
            return "se rehará por un cambio"
        return "espera una decisión"

    def render(self) -> RenderableType:
        tree = Tree(Text(self.title, style="bold"))
        for name in self.board.order:
            task = self.board.tasks[name]
            phase, agent = PHASES.get(name, (name, ""))
            symbol, label, style = STATUS[task.status]
            attempt = f"intento {task.attempts}/{MAX_PHASE_ATTEMPTS}" if task.attempts else ""
            row = f"{phase:<15} {agent:<14} {label:<13} {attempt:<12}"
            doing = self.activity(name)
            if len(doing) > 50:
                doing = doing[:49] + "…"
            if task.status in {Status.RUNNING, Status.IN_AUDIT}:
                # A spinner and a clock on the working task, so a long model call does not
                # look like a frozen program. Live redraws it several times per second.
                seconds = int(self.clock() - self.started_at.get(name, self.clock()))
                text = Text.assemble((row, style), (f"{seconds:>3} s  ", style), (doing, "italic"))
                node = tree.add(Spinner("dots", text, style=style))
            else:
                text = Text.assemble((f"{symbol} {row}", style), ("       ", ""), (doing, "italic"))
                node = tree.add(text)
            for line in self.history[name]:
                node.add(Text(line, style="red"))
        if self.last_problem is None:
            return tree
        event = self.last_problem
        what = "Último rechazo del auditor" if event.kind == "rejected" else "Fallo"
        title = f"{what} · {phase_name(event.task)}, intento {event.attempt}"
        return Group(tree, Panel(event.detail, title=title, title_align="left", border_style="red"))


def delivery(board: Board, code: Path, log: Path, seconds: int = 0) -> RenderableType:
    """The summary shown when the run ends: one row per phase and where everything was left."""
    phases = Table(title="Entrega", title_justify="left")
    for column in ["Fase", "Agente", "Estado", "Intentos"]:
        phases.add_column(column)
    for name in board.order:
        task = board.tasks[name]
        phase, agent = PHASES.get(name, (name, ""))
        symbol, label, style = STATUS[task.status]
        phases.add_row(phase, agent, Text(f"{symbol} {label}", style), str(task.attempts))
    parts: list[RenderableType] = [phases]
    trace = traceability(board)
    if trace is not None:
        parts.append(trace)
    parts.append(Text(f"Código generado en {code}\nRegistro de eventos en {log}"))
    parts.append(Text(f"Duración total: {seconds // 60}:{seconds % 60:02d}"))
    return Group(*parts)


def traceability(board: Board) -> Table | None:
    """The chain ASK -> REQ -> test -> result, read from the artifacts of a finished run."""
    if any(
        name not in board.tasks or board.tasks[name].status != Status.APPROVED for name in PHASES
    ):
        return None  # without every artifact approved there is no complete chain to show
    brief = ResearchBrief.model_validate_json(board.tasks["research"].artifact)
    prd = PRD.model_validate_json(board.tasks["prd"].artifact)
    spec = Spec.model_validate_json(board.tasks["spec"].artifact)
    code = Implementation.model_validate_json(board.tasks["implementation"].artifact)
    passed = {result.test_id: result.passed for result in code.test_results}

    table = Table(title="Trazabilidad", title_justify="left")
    for column in ["Pedido", "Requisito", "Pruebas", "Estado"]:
        table.add_column(column)
    for ask in brief.asks:
        reqs = [req.id for req in prd.requirements if ask.id in req.covers]
        tests = [test.id for test in spec.tests if set(test.covers) & set(reqs)]
        ok = bool(tests) and all(passed.get(test, False) for test in tests)
        state = Text("✓ pasa", "green") if ok else Text("✗ falla", "red")
        table.add_row(f"{ask.id} {ask.description}", ", ".join(reqs), ", ".join(tests), state)
    return table
