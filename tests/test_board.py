import pytest

from agora.board import Status, Task
from agora.errors import InvalidTransition


def test_new_task_starts_pending():
    task = Task("prd")

    assert task.status == Status.PENDING


def test_task_change_status():
    task = Task("spec")

    task.move_to(Status.RUNNING)

    assert task.status == Status.RUNNING


def test_task_reject_status():
    task = Task("planning")

    with pytest.raises(InvalidTransition, match="planning"):
        task.move_to(Status.APPROVED)

    assert task.status == Status.PENDING
