# Banking agent: what's left to finish

The agent graph is built and tested offline (steps 1–15 in [BANKING_AGENT_CHECKLIST.md](BANKING_AGENT_CHECKLIST.md)): router → product branches in parallel → Verify loop (max 3 rounds) → Gen UI, served at `POST /api/me/agent`. All 253 tests pass with **scripted** models and a **fake** Nessie server.

What's left is mostly running it against the real models, real Nessie, and the real frontend. Do the steps in order: each one depends on the one before it.

| # | Task | Blocked on | Effort |
|---|---|---|---|
| 0 | Commit the current work | Nothing | 5 min |
| 1 | Connect Nemotron and smoke-test it | NVIDIA API key, model IDs | 30 min |
| 2 | Run the seven scenarios with live models | Step 1 | 1–2 h |
| 3 | Run against live Nessie | Nessie key, MongoDB, step 2 | 1 h |
| 4 | Render the answers in the frontend (11e) | Frontend code | 2–4 h |
| 5 | Decide on LangSmith tracing | Your decision | 15 min (or skip) |
| 6 | Decide what "other API" means | Your decision | Skip unless needed |
| 7 | Harden before a public demo | Steps 2–4 | 1–3 h |
| 8 | Final check-in | All of the above | 15 min |

---

## 0. Commit the current work

Nothing from steps 1–15 is committed yet. Commit before any live testing so you can roll back prompt changes.

```bash
git add backend/agent backend/api/app.py backend/services/profile_service.py backend/config.py requirements.txt .env.example README.md docs tests
```

```bash
git commit -m "Add read-only banking agent graph with verified generated UI"
```

Check `git status` first: `banking-agent-build-guide.md` is untracked; decide whether it belongs in the repo.

---

## 1. Connect Nemotron and smoke-test it (checklist 1b)

**Goal:** both models answer, and their structured output passes the agent's schemas.

1. Get an API key at [build.nvidia.com](https://build.nvidia.com) and pick two models:
   - **Planner** (routing, Verify, UI plan): a larger Nemotron model (for example a Nemotron Super variant).
   - **Worker** (per-product evaluation, source selection): a smaller, faster Nemotron model (for example a Nano variant).

   Copy the exact model IDs from each model's page; don't guess them.
2. Put them in `.env` (never commit it):
   ```
   NVIDIA_API_KEY=nvapi-...
   PLANNER_MODEL=<planner model id>
   WORKER_MODEL=<worker model id>
   ```
3. Smoke-test the planner through the real router node:
   ```bash
   .venv/bin/python -c "from backend.agent.nodes.eval_query import eval_query; print(eval_query({'query': 'Compare my savings with my loans'}))"
   ```
   **Pass:** `products=['savings', 'loans']`. **Fail:** a `verify` key saying "Query routing is unavailable (…)". The exception type in parentheses tells you why (authentication, model not found, or output that never matched the schema).
4. Smoke-test the worker with a `ProductEvaluation`:
   ```bash
   .venv/bin/python -c "from backend.agent.llm import get_llm, structured; from backend.agent.schemas import ProductEvaluation; print(structured(get_llm('worker'), ProductEvaluation, 'Summarize: checking balance_total is 1461 whole USD dollars. Return summary and confidence 0-1.'))"
   ```
   **Pass:** a `ProductEvaluation` with a summary and a confidence between 0 and 1.
5. **If structured output keeps failing:** in `backend/agent/llm.py`, try `model.with_structured_output(schema, method="json_mode")` (or the method the adapter's docs recommend for that model), then rerun `pytest tests/test_agent_llm.py`.
6. Record the results under step 1b in the checklist and tick the two open boxes.

---

## 2. Run the seven scenarios with live models (checklist 13)

**Goal:** real Nemotron output takes the expected path and produces a sensible, grounded answer.

1. Start the API. MongoDB must have the profiles: run `python scripts/validate_profile.py --save-mongo` once.
   ```bash
   uvicorn backend.api.main:app --reload --port 8000
   ```
2. Log in and keep the token:
   ```bash
   TOKEN=$(curl -s localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"poyo@waypoint.demo","password":"waypoint-demo"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
   ```
3. Ask each question and watch the `waypoint.agent` log lines in the server terminal. They show the path without personal data.
   ```bash
   curl -s localhost:8000/api/me/agent -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question":"What'\''s my checking balance?"}' | python3 -m json.tool
   ```

   | Question | Expected log path | Expected answer |
   |---|---|---|
   | What's my checking balance? | `eval_query` → `checking` → `verify done=True` → `gen_ui` | Lead sentence + stats tile |
   | Compare my savings to my loan payoff | `savings` + `loans` in the same round → one `verify` | Savings figure; caveat that there is no loan / no payoff quote |
   | Why is my balance lower than usual? | `checking` → `verify need_other_data=True` → `other_data` → `verify` | Income vs spending chart |
   | (API failure) Stop MongoDB or Nessie, then ask a balance question | Branch `errors=1` | Fallback or answer with a warning callout; no crash |
   | Help me with my money | `eval_query products=[]` → `gen_ui` | Clarification in a callout |
   | Where did my money go in October? | Transactions fetched → `verify done=True` | Bar chart titled for October |
   | What's my savings balance? | `savings` → `gen_ui` | Text + stats, **no chart** |

4. **Poyo (stu-002) has no credit card or loans.** To test those branches live, add a second demo user linked to `stu-001` or `stu-003` in `DEMO_USERS` (`backend/auth/users.py`), then log in as that user.
5. **Common live problems and fixes:**
   - **Lots of fallback answers** ("I couldn't prepare a verified written answer"): the model is typing digits instead of `{fact_key}` placeholders. Tighten the wording in `RULES` in `backend/agent/nodes/gen_ui.py` (for example add one worked example of a placeholder sentence). Don't loosen the no-digits check.
   - **Verify never says done:** it is judging stale or synthetic data as incomplete. Check the caveats; if the data is fine, adjust the Verify prompt in `backend/agent/nodes/verify.py`.
   - **Wrong routing:** adjust the router prompt in `backend/agent/nodes/eval_query.py`.
   - After any prompt change, rerun `pytest -q`: the offline tests must still pass.
6. Record each scenario's real outcome in the checklist under step 13 ("Live Nemotron").

---

## 3. Run against live Nessie (checklist 15)

**Goal:** the same scenarios work with data read from the real Nessie API, with GET requests only.

1. Set `NESSIE_API_KEY` and `MONGODB_URI` in `.env`.
2. Seed and verify (setup only; the agent itself never writes to Nessie):
   ```bash
   python scripts/seed_nessie.py
   ```
   ```bash
   python scripts/verify_nessie_data.py
   ```
3. Restart the API and repeat the step 2 questions. In each answer, check:
   - The balances match `GET /api/me/accounts` for the same user.
   - No "pre-seed" caveat (that would mean the profile isn't linked to Nessie).
4. Test an outage: set `NESSIE_BASE_URL` to an unreachable host, restart, and ask again. Expect the caveat "Nessie unavailable (…); serving last snapshot" and no internal paths or IDs in the answer.
5. Record the results under step 15 in the checklist.

---

## 4. Render the answers in the frontend (checklist 11e)

**Goal:** the frontend renders every block the backend sends and safely ignores anything it doesn't know.

The backend returns `{"blocks": [...]}` matching the frontend's own `ai-document.schema.json`. It currently emits only `paragraph`, `stats`, `callout` and `bar_chart`.

1. In the frontend, add a call to `POST /api/me/agent` with the user's bearer token and body `{"question": "..."}`. Add the frontend's origin to `CORS_ORIGINS` in `.env` if it isn't already there.
2. Render blocks with a registry keyed by `type`, passing `props` straight through:
   ```jsx
   const REGISTRY = { heading: Heading, paragraph: Paragraph, list: List, callout: Callout, stats: Stats,
                      divider: Divider, bar_chart: BarChart, line_chart: LineChart, pie_chart: PieChart,
                      histogram: Histogram, scatter_plot: ScatterPlot, gantt_chart: GanttChart, row: Row };

   export function AiDocument({ doc }) {
     return doc.blocks.map((block, i) => {
       const Block = REGISTRY[block.type];
       return Block ? <Block key={i} {...block.props} /> : null; // unknown types are skipped, not crashed on
     });
   }
   ```
3. Check, in the browser:
   - Each of the step 2 answers renders (text, stats tiles, the October bar chart, the warning callout).
   - A chart with empty data shows its empty state.
   - A document with an unknown block type (for example `{"type": "table", "props": {}}`) renders the other blocks and skips that one.
4. **Keep the schemas in sync:** the backend validates against a copy at `backend/agent/ui/ai-document.schema.json`. Whenever the frontend's bundled schema changes, copy it over and run `pytest tests/test_ui_components.py`.
5. Record the results under 11e in the checklist and tick it.

---

## 5. Decide on LangSmith tracing (checklist 14)

Tracing sends **full prompts** to LangSmith, including balances, transactions, and student bio data.

- **Recommended:** leave it off. The `waypoint.agent` log already shows the path of each request.
- **If you want it for a demo:** only enable it with synthetic demo profiles, in a dedicated LangSmith project, by setting `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env`. Turn it off again afterwards.
- Either way, write the decision under step 14 in the checklist.

---

## 6. Decide what "other API" means (checklist 7)

The Other Data branch can fetch `transactions` and `bio`; `other_api` is a placeholder that always reports "not configured".

- **If you don't need another data source:** remove `other_api` from `OtherSource` in `backend/agent/subgraphs/other_data.py` and from `Source` in `backend/agent/data.py`, update the tests that mention it (`tests/test_agent_data.py`, `tests/test_other_data_subgraph.py`), and tick the item.
- **If you do:** name the provider and the exact read-only data it supplies, add one fetch function in `get_data`, and add a success and a failure test in `tests/test_other_data_subgraph.py`.

---

## 7. Harden before a public demo (recommended)

- **Rate limit the endpoint.** A question touching all four products makes 7 model calls in its first round, and each Verify retry and UI regeneration adds more (around 20 in the worst case). Add a per-user limit on `/api/me/agent` (for example a few questions per minute) so one user can't run up the NVIDIA bill.
- **Wrong-fact risk.** The model could place a correct number in the wrong sentence (for example the savings balance in a sentence about checking). During step 2, read every answer for this. If it happens, add a check in `backend/agent/ui/validate.py` that a sentence naming one product only uses that product's fact keys.
- **Internal IDs in data warnings.** Some mapping warnings (for example "account … is not in the id map") include internal record IDs and reach users and the model. Shorten them in `backend/mapping/nessie_to_unified.py` if that matters for your demo.
- **Timeouts.** Live model calls can be slow. Check the endpoint's total time in step 2; if it's over about 20 seconds, consider a smaller planner model.

---

## 8. Final check-in

When steps 1–4 pass (and 5–6 are decided):

1. Run the full suite:
   ```bash
   .venv/bin/python -m pytest -q
   ```
2. Tick the last step 15 box ("Final check-in") in the checklist, with any remaining gaps written out explicitly.
3. Commit and open a pull request from `DevMA` into `main`.
