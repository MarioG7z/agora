"""The artifacts the agents exchange, one Pydantic model per phase."""

from pydantic import BaseModel


class Ask(BaseModel):
    """One thing the user explicitly asked for (ASK-1, ASK-2, ...)."""

    id: str
    description: str


class Finding(BaseModel):
    """A fact that supports the work, with its source."""

    claim: str
    source: str


class ResearchBrief(BaseModel):
    """Planning artifact: the problem, the user's asks and the findings."""

    problem: str
    asks: list[Ask]
    findings: list[Finding]


class Requirement(BaseModel):
    """A requirement (REQ-n) with testable acceptance criteria and the ASKs it covers."""

    id: str
    description: str
    acceptance_criteria: list[str]
    covers: list[str]


class PRD(BaseModel):
    """PRD artifact: the requirements."""

    requirements: list[Requirement]


class Interface(BaseModel):
    """A function or endpoint planned in the Spec and the REQs it covers."""

    name: str
    covers: list[str]


class PlannedFile(BaseModel):
    """A file the Spec plans and what it is for."""

    path: str
    purpose: str


class PlannedTest(BaseModel):
    """A test planned in the Spec (T-n) and the REQs it covers."""

    id: str
    description: str
    covers: list[str]


class Spec(BaseModel):
    """Spec artifact: interfaces, files and planned tests."""

    interfaces: list[Interface]
    files: list[PlannedFile]
    tests: list[PlannedTest]


class ExecutedTest(BaseModel):
    """The measured result of one planned test, linked by its id."""

    test_id: str
    passed: bool
    output: str


class CodeFile(BaseModel):
    """One generated file with its full content."""

    path: str
    content: str


class CodeDraft(BaseModel):
    """What the developer model writes. The Implementation is built by code from it,
    because test results must be measured, not reported by the model.
    """

    files: list[CodeFile]


class Implementation(BaseModel):
    """Implementation artifact, built by code from the pytest run."""

    files: list[str]
    test_results: list[ExecutedTest]
    pytest_errors: list[str] = []  # error lines when pytest could not even run the tests
    unnamed_tests: list[str] = []  # tests that ran without the Spec id in their name
