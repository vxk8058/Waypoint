"""The planner's small presentation plan; it picks datasets/facts by key and never supplies numbers."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChartChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset: str | None = None
    facts: list[str] = Field(default_factory=list, max_length=4)  # 2-4 same-unit facts compared as bars
    title: str = Field(min_length=1)
    subtitle: str | None = None
    caption: str | None = None  # one sentence under the chart saying what to notice
    orientation: Literal["vertical", "horizontal"] = "vertical"
    layout: Literal["grouped", "stacked", "percent"] = "grouped"
    sort: Literal["none", "asc", "desc"] = "none"
    value_labels: Literal["auto", "none", "all", "max", "min-max", "last", "totals"] = "auto"
    highlight: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.dataset) == bool(self.facts):
            raise ValueError("A chart uses either one dataset or 2-4 facts")
        if self.facts and len(self.facts) < 2:
            raise ValueError("A fact comparison needs at least two facts")
        return self


class UIPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    stats: list[str] = Field(default_factory=list, max_length=4)
    charts: list[ChartChoice] = Field(default_factory=list, max_length=3)
