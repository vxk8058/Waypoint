import copy

import pytest

from backend.agent.ui.components import validate_document

BAR = {"type": "bar_chart", "props": {
    "title": "Spending by category, October", "orientation": "horizontal", "sort": "desc",
    "valueFormat": {"style": "currency"}, "highlight": ["Dining"],
    "referenceLines": [{"value": 400, "label": "Budget"}],
    "categories": ["Rent", "Groceries", "Dining"],
    "series": [{"name": "Spent", "values": [1450, 386, None]}],
}}
LINE = {"type": "line_chart", "props": {"x": ["2026-09", "2026-10"], "series": [
    {"name": "Savings", "values": [900, 1000], "band": {"lower": [850, 950], "upper": [950, 1050]}}]}}
DOC = {"blocks": [
    {"type": "paragraph", "props": {"text": "You spent **$513** on dining.", "size": "lead"}},
    {"type": "stats", "props": {"items": [{"label": "Spent in October", "value": 2349,
                                           "format": {"style": "currency"}, "goodDirection": "down"}]}},
    {"type": "callout", "props": {"tone": "danger", "text": "Dining is over budget."}},
    BAR,
    {"type": "row", "props": {"blocks": [LINE, {"type": "divider", "props": {}}]}},
]}


def test_valid_document_passes_unchanged():
    doc = copy.deepcopy(DOC)
    assert validate_document(doc) == DOC


def mutate(fn):
    doc = copy.deepcopy(DOC)
    fn(doc)
    return doc


@pytest.mark.parametrize("bad", [
    mutate(lambda d: d.update(caveats=[])),                                           # unknown top-level field
    mutate(lambda d: d["blocks"][3]["props"].update(data=[{"label": "x", "value": 1}])),  # old label/value format
    mutate(lambda d: d["blocks"].append({"type": "table", "props": {}})),             # unknown block type
    mutate(lambda d: d["blocks"][3]["props"].update(series=[])),                      # no series
    mutate(lambda d: d["blocks"][3]["props"].update(
        series=[{"name": str(i), "values": [1, 2, 3]} for i in range(6)])),            # too many series
    mutate(lambda d: d["blocks"][3]["props"].update(valueAxis={"min": 5})),           # bars must start at zero
    mutate(lambda d: d["blocks"][4]["props"]["blocks"].append(copy.deepcopy(d["blocks"][4]))),  # nested row
    mutate(lambda d: d["blocks"][4]["props"].update(blocks=[LINE] * 4)),              # row over 3 blocks
    {"blocks": []},
])
def test_schema_violations_are_rejected(bad):
    with pytest.raises(ValueError, match="Invalid AI document"):
        validate_document(bad)


@pytest.mark.parametrize("bad", [
    mutate(lambda d: d["blocks"][3]["props"]["series"][0]["values"].pop()),           # bar values < categories
    mutate(lambda d: d["blocks"][4]["props"]["blocks"][0]["props"]["series"][0]["band"]["upper"].append(1)),
])
def test_dimension_mismatches_are_rejected(bad):
    with pytest.raises(ValueError, match="one value per"):
        validate_document(bad)
