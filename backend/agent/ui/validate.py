"""Grounding: model text may state numbers only through {fact_key} placeholders filled by code."""
import re

from ..calc import normalize, question_numbers
from .datasets import fmt
from .plan import Block, UIPlan

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
_UNIT_AFTER = re.compile(r"(\{([^{}]+)\}\**)\s*(days?|weeks?|months?|years?)\b", re.IGNORECASE)


def _repeats_unit(fact: dict, word: str) -> bool:
    return fact["unit"] in ("days", "months") and word.lower().rstrip("s") == fact["unit"].rstrip("s")
_DIGIT = re.compile(r"\d")


def has_raw_number(text: str, question: str = "") -> bool:
    """True if the text types a number that is neither a placeholder nor one the user wrote in the question."""
    text = PLACEHOLDER.sub("", text)
    allowed = question_numbers(question)
    return any(float(n.replace(",", "")) not in allowed for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text))


def plan_problems(plan: UIPlan, facts: dict, datasets: dict, question: str = "") -> list[str]:
    return [problem for block in plan.blocks for problem in block_problems(block, facts, datasets, question)]


# Which dataset kinds each chart type can draw.
_KINDS = {"bar_chart": ("category", "time"), "pie_chart": ("category",), "line_chart": ("time", "projection"),
          "histogram": ("sizes",)}


def block_problems(block: Block, facts: dict, datasets: dict, question: str = "") -> list[str]:
    problems = []
    texts = [block.text, block.title, block.subtitle, block.scenario_name, *block.items,
             *(stat.caption for stat in block.stats)]
    for text in (normalize(t, facts, ()) for t in texts if t):  # bare fact keys count as placeholders
        problems += [f"Unknown fact placeholder '{{{key}}}'" for key in PLACEHOLDER.findall(text) if key not in facts]
        if has_raw_number(text, question):
            # A typed number can't be traced to a source record (unless the user wrote it in the question).
            problems.append(f"Write every number as a fact placeholder, not digits: {text!r}")
        for _, key, word in _UNIT_AFTER.findall(text):  # "{a dollar fact} days" cites the wrong figure
            fact = facts.get(key)
            if fact and fact["unit"] in ("dollars", "days", "months") and not _repeats_unit(fact, word):
                problems.append(f"{{{key}}} is {fmt(fact)}, not a number of {word}. If the number you need "
                                f"isn't a fact, say it couldn't be calculated.")
    kind = block.type
    if kind in ("heading", "paragraph", "callout") and not block.text:
        problems.append(f"A {kind} needs text")
    if kind == "list" and not block.items:
        problems.append("A list needs items")
    if kind == "stats":
        if not 1 <= len(block.stats) <= 4:
            problems.append("Stats need one to four tiles")
        for stat in block.stats:
            if stat.fact not in facts:
                problems.append(f"Unknown stat '{stat.fact}'")
            elif stat.compare_to and _units(facts, [stat.fact, stat.compare_to]) != {facts[stat.fact]["unit"]}:
                problems.append(f"Stat comparison must be a known fact in the same numeric unit: {stat.compare_to}")
    if kind in _KINDS:
        if block.dataset and block.dataset not in datasets:
            problems.append(f"Unknown dataset '{block.dataset}'")
        elif block.dataset and datasets[block.dataset]["kind"] not in _KINDS[kind]:
            problems.append(f"A {kind} can't draw the {datasets[block.dataset]['kind']} dataset {block.dataset}")
        if kind == "bar_chart" and bool(block.dataset) == bool(block.facts):
            problems.append("A bar_chart uses either one dataset or two to four facts")
        elif kind != "bar_chart" and not block.dataset:
            problems.append(f"A {kind} needs a dataset")
    if block.facts:
        problems += [f"Unknown chart fact '{key}'" for key in block.facts if key not in facts]
        if not 2 <= len(block.facts) <= 4 or len(_units(facts, block.facts)) != 1:
            problems.append(f"Chart facts must share one numeric unit (two to four facts): {block.facts}")
    for key in filter(None, (block.extra_monthly, block.lump_sum)):
        if block.dataset != "goal_projection" or facts.get(key, {}).get("unit") != "dollars":
            problems.append(f"What-if amounts must be dollar facts on the goal_projection line: {key}")
    return problems


def _units(facts: dict, keys: list[str]) -> set:
    """Units of the known keys; a date or an unknown key makes the set invalid for numeric comparison."""
    units = {facts[key]["unit"] if key in facts else "unknown" for key in keys}
    return units if not units & {"date", "unknown"} else units | {"invalid"}


_SLIPPED_BOLD = re.compile(r"\*\*([^*{}\n]+?)\}")


def fill(text: str, facts: dict) -> str:
    text = normalize(text, facts, ())
    # "{18 days} days": the placeholder already carries its unit, so drop the repeated word.
    text = _UNIT_AFTER.sub(lambda m: m[1] if m[2] in facts and _repeats_unit(facts[m[2]], m[3]) else m[0], text)
    text = PLACEHOLDER.sub(lambda m: fmt(facts[m[1]]), text)
    text = _SLIPPED_BOLD.sub(r"**\1**", text)  # the model sometimes closes "**{key}" with "}" instead of "**"
    text = text.replace("{", "").replace("}", "")
    return text if text.count("**") % 2 == 0 else text.replace("**", "")  # never leave a dangling bold marker
