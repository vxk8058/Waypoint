from unittest.mock import Mock, patch

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field

from backend.agent.llm import get_llm, structured
from backend.config import Settings


class Decision(BaseModel):
    confidence: float = Field(ge=0, le=1)


@pytest.fixture
def model_env(monkeypatch):
    for name in ("NVIDIA_API_KEY", "PLANNER_MODEL", "WORKER_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("role", ["planner", "worker"])
def test_model_configuration_is_lazy_and_requires_credentials(model_env, monkeypatch, role):
    with patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as factory:
        with pytest.raises(RuntimeError, match=role.upper() + "_MODEL"):
            get_llm(role)
        factory.assert_not_called()
        monkeypatch.setenv("NVIDIA_API_KEY", "test-secret")
        monkeypatch.setenv(role.upper() + "_MODEL", "  test-model  ")
        assert get_llm(role) is factory.return_value
        factory.assert_called_once_with(model="test-model", api_key="test-secret", temperature=0)
        assert "test-secret" not in repr(Settings.load())


def test_invalid_role():
    with pytest.raises(ValueError, match="role"):
        get_llm("unknown")


@pytest.mark.parametrize("response", [{"confidence": 0.8}, Decision(confidence=0.8)])
def test_valid_structured_output(response):
    model = Mock()
    runner = model.with_structured_output.return_value
    runner.invoke.return_value = response
    assert structured(model, Decision, "Evaluate").confidence == 0.8
    model.with_structured_output.assert_called_once_with(Decision)
    runner.invoke.assert_called_once_with("Evaluate")


@pytest.mark.parametrize("bad", [None, {"confidence": 2}, OutputParserException("private output")])
def test_retries_invalid_or_empty_output(bad):
    model = Mock()
    runner = model.with_structured_output.return_value
    runner.invoke.side_effect = [bad, {"confidence": 0.5}]
    assert structured(model, Decision, "Evaluate").confidence == 0.5
    assert runner.invoke.call_count == 2
    assert "private output" not in runner.invoke.call_args.args[0]


@pytest.mark.parametrize("retries", [0, 2])
def test_retry_exhaustion_is_bounded(retries):
    model = Mock()
    runner = model.with_structured_output.return_value
    runner.invoke.return_value = None
    with pytest.raises(RuntimeError, match=f"after {retries + 1} attempts"):
        structured(model, Decision, "Evaluate", retries=retries)
    assert runner.invoke.call_count == retries + 1


@pytest.mark.parametrize("retries", [-1, 3, True, 1.5])
def test_invalid_retry_limit(retries):
    model = Mock()
    with pytest.raises(ValueError, match="retries"):
        structured(model, Decision, "Evaluate", retries=retries)
    model.with_structured_output.assert_not_called()


def test_provider_failure_is_not_retried_as_invalid_output():
    model = Mock()
    runner = model.with_structured_output.return_value
    runner.invoke.side_effect = ConnectionError("unavailable")
    with pytest.raises(ConnectionError):
        structured(model, Decision, "Evaluate")
    runner.invoke.assert_called_once()


def test_thinking_can_be_turned_off_for_every_request(model_env, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-secret")
    monkeypatch.setenv("PLANNER_MODEL", "test-model")
    with patch("langchain_nvidia_ai_endpoints.ChatNVIDIA") as factory:
        get_llm("planner", thinking=False)
    factory.assert_called_once_with(model="test-model", api_key="test-secret", temperature=0,
                                    model_kwargs={"chat_template_kwargs": {"enable_thinking": False}})
