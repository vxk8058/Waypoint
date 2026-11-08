"""Shared agent contracts; retrieved facts are supplied by code, not the model."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Product = Literal["checking", "savings", "credit_card", "loans"]
Unit = Literal["dollars", "days", "months", "percent", "count"]
_RESERVED = {"min", "max", "round", "ceil", "floor", "abs", "days_until", "months_until"}  # calc.py functions


class ProductEvaluation(BaseModel):
    """Worker output only; excludes trusted product identity, data, and errors."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, strict=True)


class ProductResult(ProductEvaluation):
    """Assembled by subgraph code using an evaluation and the original source data."""

    product: Product | Literal["other_data"]
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    """An empty product list means no match; the router must not guess a product."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    products: list[Product]
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_products(self):
        if len(self.products) != len(set(self.products)):
            raise ValueError("Route products must be unique")
        return self


class Calculation(BaseModel):
    """A formula the planner wants computed; backend.agent.calc runs it against trusted facts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    unit: Unit
    formula: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def not_a_function_name(self):
        if self.name in _RESERVED:
            raise ValueError(f"Calculation name {self.name!r} is reserved")
        return self


class VerifyDecision(BaseModel):
    """Incomplete with no fetch targets means stop with a caveat/clarification."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    done: bool = Field(strict=True)
    need_products: list[Product] = Field(default_factory=list)
    need_other_data: bool = Field(default=False, strict=True)
    missing: str = ""
    calculations: list[Calculation] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def consistent_decision(self):
        if len(self.need_products) != len(set(self.need_products)):
            raise ValueError("Requested products must be unique")
        if len({c.name for c in self.calculations}) != len(self.calculations):
            raise ValueError("Calculation names must be unique")
        if self.done and (self.need_products or self.need_other_data or self.missing or self.calculations):
            raise ValueError("A completed decision cannot request or report missing data")
        if self.calculations and (self.need_products or self.need_other_data):
            raise ValueError("Fetch data first; request calculations in the next round")
        if not self.done and not self.missing:
            raise ValueError("An incomplete decision must explain what is missing")
        return self
