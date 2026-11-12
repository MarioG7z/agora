from pydantic import BaseModel


class Ask(BaseModel):
    id: str
    description: str


class Finding(BaseModel):
    claim: str
    source: str


class ResearchBrief(BaseModel):
    problem: str
    asks: list[Ask]
    findings: list[Finding]


class Requirement(BaseModel):
    id: str
    description: str
    acceptance_criteria: list[str]
    covers: list[str]


class PRD(BaseModel):
    requirements: list[Requirement]


class Interface(BaseModel):
    name: str
    covers: list[str]


class PlannedFile(BaseModel):
    path: str
    purpose: str


class PlannedTest(BaseModel):
    id: str
    description: str
    covers: list[str]


class Spec(BaseModel):
    interfaces: list[Interface]
    files: list[PlannedFile]
    tests: list[PlannedTest]


class ExecutedTest(BaseModel):
    test_id: str
    passed: bool
    output: str


class CodeFile(BaseModel):
    path: str
    content: str


class CodeDraft(BaseModel):
    # What the developer model writes. The Implementation is built by code from it,
    # because test results must be measured, not reported by the model.
    files: list[CodeFile]


class Implementation(BaseModel):
    files: list[str]
    test_results: list[ExecutedTest]
