import json

from pydantic import BaseModel

ROLES = {
    "research": (
        "You are the researcher of a software team. Read the user's request and turn it into "
        "a research brief: the problem in one sentence, each thing the user asks for as an ASK "
        "with ids ASK-1, ASK-2, ..., and the findings that support the work, each with its source."
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


def system_prompt(role: str, schema: type[BaseModel]) -> str:
    schema_text = json.dumps(schema.model_json_schema())
    return (
        f"{ROLES[role]}\n\n"
        f"Answer only with one JSON object that follows this JSON schema, without markdown:\n"
        f"{schema_text}"
    )
