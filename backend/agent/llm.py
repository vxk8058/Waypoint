"""Lazy NVIDIA models and bounded, validated decision output."""
from typing import Literal, TypeVar

from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError

from ..config import Settings

Decision = TypeVar("Decision", bound=BaseModel)


def get_llm(role: Literal["planner", "worker"], thinking: bool = True):
    if role not in ("planner", "worker"):
        raise ValueError("Model role must be planner or worker")
    settings = Settings.load()
    model = settings.planner_model if role == "planner" else settings.worker_model
    if not settings.nvidia_api_key or not model:
        raise RuntimeError(f"Set NVIDIA_API_KEY and {role.upper()}_MODEL before running the agent")

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    if thinking:
        return ChatNVIDIA(model=model, api_key=settings.nvidia_api_key, temperature=0)
    # Sent with every request, including structured-output ones (a with_thinking_mode binding is lost there).
    return ChatNVIDIA(model=model, api_key=settings.nvidia_api_key, temperature=0,
                      model_kwargs={"chat_template_kwargs": {"enable_thinking": False}})


def structured(model, schema: type[Decision], prompt: str, retries: int = 2) -> Decision:
    if not isinstance(retries, int) or isinstance(retries, bool) or not 0 <= retries <= 2:
        raise ValueError("retries must be an integer between 0 and 2")
    runner = model.with_structured_output(schema)
    for attempt in range(retries + 1):
        try:
            return schema.model_validate(runner.invoke(prompt))
        except (ValidationError, OutputParserException):
            # Do not echo provider output or financial data into retry errors.
            if attempt < retries:
                prompt += "\nReturn a non-empty object matching the requested schema."
    raise RuntimeError(f"Structured output failed for {schema.__name__} after {retries + 1} attempts")
