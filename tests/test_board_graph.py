import pytest

from agora.board import Board, Status, Task


def make_chain() -> Board:
    # The four phases of AGORA, each one depending on the previous.
    return Board(
        [
            Task("implementation", ["spec"]),
            Task("spec", ["prd"]),
            Task("prd", ["research"]),
            Task("research"),
        ]
    )


def approve(task: Task) -> None:
    task.move_to(Status.RUNNING)
    task.move_to(Status.IN_AUDIT)
    task.move_to(Status.APPROVED)


def test_order_follows_dependencies_not_insertion():
    board = make_chain()

    assert board.order == ["research", "prd", "spec", "implementation"]


def test_unknown_dependency_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        Board([Task("prd", ["research"])])


def test_dependency_cycle_is_rejected():
    with pytest.raises(ValueError, match="cycle"):
        Board([Task("prd", ["spec"]), Task("spec", ["prd"])])


def test_only_tasks_with_approved_dependencies_are_ready():
    board = make_chain()

    assert [task.name for task in board.ready()] == ["research"]

    approve(board.tasks["research"])

    assert [task.name for task in board.ready()] == ["prd"]


def test_running_again_counts_a_new_attempt():
    task = Task("spec")

    task.move_to(Status.RUNNING)
    task.move_to(Status.IN_AUDIT)
    task.move_to(Status.RUNNING)  # the auditor rejected it

    assert task.attempts == 2


def test_change_invalidates_everything_downstream():
    board = make_chain()
    for name in board.order:
        approve(board.tasks[name])

    invalidated = board.invalidate_dependents("prd")

    assert invalidated == ["spec", "implementation"]
    assert board.tasks["research"].status == Status.APPROVED
    assert board.tasks["prd"].status == Status.APPROVED


def test_invalidated_task_is_ready_again_once_its_dependency_is_approved():
    board = make_chain()
    for name in board.order:
        approve(board.tasks[name])
    board.tasks["prd"].move_to(Status.RUNNING)  # the user changes the PRD
    board.invalidate_dependents("prd")

    assert board.ready() == []

    board.tasks["prd"].move_to(Status.IN_AUDIT)
    board.tasks["prd"].move_to(Status.APPROVED)

    assert [task.name for task in board.ready()] == ["spec"]


def test_resume_sends_running_tasks_back_to_pending():
    board = make_chain()
    approve(board.tasks["research"])
    board.tasks["prd"].move_to(Status.RUNNING)  # the process dies here

    resumed = board.resume()

    assert resumed == ["prd"]
    assert board.tasks["prd"].status == Status.PENDING
    assert board.tasks["research"].status == Status.APPROVED
