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
