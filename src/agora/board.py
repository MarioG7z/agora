from enum import StrEnum

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
    def __init__(self, name: str):
        self.name = name
        self.status = Status.PENDING

    def move_to(self, new_status: Status) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(f"{self.name}: {self.status} -> {new_status}")
        self.status = new_status
