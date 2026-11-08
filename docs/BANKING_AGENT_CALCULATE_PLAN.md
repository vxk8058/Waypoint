# Plan: add a "calculate" step to the agent graph

## Goal

Make the agent work the way it was originally designed. After data arrives, the AI uses judgment to decide one of four things:

1. **Done:** the data answers the question.
2. **Fetch more:** call more data sources (already works).
3. **Calculate:** the answer needs maths on the data (new).
4. **Can't answer:** the question is obscure or unsupported (already works).

**The rule that keeps numbers safe:** the AI chooses the maths and writes it as a formula using named figures. Code runs the formula, so the arithmetic is always exact. The AI still never types a number into the answer itself.

**Example:** "If I add $100 a day for the next month, how much more quickly can I get my car?"

```
days_needed  = ceil({savings.goal_remaining} / 100)                          → 18
months_now   = ceil({savings.goal_remaining} / {savings.goal_monthly_contribution})
```

The answer then says "You'd reach your car goal in **18 days**", with a code-written line showing how that was worked out.

---

## New flow

```
question → Router → product branches → Verify ──done──────────→ Gen UI → answer
                         ↑               │  ├─fetch more──→ Router (as today)
                         └───────────────┘  ├─calculate───→ Calculate ─→ Verify
                                            └─can't answer─→ Gen UI (with caveat)
```

- Calculate always returns to Verify, so the AI can check the result makes sense, or try a different formula if one failed.
- Calculate rounds count toward the existing **3-round limit**, so the loop still always ends.
- A single Verify decision can either fetch or calculate, not both. Fetch first, calculate next round.

---

## Steps

Do these in order. Each step ends with its own tests passing, as in the main checklist.

### Step 1: Give every fact a unit, and add the missing facts
**Files:** `backend/agent/ui/datasets.py`, `backend/agent/ui/validate.py`, `backend/agent/nodes/gen_ui.py`

- Each fact gets a `unit`: `dollars`, `days`, `months`, `percent` or `count`. All existing facts are `dollars`.
- `fill()` and the stat tiles format by unit: `$1,800`, `18 days`, `4 months`, `25%`. Stat tiles use the schema's `format.suffix` for non-dollar units.
- Add the facts that everyday maths needs and that aren't exposed yet:
  - `savings.goal_monthly_contribution` and `savings.goal_target_date` (from the goal)
  - the monthly averages from `wellness_inputs` already in each profile: `monthly.income`, `monthly.spending`, `monthly.recurring_bills`, `monthly.debt_payments`, and `liquid_cash`
- **Tests:** formatting for each unit; existing Gen UI tests unchanged.

**✅ Done (2026-11-07).**
- Every fact now has a `unit`. A `date` unit was added for the goal target date, alongside `dollars`, `days`, `months`, `percent` and `count`.
- `fmt()` in `ui/datasets.py` formats by unit (`$1,800`, `18 days`, `1 day`, `4.5 months`, `25%`, `August 31, 2027`). Placeholder filling and the planner's fact list use it.
- Stat tiles keep dollars as numbers with currency formatting (the frontend formats them). Other units are sent as pre-formatted text (`"18 days"`), which the schema allows and which avoids "1 days".
- `get_data` now includes the profile's `wellness_inputs` in every branch's data, and `build_facts` adds:
  - `savings.goal_monthly_contribution`, `savings.goal_target_date`
  - `monthly.income`, `monthly.spending`, `monthly.recurring_bills`, `monthly.debt_payments`, `liquid_cash`
- 12 new tests in `tests/test_gen_ui.py`. Full suite: 265 passed.
- Side effect: the worker and Verify prompts are slightly larger (one small dict per branch), and the code-only fallback can now show the goal's monthly saving among its four tiles.

### Step 2: The safe formula runner
**New file:** `backend/agent/calc.py` (code only, no AI)

- Parse each formula with Python's `ast` module, never `eval`. Allow only:
  - numbers, `+ - * / //`, parentheses, unary minus
  - the functions `min`, `max`, `round`, `ceil`, `floor`, `abs`
  - `{fact.key}` names, and names of earlier calculations in the same round
  - `days_until("YYYY-MM-DD")` and `months_until("YYYY-MM-DD")`, counted from the data's `as_of_date`, not today
- **Number grounding:** every plain number in a formula must appear in the user's question (like `100`), or be a calendar or percent constant (`7, 12, 30, 52, 365, 100`). A date must be after `as_of_date` and within 10 years. This stops the AI from inventing an amount and disguising it as maths.
- **Limits:** at most 5 calculations per round, at most 200 characters per formula, and a result that is finite and under one billion.
- Each failure (division by zero, unknown fact, disallowed syntax, ungrounded number) becomes a short error for that calculation only. The other calculations still run.
- **Tests:** the screenshot case; every allowed operator and function; rejection of `__import__`, attribute access, unknown names, invented numbers, and past dates; division by zero; the limits.

**✅ Done (2026-11-07).**
- `backend/agent/calc.py` provides `evaluate(formula, facts, question, as_of, earlier)` and `run_all(calculations, facts, question, as_of)`.
- Formulas are parsed with `ast` and walked by an allow-list. Anything else is rejected with a message that is safe to show: attribute access, `**`, comparisons, conditionals, lambdas, comprehensions, keyword arguments, booleans, strings outside the date functions, `round` with a second argument, and any unknown name or call.
- **Number grounding:** a literal must appear in the question (commas and `$` handled, so "$1,500" allows 1500), or be one of `0, 1, 2, 3, 7, 12, 30, 52, 100, 365, 0.25, 0.5, 0.75`.
  - This applies decision 1's recommendation: the number words "half", "double" and so on map to the fixed constants. It's one set in `calc.py` if you decide otherwise.
- **Dates:** `days_until` / `months_until` take an ISO date string or a date fact (such as `{savings.goal_target_date}`), count from the data's `as_of_date`, and reject past dates or dates more than 10 years ahead.
- **Limits:** 200-character formulas; results must be finite and under one billion. Division by zero and mixing a date with arithmetic give per-calculation errors.
- **Chaining:** `run_all` runs calculations in order, so later ones can use earlier names, and one failure doesn't stop the rest. The five-per-round limit and name validation are enforced by the step 3 schema.
- 20 new tests in `tests/test_calc.py`, including the screenshot case: `ceil($1,800 / 100) = 18` days. Full suite: 285 passed.

### Step 3: Let Verify ask for calculations
**Files:** `backend/agent/schemas.py`, `backend/agent/nodes/verify.py`, `backend/agent/state.py`

- New `Calculation` model: `name` (snake_case), `label` (what it means, for example "Days to reach your car goal"), `unit`, `formula`.
- `VerifyDecision` gains `calculations: list[Calculation]` (at most 5).
  - **Validation:** calculations and fetch requests can't appear together, and calculations can't be paired with `done=true`. A decision asking for calculations counts as "not done yet".
- **The Verify prompt changes:**
  - It receives the **fact list** (key, label, value, unit) instead of the full raw records, which also cuts the roughly 121,000-character prompts.
  - It receives the results of any earlier calculations.
  - New rule: "If the question needs arithmetic on these facts, request calculations. Use the user's own numbers from the question. If the question can't be answered from available data or simple maths, say so."
- `AgentState` gains `calculations: list[dict]`, holding the results so far (name, label, unit, value or error, formula).
- `after_verify` gets one more destination: `"calculate"`.
- At the round limit, any pending calculation request is dropped, the same as pending fetches today.
- **Tests:** schema validation; routing to `calculate`; the round limit drops calculations; facts reach the prompt and raw transaction lists don't.

**✅ Done (2026-11-08).**
- **`schemas.py`:** new `Calculation` model.
  - `name` must be snake_case, start with a letter, be at most 40 characters, and not be a formula function name.
  - `label` is up to 80 characters; `unit` is one of dollars, days, months, percent or count; `formula` is up to 200 characters.
- **`VerifyDecision.calculations`:** at most 5, with unique names.
  - A decision can't be `done` and request calculations, or request calculations together with fetches.
  - Asking for calculations still requires a `missing` explanation.
- **Verify's prompt** now sends each result's product, summary, confidence and errors, plus the code-computed fact list (label, formatted value, unit), the data's `as_of_date`, and earlier calculation results. It no longer sends raw records. It describes the four choices: done, fetch, calculate, can't answer.
  - For the primary demo profile with all products and transactions, the payload dropped from about 272,000 to about 11,500 characters.
- **State, routing and limits:**
  - `AgentState.calculations` starts as `[]` in `initial_state`.
  - `after_verify` returns `"calculate"` when calculations are requested.
  - At the round limit, pending calculations are dropped with the limit caveat, the same as fetches.
  - New helper `data_date(results)` in `ui/datasets.py`.
- **Tests:** 14 new in `tests/test_verify.py` (routing, prior results in the prompt, the round limit, 10 invalid decisions, a valid model). Three existing tests were updated for the facts-based prompt and the new state field. Full suite: 299 passed.
- **⚠️ Until step 4:** the graph has no `calculate` node or edge. A live Verify that requests a calculation would make the graph raise an error, so don't restart the live API on this code until step 4 is done. (The API on port 8001 is still running the earlier code.)
- **Changes Verify's judgment:** it now sees facts instead of full records. Rerun the seven original scenarios live after step 4.

### Step 4: The Calculate node, wired into the graph
**Files:** new `backend/agent/nodes/calculate.py`, `backend/agent/graph.py`

- The node runs each requested formula through `calc.py`, using the current facts, and adds the results to `state["calculations"]`. A result from the same `name` replaces the earlier one.
- Graph edges: `verify → calculate` (conditional) and `calculate → verify`.
- `run_agent` logs `node=calculate count=N errors=M`. It never logs formulas or values.
- **Tests:** an end-to-end graph test (route → savings → Verify asks for a calculation → Calculate → Verify done → Gen UI); a failed formula followed by a corrected one; the round limit.

**✅ Done (2026-11-08).**
- New `backend/agent/nodes/calculate.py`. It builds facts from the current results, runs Verify's formulas through `calc.run_all` with the records' `as_of_date`, and merges results by name: a corrected formula replaces the earlier attempt.
  - Successful values from earlier rounds can be reused by name (`run_all` gained an `earlier` argument).
  - If no record date exists, each calculation gets an error instead of a crash.
- **Graph:** `verify → calculate` (conditional) and `calculate → verify`. The Mermaid output shows both edges.
  - Calculate rounds use the same three-round Verify limit.
  - Calculate never re-fetches data.
- **Logging:** `run_agent` logs `node=calculate count=N errors=M`, with no formulas or values.
- **Tests:** 4 new in `tests/test_main_graph.py`. Full suite: 303 passed.
  - The screenshot question through the real compiled graph: savings → Verify asks for `ceil({savings.goal_remaining} / 100)` → Calculate → Verify sees the value → done → Gen UI, with the exact logged path and no re-fetch.
  - A rejected ungrounded formula (`/ 250`) corrected next round and chained (`ceil(days_needed / 7)`).
  - Repeated calculation requests stopping at round 3 with the limit caveat.
  - A missing record date.
- **Not yet:** Gen UI can't cite calculation results; that's step 5. Until then, a calculated answer still reads like a facts-only answer. The live API can now safely run this code, but it won't show calculated numbers.

### Step 5: Calculations in the answer
**File:** `backend/agent/nodes/gen_ui.py`

- Successful calculations are added to the facts as `calc.<name>` (with label and unit), so Gen UI cites them with placeholders exactly like balances.
- Code adds a small **"How this was worked out"** paragraph whenever a calculation is cited. It shows the formula with labels and real values substituted, for example: *Left to reach First car fund ($1,800) ÷ $100 per day, rounded up = 18 days.* Because code writes it, it passes grounding.
- Failed calculations appear as caveats ("Couldn't calculate days to goal").
- One new line in `RULES`: "For what-if questions, lead with the calculated facts and show the before/after as stat tiles."
- **Tests:** the calculated value appears exactly in text and tiles; the explanation paragraph matches the formula; a failed calculation becomes a caveat; documents pass the frontend schema.

**✅ Done (2026-11-08).**
- **Calculation results become facts:** Gen UI adds each successful one as a fact `calc.<name>` (label, value, unit, and its formula), so the planner cites it with a placeholder and stat tiles format it by unit ("18 days").
- **Explanation line:** when the answer text, a chart title, subtitle or caption, or a stat cites a `calc.*` fact, code adds a small muted paragraph:
  - *How this was worked out: Days to reach goal = round up(Left to reach Emergency fund ($1,800) ÷ 100) = 18 days.*
  - It's built in one pass over the formula: facts become label (value); dates become "December 25, 2026"; earlier calculations become label (value); `ceil`/`floor`/`min`/`max` become words; `* / //` become `× ÷ ÷ (whole)`.
  - Uncited calculations get no line.
- **Failed calculations** become caveats: "Couldn't calculate weeks needed: Division by zero."
- **Fallback:** the code-only fallback now leads with calculation results (up to four tiles with balances) plus their explanation line, so a calculated answer survives a failed or rejected plan.
- **`RULES`:** one line telling the planner to lead with `calc.*` facts and show before/after as stats for what-if questions.
- **Tests:** 5 new (4 in `tests/test_gen_ui.py`, 1 end-to-end in `tests/test_main_graph.py`). One step 1 test had used a made-up `calc.` key without a formula and now uses another prefix. Full suite: 308 passed.

### Step 6: Router nudge for what-if questions
**File:** `backend/agent/nodes/eval_query.py`

- One sentence: "Goal, saving, car or what-if questions need savings; add checking and credit_card when the question changes spending."
- **Tests:** the existing router tests still pass. Live check: the three suggested Simulation questions route consistently.

### Step 7: Live check (Super model, port 8001, demo user Poyo)

| Question | Expected |
|---|---|
| If I add $100 a day for the next month, how much more quickly can I get my car? | Calculates days to goal; tiles show now vs with $100/day; explanation line |
| Can I afford the car by Christmas? | `months_until` the date, needed per month vs current contribution, yes/no |
| What if I cut dining out in half? | Dining spending × 0.5 per month (the 50 must come from "half": see the note below), new time to goal |
| What happens if I take a car loan instead? | Says it can't without a price, or asks for price and rate. Must not invent a price |
| What's the weather? | Still refused |

Record the results in `BANKING_AGENT_CHECKLIST.md`.

---

## Decisions to make before starting

1. **Words that mean numbers** ("half", "double", "a quarter"): allow `0.5`, `2` and `0.25` as constants, or require the AI to only use digits that appear in the question? **Recommend:** allow a small fixed list (`0.25, 0.5, 0.75, 2, 3`) and show it in the explanation line so the user can see it.
2. **Car loan:** should the AI be allowed to assume a typical rate and term (shown as assumptions), or must it ask? **Recommend:** ask, unless the user gave them; this keeps the "never invent a number" rule.
3. **Show the formula line always, or only on what-if answers?** **Recommend:** only when a calculation is cited.

## Out of scope for now
- Loops, variables across rounds, or "simulate month by month" calculations (the pnc_wellness `forecast_cash` can be added later as a single allowed function if needed)
- New chart types for projections (tiles first)
- Letting the AI call arbitrary tools or APIs

## Risks
- **The AI picks the wrong formula** (for example forgetting the user already saves monthly). The arithmetic stays exact, and the explanation line makes the mistake visible. Verify sees the results and can correct it next round.
- **Each calculation round adds a Verify call** (about 2–30 seconds each). The round limit caps it.
- **Changing Verify to see facts instead of raw records changes its judgment.** Rerun all seven original scenarios live after Step 3.

**Rough effort:** 1–1.5 days.
