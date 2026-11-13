import pytest

from agora.agent import Agent
from agora.contracts import CodeDraft
from agora.demo import CODE
from agora.developer import Developer, parse_results
from agora.llm import FakeModel
from agora.workspace import Workspace


def test_parse_results_maps_test_names_to_spec_ids():
    output = (
        "PASSED tests/test_main.py::test_t1_lists_all_products\n"
        "FAILED tests/test_main.py::test_t2_filters_by_category - AssertionError\n"
        "PASSED tests/test_main.py::test_helper_without_id\n"
    )

    results = parse_results(output)

    assert [(result.test_id, result.passed) for result in results] == [
        ("T-1", True),
        ("T-2", False),
    ]


@pytest.mark.asyncio
async def test_developer_writes_the_code_and_measures_its_tests(tmp_path):
    workspace = Workspace(tmp_path)
    agent = Agent("implementation", FakeModel([CODE.model_dump_json()]), "You code.", CodeDraft)

    implementation = await Developer(agent, workspace).run("the spec")

    assert (tmp_path / "app" / "main.py").exists()
    assert [(result.test_id, result.passed) for result in implementation.test_results] == [
        ("T-1", True),
        ("T-2", True),
    ]


@pytest.mark.asyncio
async def test_developer_reports_a_failing_test_with_its_traceback(tmp_path):
    broken = CODE.model_copy(deep=True)
    broken.files[1].content = broken.files[1].content.replace('"bebidas"', '"otra"', 1)
    agent = Agent("implementation", FakeModel([broken.model_dump_json()]), "You code.", CodeDraft)

    implementation = await Developer(agent, Workspace(tmp_path)).run("the spec")

    failed = [result for result in implementation.test_results if not result.passed]
    assert [result.test_id for result in failed] == ["T-2"]
    assert "assert" in failed[0].output


@pytest.mark.asyncio
async def test_developer_reports_why_pytest_could_not_run(tmp_path):
    broken = CODE.model_copy(deep=True)
    broken.files[1].content = "import flask\n" + broken.files[1].content
    agent = Agent("implementation", FakeModel([broken.model_dump_json()]), "You code.", CodeDraft)

    implementation = await Developer(agent, Workspace(tmp_path)).run("the spec")

    assert implementation.test_results == []
    assert any("No module named 'flask'" in line for line in implementation.pytest_errors)


@pytest.mark.asyncio
async def test_second_attempt_sees_the_code_of_the_first(tmp_path):
    model = FakeModel([CODE.model_dump_json(), CODE.model_dump_json()])
    agent = Agent("implementation", model, "You code.", CodeDraft)
    developer = Developer(agent, Workspace(tmp_path))

    await developer.run("the spec")  # attempt 1: there is no previous code yet
    await developer.run("the spec")  # attempt 2: the same developer, a second time

    assert "Your previous code was" not in model.received[0]
    assert "Your previous code was" in model.received[1]
    assert "def list_products" in model.received[1]  # a line from the code of attempt 1
