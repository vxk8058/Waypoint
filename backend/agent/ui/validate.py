"""Grounding: model text may state numbers only through {fact_key} placeholders filled by code."""
import re

from .datasets import money
from .plan import UIPlan

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
_DIGIT = re.compile(r"\d")


def has_raw_number(text: str) -> bool:
    return bool(_DIGIT.search(PLACEHOLDER.sub("", text)))


def plan_problems(plan: UIPlan, facts: dict, datasets: dict) -> list[str]:
    problems = [f"Unknown dataset '{c.dataset}'" for c in plan.charts if c.dataset not in datasets]
    problems += [f"Unknown stat '{key}'" for key in plan.stats if key not in facts]
    texts = [plan.answer] + [t for c in plan.charts for t in (c.title, c.subtitle, c.caption) if t]
    for text in texts:
        problems += [f"Unknown fact placeholder '{{{key}}}'" for key in PLACEHOLDER.findall(text) if key not in facts]
        if has_raw_number(text):
            # A typed digit can't be traced to a source record, even when it happens to match one.
            problems.append(f"Write every number as a fact placeholder, not digits: {text!r}")
    return problems


def fill(text: str, facts: dict) -> str:
    return PLACEHOLDER.sub(lambda m: money(facts[m[1]]["value"]), text)
