"""Calculate: run Verify's requested formulas against trusted facts; code does all the arithmetic."""
from datetime import date

from ..calc import run_all
from ..query import run_query
from ..state import AgentState
from ..ui.datasets import all_transactions, build_datasets, build_facts, data_date


def calculate(state: AgentState):
    results = state.get("results", [])
    requested = [c.model_dump() for c in state["verify"].calculations]
    previous = state.get("calculations", [])
    names = {c["name"] for c in requested}
    # Retry earlier failures too: one may only have failed because a name it uses didn't exist yet.
    requested += [{k: c[k] for k in ("name", "label", "unit", "formula")}
                  for c in previous if "error" in c and c["name"] not in names and not c.get("query")]
    # Queries run first so this round's formulas can use their results by name.
    queried = [run_query(q.model_dump(), all_transactions(results)) for q in state["verify"].queries]
    as_of = data_date(results)
    if as_of is None:
        new = queried + [{**c, "error": "No record date is available for calculations"} for c in requested]
    else:
        facts = build_facts(results, build_datasets(results))
        earlier = {c["name"]: c["value"] for c in previous + queried if "value" in c}  # earlier successes
        new = queried + run_all(requested, facts, state["query"], date.fromisoformat(as_of), earlier)
    by_name = {c["name"]: c for c in previous}
    by_name.update((c["name"], c) for c in new)  # a corrected formula replaces the earlier attempt
    return {"calculations": list(by_name.values())}
