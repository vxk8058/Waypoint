"""The planner's small presentation plan; it picks datasets/facts by key and never supplies numbers."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChartChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset: str
    title: str = Field(min_length=1)
    subtitle: str | None = None
    caption: str | None = None  # one sentence under the chart saying what to notice
    orientation: Literal["vertical", "horizontal"] = "vertical"
    layout: Literal["grouped", "stacked", "percent"] = "grouped"
    sort: Literal["none", "asc", "desc"] = "none"
    value_labels: Literal["auto", "none", "all", "max", "min-max", "last", "totals"] = "auto"
    highlight: list[str] = Field(default_factory=list)


class UIPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    stats: list[str] = Field(default_factory=list, max_length=4)
    charts: list[ChartChoice] = Field(default_factory=list, max_length=3)
