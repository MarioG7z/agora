import re

from agora.agent import Agent
from agora.contracts import CodeDraft, ExecutedTest, Implementation
from agora.workspace import Workspace

# Makes the generated project its own pytest root, so the tests of AGORA are never collected,
# and lets the generated tests import the generated code (for example `from app.main import ...`).
PYTEST_INI = "[pytest]\npythonpath = .\n"

# A summary line of `pytest -rA`, for a test named after its Spec id: test_t2_... -> T-2.
RESULT_LINE = re.compile(r"^(PASSED|FAILED|ERROR) \S+::test_t(\d+)\w*")

# Any summary line of `pytest -rA`; group 1 is the test name, the part after the last "::".
ANY_RESULT_LINE = re.compile(r"^(?:PASSED|FAILED) \S+::(\w+)")
SPEC_ID_NAME = re.compile(r"test_t\d+")  # a name that carries its Spec id, like test_t2_...


def parse_results(output: str) -> list[ExecutedTest]:
    tail = output[-2000:]  # the end of the output carries the tracebacks of the failures
    results = []
    for line in output.splitlines():
        match = RESULT_LINE.match(line)
        if match:
            status, number = match.groups()
            passed = status == "PASSED"
            results.append(
                ExecutedTest(test_id=f"T-{number}", passed=passed, output=line if passed else tail)
            )
    return results


def error_lines(output: str) -> list[str]:
    """The distinct `E ...` lines of pytest, e.g. "E   ModuleNotFoundError: No module named 'x'"."""
    lines = []
    for line in output.splitlines():
        if line.startswith("E ") and line.strip() not in lines:
            lines.append(line.strip())
    return lines[:5]


def unnamed_tests(output: str) -> list[str]:
    """Names of the tests that ran without their Spec id, e.g. test_get_all."""
    names = []
    for line in output.splitlines():
        match = ANY_RESULT_LINE.match(line)
        if match:
            name = match.group(1)
            if not SPEC_ID_NAME.match(name):
                names.append(name)
    return names[:10]


class Developer:
    """The Implementation expert: the model writes the code, the code measures it."""

    def __init__(self, agent: Agent, workspace: Workspace):
        self.agent = agent
        self.workspace = workspace
        self.last_draft: CodeDraft | None = None  # the code of the previous attempt, if any

    async def run(self, user: str) -> Implementation:
        if self.last_draft is not None:
            user = user + "\n\nYour previous code was:\n" + self.last_draft.model_dump_json()
        draft = await self.agent.run(user)
        self.last_draft = draft
        assert isinstance(draft, CodeDraft)
        self.workspace.write_file("pytest.ini", PYTEST_INI)
        for file in draft.files:
            self.workspace.write_file(file.path, file.content)
        run = await self.workspace.run_pytest()
        return Implementation(
            files=[file.path for file in draft.files],
            test_results=parse_results(run.output),
            pytest_errors=error_lines(run.output),
            unnamed_tests=unnamed_tests(run.output),
        )
