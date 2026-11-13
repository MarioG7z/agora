import pytest

from agora.errors import PermanentError
from agora.workspace import Workspace, read_file


def test_write_file_creates_file_inside_workspace(tmp_path):
    workspace = Workspace(tmp_path / "workspace")

    written = workspace.write_file("app/main.py", "print('hola')")

    assert written == (tmp_path / "workspace" / "app" / "main.py").resolve()
    assert written.read_text(encoding="utf-8") == "print('hola')"


def test_write_file_rejects_parent_directory_escape(tmp_path):
    workspace = Workspace(tmp_path / "workspace")

    with pytest.raises(PermanentError):
        workspace.write_file("../outside.py", "x = 1")
    assert not (tmp_path / "outside.py").exists()


def test_write_file_rejects_absolute_path(tmp_path):
    workspace = Workspace(tmp_path / "workspace")
    outside = tmp_path / "elsewhere" / "outside.py"

    with pytest.raises(PermanentError):
        workspace.write_file(str(outside), "x = 1")
    assert not outside.exists()


def test_read_file_returns_content(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("requisitos", encoding="utf-8")

    assert read_file(path) == "requisitos"


def test_read_file_missing_raises_permanent_error(tmp_path):
    with pytest.raises(PermanentError):
        read_file(tmp_path / "missing.txt")


@pytest.mark.asyncio
async def test_run_pytest_reports_passing_tests(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("test_ok.py", "def test_ok():\n    assert 1 + 1 == 2\n")

    run = await workspace.run_pytest()

    assert run.passed
    assert "1 passed" in run.output


@pytest.mark.asyncio
async def test_run_pytest_reports_failing_tests(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("test_bad.py", "def test_bad():\n    assert 1 + 1 == 3\n")

    run = await workspace.run_pytest()

    assert not run.passed
    assert "1 failed" in run.output


@pytest.mark.asyncio
async def test_run_pytest_stops_tests_that_exceed_the_timeout(tmp_path):
    workspace = Workspace(tmp_path)
    workspace.write_file("test_slow.py", "import time\n\ndef test_slow():\n    time.sleep(30)\n")

    run = await workspace.run_pytest(time_limit=2)

    assert not run.passed
    assert "stopped after 2 seconds" in run.output
