from agora.board import Board, Status, Task
from agora.store import BoardStore


def make_board() -> Board:
    return Board([Task("research"), Task("prd", ["research"])])


def test_board_survives_a_save_and_load(tmp_path):
    store = BoardStore(tmp_path / "runs.db")
    board = make_board()
    research = board.tasks["research"]
    research.move_to(Status.RUNNING)
    research.artifact = '{"problem": "API de inventario"}'
    research.move_to(Status.IN_AUDIT)
    research.move_to(Status.APPROVED)

    store.save("run-1", board)
    loaded = store.load("run-1")

    assert loaded.tasks["research"].status == Status.APPROVED
    assert loaded.tasks["research"].artifact == '{"problem": "API de inventario"}'
    assert loaded.tasks["research"].attempts == 1
    assert loaded.tasks["prd"].depends_on == ["research"]
    store.close()


def test_a_new_version_is_kept_only_when_the_artifact_changes(tmp_path):
    store = BoardStore(tmp_path / "runs.db")
    board = make_board()
    research = board.tasks["research"]

    research.artifact = '{"v": 1}'
    store.save("run-1", board)
    store.save("run-1", board)  # nothing changed
    research.artifact = '{"v": 2}'
    store.save("run-1", board)

    assert store.versions("run-1", "research") == ['{"v": 1}', '{"v": 2}']
    store.close()


def test_resume_after_a_crash(tmp_path):
    path = tmp_path / "runs.db"
    store = BoardStore(path)
    board = make_board()
    board.tasks["research"].move_to(Status.RUNNING)
    store.save("run-1", board)
    store.close()  # the process dies with research still running

    board = BoardStore(path).load("run-1")
    board.resume()

    assert board.tasks["research"].status == Status.PENDING
    assert [task.name for task in board.ready()] == ["research"]
