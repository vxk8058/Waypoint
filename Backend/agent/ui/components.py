"""Frontend AI document contract: the vendored schema plus the dimension rules it cannot express."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

# Copied verbatim from the frontend's bundled ai-document.schema.json; replace the file when the frontend changes.
SCHEMA = json.loads((Path(__file__).with_name("ai-document.schema.json")).read_text())
_validator = Draft202012Validator(SCHEMA)


def validate_document(doc: dict) -> dict:
    """Return doc unchanged if the frontend can render it; otherwise raise ValueError."""
    error = next(iter(sorted(_validator.iter_errors(doc), key=lambda e: list(e.path))), None)
    if error:
        raise ValueError(f"Invalid AI document at {'/'.join(map(str, error.path)) or '<root>'}: {error.message}")
    for i, block in enumerate(doc["blocks"]):
        inner = block["props"]["blocks"] if block["type"] == "row" else [block]
        for leaf in inner:
            _check_dimensions(leaf, i)
    return doc


def _check_dimensions(block: dict, index: int):
    props = block["props"]
    axis = {"bar_chart": "categories", "line_chart": "x"}.get(block["type"])
    if not axis:
        return
    expected = len(props[axis])
    for series in props["series"]:
        lengths = [len(series["values"])] + [len(series["band"][k]) for k in ("lower", "upper") if "band" in series]
        if any(n != expected for n in lengths):
            raise ValueError(f"Block {index} series '{series['name']}' needs one value per {axis} entry ({expected})")
