"""The orchestrator: delegates ready tasks to their experts, audits them, streams events."""

from typing import Protocol

from pydantic import BaseModel

from agora.auditor import Auditor
from agora.board import Board, Status, Task
from agora.errors import PermanentError, SchemaValidationError, TransientError
from agora.store import BoardStore

MAX_PHASE_ATTEMPTS = 3  # how many times the auditor may send a task back before it fails


class Event(BaseModel):
    """Something that happened in a run: started, approved, rejected, failed or finished."""

    kind: str
    task: str
    detail: str = ""
    attempt: int = 0


class Expert(Protocol):
    """Anything that turns an input into a validated artifact: an Agent or the Developer."""

    async def run(self, user: str) -> BaseModel: ...


class Orchestrator:
    """Runs the board: delegates each ready task to its expert and audits the result."""

    def __init__(
        self,
        board: Board,
        agents: dict[str, Expert],
        auditor: Auditor | None = None,
        store: BoardStore | None = None,
        run_id: str = "run",
        changes: dict[str, str] | None = None,
    ):
        self.board = board  # store both, like in Agent.__init__
        self.agents = agents
        self.auditor = auditor  # without an auditor every artifact is approved
        self.store = store  # without a store nothing is saved
        self.run_id = run_id
        self.changes = changes or {}  # task -> change asked by the user, added to its input

    def save(self) -> None:
        """Save the board, if there is a store."""
        if self.store is not None:
            self.store.save(self.run_id, self.board)

    async def run(self, request: str):
        """Run the ready tasks in order, yielding an event for every step.

        Each task receives the artifacts of its dependencies; the first one, the user's request.
        The run stops when no task is ready or when a task fails.
        """
        while True:
            ready = self.board.ready()
            if not ready:
                break  # nothing left to start: the run is over
            for task in ready:
                if task.status == Status.INVALIDATED:
                    task.move_to(Status.PENDING)  # back in the queue after a change
                    task.attempts = 0  # a change opens a new round of attempts
                task.move_to(Status.RUNNING)
                self.save()
                yield Event(kind="started", task=task.name, attempt=task.attempts)

                if task.depends_on:
                    user = "\n\n".join(self.board.tasks[dep].artifact for dep in task.depends_on)
                else:
                    user = request  # the first task receives the user's request
                if task.name in self.changes:
                    user += "\n\nChange requested by the user:\n" + self.changes[task.name]

                async for event in self.run_task(task, user):
                    yield event
                if task.status == Status.FAILED:
                    return  # stop the whole run

        yield Event(kind="finished", task="")

    async def run_task(self, task: Task, user: str):
        """Run one task until the auditor approves it or its attempts run out."""
        feedback = ""
        while True:
            try:
                # find the agent by the task name and run it
                artifact = await self.agents[task.name].run(user + feedback)
            except (SchemaValidationError, TransientError, PermanentError) as error:
                # The agent gave up, or the model kept failing after its own retries.
                task.move_to(Status.FAILED)
                self.save()
                yield Event(kind="failed", task=task.name, detail=str(error), attempt=task.attempts)
                return

            task.artifact = artifact.model_dump_json()
            task.move_to(Status.IN_AUDIT)
            self.save()

            if self.auditor is None:
                task.move_to(Status.APPROVED)
                self.save()
                yield Event(kind="approved", task=task.name, attempt=task.attempts)
                return

            verdict = self.auditor.review(task.name, artifact, self.board)
            if verdict.approved:
                task.move_to(Status.APPROVED)
                self.save()
                yield Event(kind="approved", task=task.name, attempt=task.attempts)
                return

            yield Event(
                kind="rejected", task=task.name, detail=verdict.summary(), attempt=task.attempts
            )
            if task.attempts >= MAX_PHASE_ATTEMPTS:
                task.move_to(Status.FAILED)
                self.save()
                yield Event(
                    kind="failed",
                    task=task.name,
                    detail=f"Rejected by the auditor {task.attempts} times",
                    attempt=task.attempts,
                )
                return

            # Same task again, now with the verdict: the agent learns what to fix.
            task.move_to(Status.RUNNING)
            self.save()
            feedback = "\n\nThe auditor rejected your previous answer:\n" + verdict.summary()
            yield Event(kind="started", task=task.name, attempt=task.attempts)
