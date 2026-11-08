"""The planner's presentation plan: an ordered list of blocks that pick facts and datasets by key, never numbers."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BlockType = Literal["heading", "paragraph", "list", "callout", "stats", "divider",
                    "bar_chart", "pie_chart", "line_chart", "histogram"]
CHARTS = {"bar_chart", "pie_chart", "line_chart", "histogram"}


class Stat(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fact: str
    compare_to: str | None = None  # the same measure for an earlier period; code computes the change
    caption: str | None = None  # short context, e.g. "vs. September"


class Block(BaseModel):
    """One block of the answer; validate.block_problems checks the fields its type needs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: BlockType
    beside_previous: bool = False  # show next to the previous block (a row holds two or three)
    text: str | None = None
    level: Literal[1, 2, 3] = 1
    size: Literal["default", "lead", "small"] = "default"
    tone: Literal["default", "muted", "info", "success", "warning", "danger"] = "default"
    title: str | None = None
    subtitle: str | None = None
    items: list[str] = Field(default_factory=list)
    ordered: bool = False
    stats: list[Stat] = Field(default_factory=list)
    dataset: str | None = None
    facts: list[str] = Field(default_factory=list)  # bar_chart: two to four same-unit facts compared as bars
    orientation: Literal["vertical", "horizontal"] = "vertical"
    layout: Literal["grouped", "stacked", "percent"] = "grouped"
    sort: Literal["none", "asc", "desc"] = "none"
    value_labels: Literal["auto", "none", "all", "max", "min-max", "last", "totals"] = "auto"
    highlight: list[str] = Field(default_factory=list)
    markers: list[Literal["mean", "median"]] = Field(default_factory=list)
    extra_monthly: str | None = None  # goal_projection what-if: dollar fact added every month
    lump_sum: str | None = None  # goal_projection what-if: dollar fact added once, next month
    scenario_name: str | None = None

    @model_validator(mode="after")
    def text_in_title(self):
        # Models often put a heading's or paragraph's words in "title"; treat them as the block's text.
        if self.type in ("heading", "paragraph", "callout") and not self.text and self.title:
            self.text, self.title = self.title, None
        return self


class UIPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # maxItems guides the model's constrained decoding (it can loop on repeated blocks); code also caps it.
    blocks: list[Block] = Field(min_length=1, json_schema_extra={"maxItems": 12})

    @model_validator(mode="before")
    @classmethod
    def compact_form(cls, data):
        """{answer, stats, charts} is shorthand for a lead paragraph, a stats block and captioned bar charts."""
        if not isinstance(data, dict) or "blocks" in data:
            return data
        blocks = [{"type": "paragraph", "size": "lead", "text": data["answer"]}] if "answer" in data else []
        if data.get("stats"):
            blocks.append({"type": "stats", "stats": [{"fact": key} for key in data["stats"]]})
        for chart in data.get("charts", []):
            chart = dict(chart)
            caption = chart.pop("caption", None)
            blocks.append({"type": "bar_chart", **chart})
            if caption:
                blocks.append({"type": "paragraph", "text": caption})
        extra = set(data) - {"answer", "stats", "charts"}
        return {"blocks": blocks, **{key: data[key] for key in extra}}  # unknown keys still fail validation
