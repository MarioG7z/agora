import pytest

from agora.llm import FakeModel


@pytest.mark.asyncio
async def test_fake_model_returns_responses_in_order():
    model = FakeModel(["Uno", "Dos"])

    first = await model.complete("system", "user")
    second = await model.complete("system", "user")

    assert first == "Uno"
    assert second == "Dos"
