from pathlib import Path

from pydantic import BaseModel

from agora.board import Board
from agora.contracts import PRD, Implementation, ResearchBrief, Spec

FORBIDDEN_IMPORTS = ["subprocess", "os.system", "shutil.rmtree"]


class RuleResult(BaseModel):
    rule: str
    passed: bool
    evidence: str = ""
    blocking: bool = True  # only blocking failures send the task back


class Verdict(BaseModel):
    task: str
    results: list[RuleResult]

    @property
    def approved(self) -> bool:
        return all(result.passed for result in self.results if result.blocking)

    def summary(self) -> str:
        failed = [result for result in self.results if not result.passed]
        if not failed:
            return "All rules passed."
        return "\n".join(f"- {result.rule}: {result.evidence}" for result in failed)


def check(rule: str, problems: list[str] | set[str], blocking: bool = True) -> RuleResult:
    """A rule passes when it found no problems; the problems are its evidence."""
    return RuleResult(
        rule=rule,
        passed=not problems,
        evidence=", ".join(sorted(problems)),
        blocking=blocking,
    )


def duplicates(ids: list[str]) -> set[str]:
    return {item for item in ids if ids.count(item) > 1}


def check_research(brief: ResearchBrief) -> list[RuleResult]:
    ask_ids = [ask.id for ask in brief.asks]
    return [
        check("There is at least one ASK", [] if ask_ids else ["no asks"]),
        check("ASK ids are unique", duplicates(ask_ids)),
    ]


def check_prd(prd: PRD, brief: ResearchBrief) -> list[RuleResult]:
    asks = {ask.id for ask in brief.asks}
    covered = {ask for req in prd.requirements for ask in req.covers}
    without_criteria = [req.id for req in prd.requirements if not req.acceptance_criteria]
    return [
        check("Every ASK is covered by a REQ", asks - covered),
        check("Every REQ covers an existing ASK", covered - asks),
        check("Every REQ has acceptance criteria", without_criteria),
        check("REQ ids are unique", duplicates([req.id for req in prd.requirements])),
    ]


def check_spec(spec: Spec, prd: PRD) -> list[RuleResult]:
    reqs = {req.id for req in prd.requirements}
    by_interface = {req for interface in spec.interfaces for req in interface.covers}
    by_test = {req for test in spec.tests for req in test.covers}
    paths = [file.path for file in spec.files]
    unsafe = [path for path in paths if path.startswith(("/", "\\")) or ".." in path]
    not_python = [path for path in paths if not path.endswith(".py")]
    test_files = [path for path in paths if path.startswith("tests/")]
    no_test_file = ["no file under tests/"] if spec.tests and not test_files else []
    return [
        check("Every REQ is covered by an interface", reqs - by_interface),
        check("Every REQ is covered by a test", reqs - by_test),
        check("Every covered id exists in the PRD", (by_interface | by_test) - reqs),
        check("File paths stay inside the workspace", unsafe),
        check("File paths are unique", duplicates(paths)),
        check("Every file is Python", not_python),
        check("Planned tests have a test file", no_test_file),
    ]


def check_implementation(
    implementation: Implementation, spec: Spec, workspace_root: Path | None
) -> list[RuleResult]:
    results_by_id = {result.test_id: result for result in implementation.test_results}
    missing_files = {file.path for file in spec.files} - set(implementation.files)
    missing_tests = [test.id for test in spec.tests if test.id not in results_by_id]
    failed_tests = [test_id for test_id, result in results_by_id.items() if not result.passed]
    rules = [
        check("Every file in the Spec was written", missing_files),
        check("Every test in the Spec was run", missing_tests),
        check("Every test passes", failed_tests),
        # Without the reason (an import error, a syntax error) the developer cannot fix it.
        check("pytest reports no errors", implementation.pytest_errors),
        check(
            "Every test is named after its Spec id (test_t1_..., test_t2_...)",
            implementation.unnamed_tests,
            blocking=False,
        ),
    ]
    if workspace_root is not None:
        forbidden = []
        for path in implementation.files:
            text = (workspace_root / path).read_text(encoding="utf-8")
            forbidden += [f"{path} uses {name}" for name in FORBIDDEN_IMPORTS if name in text]
        rules.append(check("No forbidden modules", forbidden))
    return rules


class Auditor:
    """Reviews each artifact against the artifact it came from, with rules written in code."""

    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = workspace_root

    def review(self, task_name: str, artifact: BaseModel, board: Board) -> Verdict:
        if isinstance(artifact, ResearchBrief):
            results = check_research(artifact)
        elif isinstance(artifact, PRD):
            results = check_prd(artifact, self._input(board, task_name, ResearchBrief))
        elif isinstance(artifact, Spec):
            results = check_spec(artifact, self._input(board, task_name, PRD))
        elif isinstance(artifact, Implementation):
            spec = self._input(board, task_name, Spec)
            results = check_implementation(artifact, spec, self.workspace_root)
        else:
            results = []  # an artifact without rules passes
        return Verdict(task=task_name, results=results)

    @staticmethod
    def _input(board: Board, task_name: str, schema: type[BaseModel]):
        """The artifact this task received as input: the one of its dependency."""
        dependency = board.tasks[task_name].depends_on[0]
        return schema.model_validate_json(board.tasks[dependency].artifact)
