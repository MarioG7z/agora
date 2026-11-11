from collections import deque
from enum import StrEnum
from graphlib import TopologicalSorter

from agora.errors import InvalidTransition


class Status(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    IN_AUDIT = "in_audit"
    APPROVED = "approved"
    FAILED = "failed"
    INVALIDATED = "invalidated"
    WAITING_USER = "waiting_user"


ALLOWED_TRANSITIONS = {
    Status.PENDING: {Status.RUNNING},
    Status.RUNNING: {Status.IN_AUDIT, Status.FAILED, Status.PENDING},
    Status.IN_AUDIT: {Status.APPROVED, Status.RUNNING, Status.FAILED},
    Status.APPROVED: {Status.INVALIDATED, Status.RUNNING},
    Status.FAILED: {Status.WAITING_USER, Status.INVALIDATED},
    Status.INVALIDATED: {Status.PENDING},
    Status.WAITING_USER: {Status.RUNNING},
}


class Task:
    def __init__(self, name: str, depends_on: list[str] | None = None):
        self.name = name
        self.status = Status.PENDING
        self.depends_on = depends_on or []
        self.attempts = 0  # how many times the task entered RUNNING
        self.artifact: str | None = None  # current artifact as JSON text

    def move_to(self, new_status: Status) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(f"{self.name}: {self.status} -> {new_status}")
        self.status = new_status
        if new_status == Status.RUNNING:
            self.attempts = self.attempts + 1


class Board:
    """The tasks of one run and the dependencies between them."""

    def __init__(self, tasks: list[Task]):
        self.tasks = {task.name: task for task in tasks}
        self.order = self._topological_order()

    def _topological_order(self) -> list[str]:
        graph = {name: set(task.depends_on) for name, task in self.tasks.items()}
        for name, deps in graph.items():
            unknown = deps - graph.keys()
            if unknown:
                raise ValueError(f"{name} depends on unknown tasks: {sorted(unknown)}")
        # Raises graphlib.CycleError (a ValueError) if the dependencies form a cycle.
        return list(TopologicalSorter(graph).static_order())

    def ready(self) -> list[Task]:
        """Tasks that can start now: waiting, with every dependency approved.

        An invalidated task is included: the orchestrator moves it to PENDING and then RUNNING.
        """
        waiting = {Status.PENDING, Status.INVALIDATED}
        ready = []
        for name in self.order:
            task = self.tasks[name]
            deps_approved = all(
                self.tasks[dep].status == Status.APPROVED for dep in task.depends_on
            )
            if task.status in waiting and deps_approved:
                ready.append(task)
        return ready

    def dependents(self, name: str) -> list[Task]:
        return [task for task in self.tasks.values() if name in task.depends_on]

    def invalidate_dependents(self, name: str) -> list[str]:
        """Invalidate every task reachable from `name`, walking the graph breadth first.

        Only tasks that already produced a result (approved or failed) change state; pending
        ones simply keep waiting. Returns the names that were invalidated.
        """
        invalidated = []
        seen = {name}
        queue = deque([name])
        while queue:
            current = queue.popleft()
            for task in self.dependents(current):
                if task.name in seen:
                    continue
                seen.add(task.name)
                queue.append(task.name)
                if task.status in {Status.APPROVED, Status.FAILED}:
                    task.move_to(Status.INVALIDATED)
                    invalidated.append(task.name)
        return invalidated

    def resume(self) -> list[str]:
        """After a crash, a task left RUNNING may not have finished: send it back to PENDING."""
        resumed = []
        for task in self.tasks.values():
            if task.status == Status.RUNNING:
                task.move_to(Status.PENDING)
                resumed.append(task.name)
        return resumed
