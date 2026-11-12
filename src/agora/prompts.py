import json

from pydantic import BaseModel

ROLES = {
    "research": (
        "You are the researcher of a software team. Read the user's request and turn it into "
        "a research brief: the problem in one sentence, each thing the user asks for as an ASK "
        "with ids ASK-1, ASK-2, ..., and the findings that support the work, each with its source. "
        "An ASK is only something the user explicitly asked for, in a few words: never a research "
        "question and never a feature the user did not request."
    ),
    "prd": (
        "You are the product manager. From the research brief, write the requirements: ids "
        "REQ-1, REQ-2, ..., each with acceptance criteria that a test can check, and in `covers` "
        "the ASK ids it answers. Every ASK must be covered by at least one requirement."
    ),
    "spec": (
        "You are the tech lead. From the PRD, write the technical spec: the interfaces, the "
        "files (relative paths, code under app/ and tests under tests/) and the planned tests "
        "with ids T-1, T-2, .... Every REQ must be covered by an interface and by a test."
    ),
    "implementation": (
        "You are the developer. From the spec, write every file with its full content, in plain "
        "Python without external packages. Name each test function after its Spec id, for "
        "example `test_t1_lists_all_products` for T-1, so its result can be traced."
    ),
}


def shape(schema: type[BaseModel]) -> dict:
    """The shape of an answer, e.g. {"asks": [{"id": "string"}]}, without JSON Schema keywords.

    Small models sometimes copy a JSON Schema ($defs, properties, type) instead of filling it;
    a plain shape is easier to follow.
    """
    json_schema = schema.model_json_schema()
    definitions = json_schema.get("$defs", {})

    def walk(node: dict):
        if "$ref" in node:  # "#/$defs/Ask" -> the definition of Ask
            return walk(definitions[node["$ref"].split("/")[-1]])
        if node.get("type") == "object":
            return {name: walk(field) for name, field in node["properties"].items()}
        if node.get("type") == "array":
            return [walk(node["items"])]
        return node.get("type", "value")  # "string", "boolean", "integer"

    return walk(json_schema)


def system_prompt(role: str, schema: type[BaseModel]) -> str:
    return (
        f"{ROLES[role]}\n\n"
        f"Answer only with one JSON object with this shape, filled with your content, "
        f"without markdown:\n{json.dumps(shape(schema))}"
    )
