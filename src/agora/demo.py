"""A complete run with scripted model answers: no tokens, always the same story.

The PRD agent first forgets ASK-2, so the auditor rejects it and the second attempt passes.
"""

from agora.agent import Agent
from agora.board import Board, Task
from agora.contracts import (
    PRD,
    Ask,
    CodeDraft,
    CodeFile,
    Finding,
    Interface,
    PlannedFile,
    PlannedTest,
    Requirement,
    ResearchBrief,
    Spec,
)
from agora.developer import Developer
from agora.llm import FakeModel, ModelClient
from agora.orchestrator import Expert
from agora.prompts import system_prompt
from agora.workspace import Workspace

BRIEF = ResearchBrief(
    problem="Consultar un inventario de productos",
    asks=[
        Ask(id="ASK-1", description="Listar todos los productos"),
        Ask(id="ASK-2", description="Filtrar productos por categoria"),
    ],
    findings=[
        Finding(
            claim="Una lista en memoria basta para un inventario de ejemplo",
            source="https://docs.python.org/3/tutorial/datastructures.html",
        )
    ],
)

REQ_1 = Requirement(
    id="REQ-1",
    description="Se pueden listar todos los productos",
    acceptance_criteria=["list_products() devuelve todos los productos"],
    covers=["ASK-1"],
)
REQ_2 = Requirement(
    id="REQ-2",
    description="Se pueden filtrar los productos por categoria",
    acceptance_criteria=[
        "list_products('bebidas') devuelve solo bebidas",
        "Una categoria inexistente devuelve una lista vacia",
    ],
    covers=["ASK-2"],
)
PRD_MISSING_ASK_2 = PRD(requirements=[REQ_1])
PRD_COMPLETE = PRD(requirements=[REQ_1, REQ_2])

SPEC = Spec(
    interfaces=[Interface(name="list_products(category=None)", covers=["REQ-1", "REQ-2"])],
    files=[
        PlannedFile(path="app/__init__.py", purpose="Marks app as a package"),
        PlannedFile(path="app/main.py", purpose="Inventory data and list_products"),
        PlannedFile(path="tests/test_main.py", purpose="Tests T-1 and T-2"),
    ],
    tests=[
        PlannedTest(id="T-1", description="Lists every product", covers=["REQ-1"]),
        PlannedTest(id="T-2", description="Filters by category", covers=["REQ-2"]),
    ],
)

MAIN_PY = """PRODUCTS = [
    {"name": "agua", "category": "bebidas"},
    {"name": "cafe", "category": "bebidas"},
    {"name": "pan", "category": "panaderia"},
]


def list_products(category=None):
    if category is None:
        return PRODUCTS
    return [product for product in PRODUCTS if product["category"] == category]
"""

TEST_MAIN_PY = """from app.main import PRODUCTS, list_products


def test_t1_lists_all_products():
    assert list_products() == PRODUCTS


def test_t2_filters_by_category():
    assert [p["name"] for p in list_products("bebidas")] == ["agua", "cafe"]
    assert list_products("ropa") == []
"""

CODE = CodeDraft(
    files=[
        CodeFile(path="app/__init__.py", content=""),
        CodeFile(path="app/main.py", content=MAIN_PY),
        CodeFile(path="tests/test_main.py", content=TEST_MAIN_PY),
    ]
)

DEMO_REQUEST = "Una API para consultar un inventario de productos y filtrarlos por categoria"


def make_board() -> Board:
    return Board(
        [
            Task("research"),
            Task("prd", ["research"]),
            Task("spec", ["prd"]),
            Task("implementation", ["spec"]),
        ]
    )


def make_agents(models: dict[str, ModelClient], workspace: Workspace) -> dict[str, Expert]:
    """The four experts. The same function serves the scripted demo and a real model."""
    return {
        "research": Agent(
            "research", models["research"], system_prompt("research", ResearchBrief), ResearchBrief
        ),
        "prd": Agent("prd", models["prd"], system_prompt("prd", PRD), PRD),
        "spec": Agent("spec", models["spec"], system_prompt("spec", Spec), Spec),
        "implementation": Developer(
            Agent(
                "implementation",
                models["implementation"],
                system_prompt("implementation", CodeDraft),
                CodeDraft,
            ),
            workspace,
        ),
    }


def demo_models() -> dict[str, ModelClient]:
    return {
        "research": FakeModel([BRIEF.model_dump_json()]),
        "prd": FakeModel([PRD_MISSING_ASK_2.model_dump_json(), PRD_COMPLETE.model_dump_json()]),
        "spec": FakeModel([SPEC.model_dump_json()]),
        "implementation": FakeModel([CODE.model_dump_json()]),
    }
