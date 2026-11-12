from agora.auditor import Auditor, check_implementation, check_prd, check_research, check_spec
from agora.board import Board, Task
from agora.contracts import (
    PRD,
    Ask,
    ExecutedTest,
    Implementation,
    PlannedFile,
    ResearchBrief,
)
from agora.demo import BRIEF, PRD_COMPLETE, PRD_MISSING_ASK_2, REQ_1, REQ_2, SPEC


def failed_rules(results) -> dict[str, str]:
    return {result.rule: result.evidence for result in results if not result.passed}


def test_research_without_asks_is_rejected():
    brief = ResearchBrief(problem="x", asks=[], findings=[])

    assert "There is at least one ASK" in failed_rules(check_research(brief))


def test_research_with_repeated_ask_ids_is_rejected():
    brief = ResearchBrief(
        problem="x",
        asks=[Ask(id="ASK-1", description="a"), Ask(id="ASK-1", description="b")],
        findings=[],
    )

    assert failed_rules(check_research(brief)) == {"ASK ids are unique": "ASK-1"}


def test_prd_that_forgets_an_ask_is_rejected_with_its_id():
    assert failed_rules(check_prd(PRD_MISSING_ASK_2, BRIEF)) == {
        "Every ASK is covered by a REQ": "ASK-2"
    }


def test_prd_that_points_to_an_unknown_ask_is_rejected():
    dangling = REQ_2.model_copy(update={"covers": ["ASK-9"]})

    failed = failed_rules(check_prd(PRD(requirements=[REQ_1, dangling]), BRIEF))

    assert failed["Every REQ covers an existing ASK"] == "ASK-9"


def test_prd_requirement_without_criteria_is_rejected():
    empty = REQ_2.model_copy(update={"acceptance_criteria": []})

    failed = failed_rules(check_prd(PRD(requirements=[REQ_1, empty]), BRIEF))

    assert failed == {"Every REQ has acceptance criteria": "REQ-2"}


def test_complete_chain_passes_every_rule():
    assert failed_rules(check_research(BRIEF)) == {}
    assert failed_rules(check_prd(PRD_COMPLETE, BRIEF)) == {}
    assert failed_rules(check_spec(SPEC, PRD_COMPLETE)) == {}


def test_spec_without_a_test_for_a_requirement_is_rejected():
    spec = SPEC.model_copy(update={"tests": SPEC.tests[:1]})  # drops T-2, the test of REQ-2

    assert failed_rules(check_spec(spec, PRD_COMPLETE)) == {
        "Every REQ is covered by a test": "REQ-2"
    }


def test_spec_file_outside_the_workspace_is_rejected():
    spec = SPEC.model_copy(
        update={"files": [*SPEC.files, PlannedFile(path="../evil.py", purpose="x")]}
    )

    failed = failed_rules(check_spec(spec, PRD_COMPLETE))

    assert failed == {"File paths stay inside the workspace": "../evil.py"}


def test_implementation_with_a_failing_test_is_rejected():
    implementation = Implementation(
        files=[file.path for file in SPEC.files],
        test_results=[
            ExecutedTest(test_id="T-1", passed=True, output=""),
            ExecutedTest(test_id="T-2", passed=False, output="AssertionError"),
        ],
    )

    failed = failed_rules(check_implementation(implementation, SPEC, None))

    assert failed == {"Every test passes": "T-2"}


def test_implementation_using_subprocess_is_rejected(tmp_path):
    for file in SPEC.files:
        (tmp_path / file.path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / file.path).write_text("", encoding="utf-8")
    (tmp_path / "app/main.py").write_text("import subprocess\n", encoding="utf-8")
    implementation = Implementation(
        files=[file.path for file in SPEC.files],
        test_results=[
            ExecutedTest(test_id="T-1", passed=True, output=""),
            ExecutedTest(test_id="T-2", passed=True, output=""),
        ],
    )

    failed = failed_rules(check_implementation(implementation, SPEC, tmp_path))

    assert failed == {"No forbidden modules": "app/main.py uses subprocess"}


def test_auditor_reviews_an_artifact_against_its_dependency():
    board = Board([Task("research"), Task("prd", ["research"])])
    board.tasks["research"].artifact = BRIEF.model_dump_json()

    verdict = Auditor().review("prd", PRD_MISSING_ASK_2, board)

    assert not verdict.approved
    assert "ASK-2" in verdict.summary()
