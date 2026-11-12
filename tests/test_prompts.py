from agora.contracts import PRD, Implementation, ResearchBrief
from agora.prompts import shape, system_prompt


def test_shape_follows_nested_contracts():
    assert shape(PRD) == {
        "requirements": [
            {
                "id": "string",
                "description": "string",
                "acceptance_criteria": ["string"],
                "covers": ["string"],
            }
        ]
    }


def test_shape_keeps_non_text_types():
    assert shape(Implementation)["test_results"] == [
        {"test_id": "string", "passed": "boolean", "output": "string"}
    ]


def test_prompt_has_no_json_schema_keywords():
    prompt = system_prompt("research", ResearchBrief)

    assert '"asks"' in prompt
    assert "$defs" not in prompt
    assert "properties" not in prompt
