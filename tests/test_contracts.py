import pytest
from pydantic import ValidationError

from agora.contracts import (
    PRD,
    Ask,
    ExecutedTest,
    Finding,
    Implementation,
    Interface,
    PlannedFile,
    PlannedTest,
    Requirement,
    ResearchBrief,
    Spec,
)


def test_ask_parses_from_json():
    raw_json = (
        '{"id": "ASK-1", "description": "listar productos"}'  # this is text, as an LLM returns it
    )
    ask = Ask.model_validate_json(raw_json)
    assert ask.id == "ASK-1"  # compares against the expected value


def test_finding_parses_from_json():
    raw_json = '{"claim": "FastAPI genera la documentacion de la api automaticamente", "source": "https://fastapi.tiangolo.com/"}'
    finding = Finding.model_validate_json(raw_json)
    assert finding.claim == "FastAPI genera la documentacion de la api automaticamente"


def test_research_parses_from_json():
    raw_json = """
    {
        "problem": "API de inventario",
        "asks": [
            {"id": "ASK-1", "description": "listar productos"},
            {"id": "ASK-2", "description": "filtrar por categoria"}
        ],
        "findings": [
            {
                "claim": "FastAPI genera la documentacion de la api automaticamente",
                "source": "https://fastapi.tiangolo.com/"
            }
        ]
    }
    """
    research = ResearchBrief.model_validate_json(raw_json)
    assert research.asks[1].id == "ASK-2"
    assert len(research.findings) == 1


def test_requirement_parses_from_json():
    raw_json = """
    {
        "id": "REQ-2",
        "description": "La API permite filtrar productos por categoría",
        "acceptance_criteria": [
            "GET /products?category=X devuelve solo productos de la categoría X",
            "Con una categoría inexistente devuelve una lista vacía"
        ],
        "covers": ["ASK-2"]
    }
    """
    requirement = Requirement.model_validate_json(raw_json)
    assert requirement.id == "REQ-2"


def test_prd_without_acceptance_criteria_fails():
    raw_json = """
    {
        "requirements":[
            {
                "id": "REQ-3",
                "description": "La API permite borrar productos",
                "covers": ["ASK-3"]
            }
        ]
    }
    """
    with pytest.raises(ValidationError, match="acceptance_criteria"):
        PRD.model_validate_json(raw_json)


def test_interface_parses_from_json():
    raw_json = '{"name": "GET /products", "covers": ["REQ-1", "REQ-2"]}'
    interface = Interface.model_validate_json(raw_json)
    assert interface.name == "GET /products"


def test_plannedfile_parses_from_json():
    raw_json = '{"path": "app/main.py", "purpose": "Define los endpoints de productos"}'
    plannedfile = PlannedFile.model_validate_json(raw_json)
    assert plannedfile.path == "app/main.py"


def test_plannedtest_parses_from_json():
    raw_json = """
    {
       "id": "T-1",
        "description": "GET /products?category=bebidas devuelve solo bebidas",
        "covers": ["REQ-2"]
    }
    """
    plannedtest = PlannedTest.model_validate_json(raw_json)
    assert plannedtest.id == "T-1"


def test_spec_parses_from_json():
    raw_json = """
    {
        "interfaces": [
            {"name": "GET /products", "covers": ["REQ-1", "REQ-2"]}
        ],
        "files": [
            {"path": "app/main.py", "purpose": "Define los endpoints de productos"}
        ],
        "tests": [
            {
                "id": "T-1",
                "description": "GET /products?category=bebidas devuelve solo bebidas",
                  "covers": ["REQ-2"]
            }
        ]
    }
    """
    spec = Spec.model_validate_json(raw_json)
    assert spec.interfaces[0].name == "GET /products"


def test_executedtest_parses_from_json():
    raw_json = '{"test_id": "T-1", "passed": true, "output": "1 passed"}'
    executedtest = ExecutedTest.model_validate_json(raw_json)
    assert executedtest.test_id == "T-1"


def test_implementation_parses_from_json():
    raw_json = """
    {
        "files": ["app/main.py", "tests/test_products.py"],
        "test_results": [
            {"test_id": "T-1", "passed": true, "output": "1 passed"}
        ]
    }
    """
    implementation = Implementation.model_validate_json(raw_json)
    assert len(implementation.files) == 2
