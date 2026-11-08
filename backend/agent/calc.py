"""Safe evaluation of planner-written formulas over trusted facts: the model picks the maths, code does it."""
import ast
import math
import operator
import re
from datetime import date, timedelta

# Plain numbers a formula may use without the user having typed them: identities, calendar units, percent,
# and number words ("half", "double"). Every other number must appear in the user's question.
CONSTANTS = {0, 1, 2, 3, 7, 12, 30, 52, 100, 365, 0.25, 0.5, 0.75}
MAX_FORMULA = 400
MAX_RESULT = 1e9
MAX_YEARS_AHEAD = 10

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
_QUESTION_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv}
_FUNCTIONS = {"min": min, "max": max, "round": round, "ceil": math.ceil, "floor": math.floor, "abs": abs}


class CalcError(ValueError):
    """A formula that is unsafe, ungrounded, or can't be computed; the message is safe to show."""


def question_numbers(question: str) -> set[float]:
    return {float(n.replace(",", "")) for n in _QUESTION_NUMBER.findall(question)}


def normalize(formula: str, facts: dict, names) -> str:
    """Canonical form: facts in braces, earlier calculation names bare (models often mix these up)."""
    def unbrace(match):
        name = match[1].removeprefix("calc.")
        return name if match[1] not in facts and name in names else match[0]

    formula = _PLACEHOLDER.sub(unbrace, formula)
    for key in sorted(facts, key=len, reverse=True):  # longest first, so one key can't split a longer one
        formula = re.sub(rf"(?<![\w.{{]){re.escape(key)}(?![\w.}}])", "{" + key + "}", formula)
    return formula


def evaluate(formula: str, facts: dict, question: str, as_of: date, earlier: dict | None = None) -> float:
    """facts: {key: {"value", "unit", ...}} referenced as {key}; earlier: {name: value} from previous calculations."""
    if len(formula) > MAX_FORMULA:
        raise CalcError(f"Formula is longer than {MAX_FORMULA} characters")
    env = dict(earlier or {})
    formula = normalize(formula, facts, env)

    def placeholder(match):
        key = match[1]
        if key not in facts:
            raise CalcError(f"Unknown fact {{{key}}}")
        name = f"_fact{len(env)}"
        env[name] = facts[key]["value"]
        return name

    source = _PLACEHOLDER.sub(placeholder, formula)
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        raise CalcError("Formula is not valid arithmetic") from None
    allowed = CONSTANTS | question_numbers(question)
    try:
        value = _eval(tree.body, env, allowed, as_of)
    except ZeroDivisionError:
        raise CalcError("Division by zero") from None
    except (TypeError, OverflowError):
        raise CalcError("Formula mixes incompatible values") from None
    if isinstance(value, str) or not math.isfinite(value) or abs(value) >= MAX_RESULT:
        raise CalcError("Result is not a usable number")
    return int(value) if float(value).is_integer() else value


def run_all(calculations: list[dict], facts: dict, question: str, as_of: date,
            earlier: dict | None = None) -> list[dict]:
    """Run in order so later formulas can use earlier names; one failure doesn't stop the rest."""
    done, results = dict(earlier or {}), []
    for calc in calculations:
        out = {k: calc[k] for k in ("name", "label", "unit")}
        out["formula"] = normalize(calc["formula"], facts, done)
        try:
            out["value"] = done[calc["name"]] = evaluate(calc["formula"], facts, question, as_of, done)
        except CalcError as exc:
            out["error"] = str(exc)
        results.append(out)
    return results


def _eval(node, env, allowed, as_of):
    match node:
        case ast.Constant(value=v) if type(v) in (int, float):
            if float(v) not in allowed:
                raise CalcError(f"Number {v} is not in the question or the allowed constants")
            return v
        case ast.Name(id=name) if name in env:
            return env[name]
        case ast.Name(id=name):
            raise CalcError(f"Unknown name {name}")
        case ast.BinOp(op=op, left=left, right=right) if type(op) in _BINARY:
            return _BINARY[type(op)](_eval(left, env, allowed, as_of), _eval(right, env, allowed, as_of))
        case ast.UnaryOp(op=ast.USub(), operand=operand):
            return -_eval(operand, env, allowed, as_of)
        case ast.UnaryOp(op=ast.UAdd(), operand=operand):
            return +_eval(operand, env, allowed, as_of)
        case ast.Call(func=ast.Name(id="days_until" | "months_until" as name), args=[arg], keywords=[]):
            days = (_date_arg(arg, env, as_of) - as_of).days
            return days if name == "days_until" else days * 12 / 365.25
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in _FUNCTIONS and args:
            if name == "round" and len(args) != 1:
                raise CalcError("round takes one value; amounts are whole dollars")
            return _FUNCTIONS[name](*(_eval(a, env, allowed, as_of) for a in args))
        case _:
            raise CalcError(f"{type(node).__name__} is not allowed in a formula")


def _date_arg(arg, env, as_of) -> date:
    match arg:
        case ast.Constant(value=str(text)):
            pass
        case ast.Name(id=name) if isinstance(env.get(name), str):  # a date fact such as the goal target date
            text = env[name]
        case _:
            raise CalcError("Date functions take one YYYY-MM-DD date")
    try:
        when = date.fromisoformat(text)
    except ValueError:
        raise CalcError("Date functions take one YYYY-MM-DD date") from None
    if not as_of < when <= as_of + timedelta(days=round(365.25 * MAX_YEARS_AHEAD)):
        raise CalcError(f"Date must be after {as_of.isoformat()} and within {MAX_YEARS_AHEAD} years")
    return when
