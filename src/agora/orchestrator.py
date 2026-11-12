from pydantic import BaseModel

from agora.agent import Agent
from agora.board import Board, Status
from agora.errors import SchemaValidationError


class Event(BaseModel):
    kind: str
    task: str
    detail: str = ""


class Orchestrator:
    def __init__(self, board: Board, agents: dict[str, Agent]):
        self.board = board  # store both, like in Agent.__init__
        self.agents = agents

    async def run(self, request: str):
        while True:
            ready = self.board.ready()
            if not ready:
                break  # nothing left to start: the run is over
            for task in ready:
                task.move_to(Status.RUNNING)
                yield Event(kind="started", task=task.name)

                if task.depends_on:
                    user = "\n\n".join(self.board.tasks[dep].artifact for dep in task.depends_on)
                else:
                    user = request  # the first task receives the user's request

                try:
                    # find the agent by the task name and run it
                    artifact = await self.agents[task.name].run(user)
                except SchemaValidationError as error:
                    task.move_to(Status.FAILED)
                    yield Event(kind="failed", task=task.name, detail=str(error))
                    return  # stop the whole run

                task.artifact = artifact.model_dump_json()
                task.move_to(Status.IN_AUDIT)
                task.move_to(Status.APPROVED)  # in B5 the auditor decides here
                yield Event(kind="approved", task=task.name)

        yield Event(kind="finished", task="")
