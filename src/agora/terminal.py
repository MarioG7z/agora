"""What the user sees in the terminal: the live tree while a run works, then the delivery."""

from pathlib import Path

from rich.console import Group, RenderableType
from rich.panel import Panel
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


def phase_name(task_name: str) -> str:
    return PHASES.get(task_name, (task_name, ""))[0]


class LiveTree:
    """The board drawn as a tree. The state comes from the board; the events add the history.

    The board only knows the current state of each task, so the rejected attempts and their
    reasons are collected from the events as they arrive.
    """

    def __init__(self, board: Board, run_id: str, request: str):
        self.board = board
        self.title = f'Ejecución {run_id} · "{request}"'
        self.history: dict[str, list[str]] = {name: [] for name in board.tasks}
        self.last_problem: Event | None = None  # last rejection or failure, shown in full

    def update(self, event: Event) -> None:
        if event.kind in {"rejected", "failed"}:
            first_line = event.detail.splitlines()[0].removeprefix("- ") if event.detail else ""
            self.history[event.task].append(f"✗ intento {event.attempt}: {first_line}")
            self.last_problem = event

    def render(self) -> RenderableType:
        tree = Tree(Text(self.title, style="bold"))
        for name in self.board.order:
            task = self.board.tasks[name]
            phase, agent = PHASES.get(name, (name, ""))
            symbol, label, style = STATUS[task.status]
            attempt = f"intento {task.attempts}/{MAX_PHASE_ATTEMPTS}" if task.attempts else ""
            node = tree.add(Text(f"{symbol} {phase:<15} {agent:<14} {label:<13} {attempt}", style))
            for line in self.history[name]:
                node.add(Text(line, style="red"))
        if self.last_problem is None:
            return tree
        event = self.last_problem
        what = "Último rechazo del auditor" if event.kind == "rejected" else "Fallo"
        title = f"{what} · {phase_name(event.task)}, intento {event.attempt}"
        return Group(tree, Panel(event.detail, title=title, title_align="left", border_style="red"))


def delivery(board: Board, code: Path, log: Path) -> RenderableType:
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
