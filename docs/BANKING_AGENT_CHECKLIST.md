# Banking agent implementation checklist

Based on `banking-agent-build-guide.md`, adapted to the existing Waypoint backend.

## Working agreement

- Work on one numbered step at a time. After each step, run its checks, record the result here, and check in with the user before continuing.
- Each check-in states what changed, what passed or failed, and any decision needed. A failed or blocked check stays unchecked.
- Reuse existing services, schemas, authentication, fixtures, and dependencies. Add only code needed for the current step.
- Keep financial calculations in code using the project's whole-dollar integer convention (`backend/schemas/common.py`). Do not scale existing values as cents.
- Keep bank access read-only. Never seed, reset, or modify bank records as part of agent execution.
- Use deterministic model stubs for routine tests; report live model checks separately. Never print credentials.

## Preparation

- [x] Read the complete build guide and Ponytail instructions.
- [x] Inspect the existing project, dependencies, profile service, authentication boundary, Nessie gateway, normalized schemas, and test fixtures.
- [x] Create this checklist, covering guide steps 1–15, including 1b and 11a–11f.
- [x] Resolve scope questions at the first check-in: add the agent to the existing backend; defer the separately developed frontend; leave NVIDIA credentials and model IDs as placeholders.

Inspection evidence: `backend/services/profile_service.py` already supplies unified profiles with cache and fallback metadata; `backend/api/app.py` resolves the authenticated user's profile; `backend/integrations/nessie/gateway.py` owns retrieval. No frontend implementation or `bar_chart.schema.json` was found in the repository file inventory. Git tracks the application under lowercase `backend`; the local case-insensitive filesystem displays `Backend`, which also contains two legacy tracked files. Use lowercase package imports.

Preparation verification: checklist mapped against the source guide; no implementation files changed and no runtime or live-service tests run yet.

## Implementation steps and acceptance checks

### 1. Project and environment

- [x] Establish the existing test baseline and confirm Python/environment and package casing.
- [x] Use the existing backend package for the agent, rather than scaffolding a second application.
- [x] Install current requirements and add documented environment variable placeholders; preserve current settings and requirements. Add agent dependencies when their implementation steps need them.
- [x] Verify: imports work, dependencies install, secrets remain ignored, and baseline failures are recorded separately from new failures.
- [x] Check in with changed files and verification results.

Step 1 evidence: created `.venv` with Python 3.12; installed existing requirements; `pip check` passed; all 79 existing tests passed (one third-party Starlette deprecation warning). Initial collection failed because the physical directory was `Backend`; normalized it to `backend`, matching application imports, without changing tracked source contents. Confirmed `.env` and `.venv` are ignored and all three NVIDIA placeholders parse as empty strings. No NVIDIA calls made. Corrected this checklist's initial cents assumption to the repository's documented whole-dollar convention.

### 1b. Nemotron configuration

- [x] Confirm supported structured-output behavior from official LangChain NVIDIA reference/source and installed adapter 1.5.0. Exact model IDs remain blank as requested, pending live configuration.
- [x] Centralize planner/worker setup and bounded structured-output retries; reuse existing environment loading.
- [x] Keep model/network initialization out of unrelated API imports and offline tests.
- [x] Verify valid, malformed, empty, and exhausted-retry outputs with deterministic tests.
- [x] Smoke-test both configured models when credentials are available (deferred by request).
- [x] After step 2, verify live structured `ProductResult` output. Record live checks as blocked if credentials are unavailable.

Live 1b evidence (2026-11-07): planner `nvidia/nemotron-3.5-super-vl-120b-a12b`, worker `nvidia/nemotron-3.5-lightning-30b-a3b`. The live router (`eval_query`) routed "Compare my savings with my loans" to `['savings', 'loans']` with a valid `RouteDecision`; the live worker returned a valid `ProductEvaluation` (confidence 0.98) for a synthetic checking balance. Each smoke test used only a sample question or number, no profile data. Full offline suite still 253 passed. Verify and Gen UI planning with live models are still untested (step 13 live scenarios).
- [x] Check in with offline and live results distinguished.

Step 1b evidence: added lazy `get_llm(role)` and `structured()` in `backend/agent/llm.py`, three settings in the existing configuration, and the NVIDIA adapter dependency. All 94 tests passed, including 15 new model setup/output cases; `pip check` passed. No live model requests were made. Self-hosted NIM configuration, reasoning flags, and rate-limit backoff are deferred until needed. The adapter can attempt alternative structured-output formats internally; the helper's three-attempt limit bounds wrapper invocations, not individual HTTP requests.

### 2. Shared contracts

- [x] Define `ProductResult`, `RouteDecision`, and `VerifyDecision` with validated product names and confidence limits.
- [x] Define the trusted-data boundary: workers return only `ProductEvaluation` (summary/confidence); subgraph code assembles `ProductResult` with original data, product identity, and errors. Actual assembly will be implemented and checked in step 5.
- [x] Define consistent behavior for empty routing and contradictory verification decisions.
- [x] Verify valid construction, invalid decisions, and the existing structured-output helper with the new contracts using offline tests. Live checks remain deferred.
- [x] Check in.

Step 2 evidence: 44 focused tests passed (29 new contract cases plus 15 existing model-helper cases). Unknown products/fields, duplicate routes, invalid confidence, and contradictory verification are rejected. Empty routes require an explanation and must not default to checking. Incomplete verification requires `missing`; with no fetch targets it means stop with a caveat or clarification, not loop. Product data/errors are excluded from the worker output schema. The deferred live check will use `ProductEvaluation` rather than asking the model to generate trusted `ProductResult.data`.

### 3. Main state

- [x] Define minimal state: query, trusted user/profile context, routes, results, verification, iteration count, and final UI.
- [x] Support independent branch updates without losing results and ensure later results supersede stale results when consumed.
- [x] Verify reducer behavior and fresh state initialization for the same and different users. Actual graph concurrency and API authorization checks remain in steps 8, 12, and 13.
- [x] Check in.

Step 3 evidence: 52 focused agent tests passed, including eight new state cases; diff checks passed. `initial_state(query, user)` derives identity from the server-authenticated `PublicUser` and creates a new result list for each request. `merge_results` retains one current result per product, preserving other products and replacing previous successes even when a re-fetch fails. Unlike the guide's append-only reducer, this prevents old product facts from surviving a failed refresh. Inputs are not mutated. No checkpointing or main graph was added; callers must use fresh state and must not share checkpoint threads across requests/users when graph execution is introduced.

### 4. Mock data access

- [x] Reuse existing synthetic profiles and fixtures for checking, savings, credit cards, loans, transactions, and student bio data. Undefined `other_api` is explicitly unavailable.
- [x] Keep a small data-access boundary compatible with `ProfileService`; do not duplicate Nessie clients or existing financial mapping.
- [x] Include unavailable data, missing accounts, and failing retrieval cases.
- [x] Verify: fixtures preserve whole-dollar units, provenance, dates, and stale/pre-seed warnings; offline tests use an in-memory database and no live gateway.
- [x] Check in.

Step 4 evidence: 64 focused agent tests passed, including 12 new data-access cases. `get_data(profiles, profile_id, source)` uses the existing profile service; test fixtures supply existing synthetic profiles through mongomock. Product branches receive matching accounts, transactions, and bills; savings also receives its linked goal. Other sources expose transactions or student bio, omitting names and addresses. Missing accounts stay empty rather than becoming invented zero balances. Errors propagate for subgraphs to handle in step 5. Stale warnings and dates are retained, returned data does not mutate cached profiles, and a mismatched returned profile is rejected. No bank API calls, new dependencies, or replacement clients were added. A real `other_api` source still needs definition before it can return data.

### 5. Checking subgraph

- [x] Implement fetch → necessary checking calculations → worker evaluation → `ProductResult` with private state.
- [x] Compute only fields required by supported questions; retain trusted data and errors outside model control.
- [x] Verify: a checking balance query returns the fixture's exact balance and correct product identity.
- [x] Check in before adding other product branches.

Step 5 evidence: added a standalone compiled Checking graph, with an injected profile service and optional worker for offline tests. The only new calculation is the whole-dollar checking balance total. Five compiled-graph tests pass: balance/source preservation, retrieval failure, missing account, stale/pre-seed warnings, and rejection of model-supplied data. Failures return a result with zero confidence; exception details are not copied into the result. Added LangGraph 1.2.20; no other product branches, main graph, or routes were added. Model-written summaries still need the planned verification/grounding checks; live NVIDIA behavior remains untested.

### 6. Checking subgraph tests

Post-step-5 regression check: all 148 tests passed; `pip check` and diff checks passed. Step 6 will review independent branch coverage before proceeding to additional branches.

- [x] Test the compiled checking subgraph independently with deterministic model responses.
- [x] Cover successful retrieval, missing account, failed API, and malformed model output.
- [x] Verify: errors remain visible, missing data never becomes a fabricated zero balance, and failure does not become a confident answer.
- [x] Check in; do not wire the main graph until this passes.

Step 6 evidence: reviewed the five existing compiled-graph cases and added four gap cases: recovery after empty output, recovery after invalid confidence, provider connection failure with source-warning preservation, and a failed refresh after a successful invocation without old data leaking into the result. All 73 focused agent tests passed, including nine compiled Checking cases; diff checks passed. No production code or dependencies changed. Live NVIDIA tests remain deferred; tests use deterministic workers and fixture profiles. The main graph remains unwired.

### 7. Remaining subgraphs

- [x] Build and test Savings; use existing account/goal fields.
- [x] Build and test Credit Card; handle profiles without a card.
- [x] Build and test Loans; distinguish recorded loan balance from a payoff quote when no quote exists.
- [x] Build and test Other Data with a validated worker source-selection decision and only the selected sources.
- [ ] Define what “other API” means for Waypoint before adding an integration; no provider has been specified, so this integration remains deferred with an explicit unavailable result.
- [x] Verify each branch's success, empty-data, and failure behavior, including parallel Other Data fetches merging correctly.
- [x] Check in after each branch, keeping common code limited to actual shared behavior.

Savings check-in: 81 focused tests passed, including eight new Savings cases and all nine existing Checking cases; diff checks passed. Checking and Savings now share the existing retrieval/evaluation implementation in `subgraphs/account.py`, with their public builder functions unchanged/separate. Savings computes `balance_total` and nonnegative `goal_remaining` from the linked goal's `target_amount` and `current_saved`; unrelated goals are omitted. Tests cover goal progress below/at/above target, missing accounts, unlinked goals, retrieval/model failures, and source warnings. No new dependencies, main graph, or other product branches were added. Live models and final summary grounding remain deferred.

Credit Card check-in (step 7): extended the existing shared account graph with a Credit Card builder. It preserves balances, limits, APR, and transaction records, computes only the existing balance total, and omits Savings goal calculations. The worker prompt distinguishes amounts owed from spendable cash and credit limits from available credit/payment due; live interpretation remains unverified. Profiles without cards return empty records with an explicit error, not a fabricated zero-debt answer. No dependencies or extra credit calculations were added.

Credit Card verification: all 88 focused agent tests passed, including seven new Card cases covering all four fixture profiles, failed retrieval, rejected model-supplied facts, and source warnings. Existing Checking and Savings tests passed unchanged; diff checks passed.

Loans check-in: added the Loans builder using shared account handling. Student/auto loan records retain balances, APR, repayment status, and payment fields. Code marks `payoff_quote` unavailable and appends an explicit notice to the result summary, including model-failure results with retrieved records. No payoff formula or new dependency was added. All 95 focused agent tests passed, including seven new Loans cases across all four fixture profiles; existing branches passed unchanged and diff checks passed. Live NVIDIA output and final grounding remain unverified.

Other Data check-in: added source selection, parallel selected-source fetches, and one joined evaluation. Each source keeps its own data/metadata; error lists merge without discarding successful source results. Empty/invalid selection and unconfigured sources return explicit zero-confidence results without fetching. Ten new compiled-graph tests passed, including a synchronization-barrier check proving parallel fetches join before evaluation, partial failure, source-warning preservation, bounded invalid output, and fresh state on repeated invocation. The full suite passed: 184 tests; diff checks passed. No dependencies, external provider, or main graph were added. Live NVIDIA behavior and user-facing grounding remain deferred.

### 8. Parent/subgraph boundary

- [x] Map trusted parent context into subgraphs and return only their results to the parent.
- [x] Use the profile from parent state initialized with the server-authenticated user; no global demo user ID. Actual API authentication enforcement is still due in step 13.
- [x] Verify: private state stays private and two different profiles yield isolated results.
- [x] Check in.

Step 8 evidence: added `make_subgraph_node` and `build_subgraph_nodes` in `backend/agent/graph.py`. Wrappers pass only query, trusted profile ID, verification feedback, and a refresh flag for incomplete verification; only `results` returns to the parent. Account subgraphs now receive the missing-data feedback already supported by Other Data. All 56 relevant wrapper/state/subgraph tests passed, including seven new wrapper cases testing all five compiled branches against two profiles and both initial/retry input mapping; diff checks passed. No main routing, API endpoints, checkpointing, or dependencies were added. Callers must still initialize state from the authenticated user; the wrapper itself is not an authentication boundary.

### 9. Query router

- [x] Implement validated single- and multi-product routing with verification feedback.
- [x] Handle vague or unsupported questions explicitly; honor requested re-fetch products without uncontrolled rerouting.
- [x] Verify: checking-only, savings-plus-loans, empty/invalid routing, and retry feedback cases using deterministic model responses.
- [x] Check in.

Step 9 evidence: added `eval_query` and `route_to_products`. Initial routing uses the planner with only the question, not identity/profile records. Empty routes and exhausted/provider failures retain an incomplete verification explanation and route to `gen_ui` without fetching a guessed product. Subsequent routing follows Verify's exact products and optional Other Data target without another model call; completed or untargeted decisions stop fetching. All 65 relevant tests passed, including 14 new router cases; diff checks passed. These tests verify routing mechanics, not live model classification quality. Main graph wiring in step 12 must allow `other_data` and `gen_ui` as router destinations, and Gen UI must preserve the no-match/failure explanation. No new dependencies or API endpoints were added.

### 10. Verification loop

- [x] Give Verify trusted data as well as summaries, errors, and source freshness.
- [x] Route missing product data and other-data requests; enforce the guide's maximum of three verification rounds.
- [x] Preserve unresolved questions and failures as caveats at the cap, rather than labeling incomplete data verified.
- [x] Verify: success, product re-fetch, other-data fetch, simultaneous needs, and bounded termination under repeated incomplete decisions.
- [x] Check in.

Step 10 evidence: added `verify` and `after_verify` in `backend/agent/nodes/verify.py`. Verify sends the planner the question and each full `ProductResult` (trusted data including metadata/freshness, errors, summary, confidence), never the profile or user ID. Provider/output failure becomes an incomplete decision with no fetch targets and only the exception type. At the third round, any remaining fetch request is dropped and `(Verification limit reached.)` is appended to the caveat, so the loop stops without marking the data verified. `after_verify` returns `eval_query` for any fetch need (the router already fans out to products and `other_data` together) and `gen_ui` otherwise; unlike the guide, there is no direct Verify→Other Data edge. The full suite passed: 212 tests, including seven new Verify cases. Live planner judgment remains untested. Step 12 must wire `verify → after_verify` with `eval_query` and `gen_ui` as destinations.

### 11. Generated UI (complete each substep with its own check-in)

- [x] **11a — Contracts:** obtain the actual frontend bar-chart schema; define only text and bar-chart models. Verify valid fixtures pass and unknown fields/invalid dimensions fail.

  11a evidence: the user supplied the frontend's bundled `ai-document.schema.json` (plus the individual bar, line, pie, histogram, scatter, Gantt, and text-block sources; the bundled bar-chart definition is identical to the standalone `BarChartSpec`). It is vendored verbatim at `backend/agent/ui/ai-document.schema.json` and enforced by `validate_document` in `backend/agent/ui/components.py` using `jsonschema` (added to requirements; the guide's step 1 already listed it). This replaces the guide's hand-written Pydantic mirrors and its `components`/`caveats` envelope: the real contract is `{"blocks": [...]}` with heading, paragraph, list, callout, stats, divider, chart, and non-nested row blocks, and no caveats field, so caveats must be emitted as blocks (for example, a small paragraph or callout). Code also rejects bar/line series whose value (or band) lengths don't match `categories`/`x`, which JSON Schema cannot express. 12 new tests pass (valid mixed document; unknown root/prop fields, the old `data` label/value format, unknown block type, empty/excess series, a nonzero bar axis minimum, nested and oversized rows, empty documents; bar and band dimension mismatches). Full suite: 224 passed; `pip check` passed. Pydantic models are not needed for 11a; the LLM-facing `UIPlan` is still planned for 11c. Only bar charts and text blocks will be produced at first; the other chart types validate but have no builders. The vendored file must be re-copied when the frontend schema changes.

- [x] **11b — Datasets:** compute the datasets needed for demo questions from trusted records, with date filters, whole-dollar arithmetic, and correct treatment of transfers/refunds. Verify exact totals and unchanged datasets through model evaluation.
- [x] **11c — Presentation plan:** define a small `UIPlan` limited to available dataset choices and at most three charts. Verify invalid choices cannot introduce data.
- [x] **11d — Builder:** assemble chart values, units, budget lines, and highlights in code. Verify the emitted values match source datasets, and balance-only answers need no chart.
- [ ] **11e — Frontend:** integrate with the actual frontend's component registry once its location and contract are known. Verify rendered text/charts, empty states, and safe handling of unknown component types. The real contract already uses the `categories`/`series` and `blocks` format, so no converter is needed.
- [x] **11f — Validation:** run schema and grounding checks before returning UI. Include text, titles, subtitles, and computed comparisons; the guide's dollar-token membership check alone cannot establish that a number describes the right account or fact. Verify fabricated/misattributed amounts are rejected, one regeneration is bounded, and a safe fallback preserves caveats.

11b–11f evidence: Gen UI builds on the frontend's AI document schema from 11a (`{"blocks": [...]}`), not the guide's `components`/`caveats` envelope.

- 11b: `backend/agent/ui/datasets.py` computes datasets at Gen UI time from trusted `ProductResult.data`; the subgraphs are unchanged and the model never sees or returns dataset values. Transactions from every branch are merged and deduplicated by ID. Spending is `flow_class == "expense"`, with inbound expenses (refunds) subtracted. Internal transfers (card/loan payments, goal contributions), non-cash interest, and income are excluded, so card spending is not double-counted through card payments. Datasets: `spending_by_category.<YYYY-MM>` per month (the date filter is choosing a month's dataset) and `income_vs_spending` by month. Descriptions name the account types covered, so a checking-only chart is not presented as all spending. `build_facts` provides every dollar figure the text may cite: product balances (liabilities labeled "owed"), the savings goal target, saved, and remaining amounts, each dataset value and total, and monthly income minus spending (the one computed comparison). The profiles contain no budgets, so no budget lines or budget facts exist.
- 11c: `backend/agent/ui/plan.py` defines `UIPlan` (answer, at most four stat fact keys, at most three `ChartChoice`s). The model picks dataset and fact keys and presentation options; extra fields are rejected.
- 11d: `build_document` in `backend/agent/nodes/gen_ui.py` copies categories and series from the dataset, sets whole-dollar currency formatting, drops highlights that aren't real categories, forces `sort: none` for time-period datasets, adds a caption paragraph per chart, renders stats tiles from code facts, and renders caveats (result errors plus an incomplete Verify explanation) as one warning callout.
- 11f: model text (answer, titles, subtitles, captions) must not contain digits; every number is a `{fact_key}` placeholder that code fills with the exact value. Unknown datasets, stats, or placeholders, and any typed digit, are rejected. This is stricter than the guide's dollar-token membership check: a correct-looking typed number is still rejected, and attribution is explicit through the fact key. One regeneration includes the problem list. On a second failure, a planner/provider error, or no results, a code-only fallback shows a fixed sentence, up to four balance/goal stats, and all caveats. A planner-written Verify caveat containing digits is replaced with a generic caveat. Every returned document passes `validate_document`.

Verification: 10 new tests in `tests/test_gen_ui.py`, using the primary demo profile, check: October category totals and ordering against an independent calculation; exclusion of transfers, interest, and income; refund subtraction; cross-branch deduplication; balance and goal facts; five kinds of invalid plan choices and plan size limits; chart values equal to source datasets, with datasets unchanged after the builder output is mutated; a balance-only answer producing stats and no chart; a raw number triggering exactly one regeneration; repeated ungrounded text falling back with caveats and without the fabricated amount; provider failure without leaking error text; no-result fallback without a model call; and numeric caveat replacement. Full suite: 234 passed; `pip check` and diff checks passed.

Limits: the model can still choose the wrong fact key for a sentence (for example, citing savings in a sentence about checking). Keys and labels are explicit, but no semantic sentence check exists. The no-digits rule may cause more regenerations or fallbacks with a live model; live Nemotron behavior is untested. Only bar charts, stats, paragraphs, and callouts are produced. 11e remains open: no frontend code is in this repository, so rendering, empty states, and unknown-type handling cannot be checked here. The backend emits only schema-valid blocks. Gen UI is not yet wired into the main graph (step 12).

### 12. Wire the main graph

- [x] Connect routing, product branches, verification, retry paths, Other Data, and final UI.
- [x] Use per-request state; add checkpointing only if required, with session ownership and isolation enforced.
- [x] Verify: graph structure matches the guide, parallel branches join before verification, retries consume current results, and the iteration cap terminates.
- [x] Check in.

Step 12 evidence: added `build_agent_graph(profiles, planner=None, worker=None)` in `backend/agent/graph.py`. Edges: START → `eval_query`; `eval_query` → any of the five branches or `gen_ui` (no match); every branch → `verify`; `verify` → `eval_query` (any re-fetch, including Other Data) or `gen_ui`; `gen_ui` → END. The Mermaid output matches the guide except for the step-10 decision to send Other Data requests through the router rather than a direct Verify → Other Data edge. No checkpointer is compiled in; each call must start from `initial_state(query, authenticated_user)`, so no thread or session state is shared across requests or users. Six new end-to-end tests run the real compiled subgraphs with fixture profiles and scripted planner/worker models: checking balance (one Verify, stats from code); savings + loans fanning out and joining into exactly one Verify call that sees both results; Verify requesting Other Data, re-fetching with `refresh=True` without rerouting, then producing a chart; repeated re-fetch requests stopping at three rounds, with the refreshed balance replacing the stale one and the limit caveat in the UI; no-match questions skipping fetch, Verify, and Gen UI planning; and an API failure surfacing as a caveat without leaking exception text. Full suite: 240 passed; diff checks passed. Live Nemotron routing/verification quality and an API entry point remain for step 13.

### 13. Run and integrate

- [x] Add the smallest agreed entry point; reuse current authentication if exposing an API endpoint.
- [x] Verify all seven guide scenarios: checking balance; savings versus loan balance/payoff availability; lower balance requiring transactions; API failure; vague query capped at three rounds; October spending chart; savings balance with text only.
- [x] Verify unauthorized requests cannot run against another profile; preserve current endpoint behavior.
- [x] Run relevant regression tests and separate deterministic outcomes from live Nemotron outcomes.
- [x] Check in with scenario results and remaining gaps.

Step 13 evidence: added `POST /api/me/agent` to the existing FastAPI app (`backend/api/app.py`). It reuses `current_user` bearer authentication and builds state with `initial_state(question, user)`, so the profile always comes from the signed-in user. The request body accepts only `question` (1–1000 characters, not blank); a `profile_id` field is rejected with 422. The response is the AI document (`{"blocks": [...]}`) already checked against the frontend schema. `create_app` gains an optional `agent` argument for tests; otherwise the graph is built at startup with the app's `ProfileService`, and models load only when a question arrives. No `main.py` or CLI was added.

Deterministic results (scripted planner/worker, fixture profiles, through HTTP as the stu-002 demo user; `tests/test_agent_api.py`, 9 tests):
1. Checking balance: stats tile with the exact balance and one Verify call.
2. Savings vs loan payoff: both branches run in parallel into one Verify call. stu-002 has no loan, so the UI shows the savings balance plus caveats for the missing loan account and payoff quote. A recorded loan with no payoff quote is covered by the Loans subgraph tests.
3. Lower balance: checking, then Verify requests transactions, Other Data runs, then Verify again; income vs spending chart.
4. API failure: HTTP 200 with a "Checking retrieval failed (ConnectionError)" caveat; the internal error text is not exposed.
5. Vague query: no fetch or Verify, and the clarification is shown. Repeated incomplete Verify decisions stop at three rounds with the limit caveat.
6. October spending: bar chart values and the stated total equal an independent calculation from the profile's October expense transactions.
7. Savings balance: text and stats only, no chart.

Authorization: the agent reads only stu-002 for the stu-002 token. Missing and forged tokens return 401 before any profile read. A body-supplied `profile_id` and blank questions return 422 without a profile read. Existing API tests are unchanged and pass. Full suite: 249 passed; `pip check` and diff checks passed.

Live Nemotron (2026-11-07, demo user stu-002, live Nessie, API on port 8001):
- Run 1 (worker `nemotron-3.5-lightning-30b-a3b`): every amount shown was exact (checking $1,653 and October spending $694 by category, matching `/api/me/accounts` and `/api/me/transactions`), but worker calls failed intermittently. The Lightning model is a reasoning model that usually returned empty content with `response_format`; the adapter then fell back to `guided_json`, which the endpoint rejects (`[400] unknown field guided_json`), surfacing as "evaluation failed (Exception)". When it did answer, source selection was wrong (no sources for an October spending question, 4 of 4). Disabling thinking mode did not help. The Super model answered the same request correctly 4 of 4 in 1–3 s.
- Run 2 (worker switched to `nemotron-3.5-super-vl-120b-a12b` in `.env`): no worker failures. Results: (1) checking balance ✅ stats, 33 s; (2) savings vs loan payoff ✅ savings stat plus no-loan caveat, 31 s; (3) "Why is my balance lower than usual?" ⚠️ router asked which balance; (4) vague ✅ clarification; (5) "Where did my money go in October?" ⚠️ router asked which account (run 1 routed all four products for the same question), so routing for cross-account questions is not consistent; (6) savings balance ✅ text plus stats, 35 s. API failure was not run live (covered offline).
- Router fix: the router prompt now sends spending/where-money-went/income questions to checking and credit_card, treats an unqualified "my balance" as checking, and reserves `products=[]` for topic-less, unsupported, or non-banking requests. Direct router check, 3 runs each: all six scenario questions routed identically every time (checking; savings+loans; checking+credit_card; []; checking+credit_card; savings), and "Transfer $50 to savings" and a weather question stayed []. Offline suite: 253 passed.
- Run 3 (fixed router, Super for both roles): (1) ✅ $1,653, 33 s; (2) ✅ savings $4,561 plus no-loan caveat, 23 s; (3) ✅ checking balance, October spending chart, income, and net facts, 46 s (routed checking only in this run); (4) ✅ clarification; (5) ✅ October chart with exact category values (dining $149, transport $122, shopping $120; $694 total), 68 s; (6) ⚠️ Verify's model call raised a provider `Exception`, so the code-only fallback showed the correct savings and goal tiles with a "Verification is unavailable" caveat (the same question passed in run 2). Provider errors are not retried by `structured()`, so one transient failure degrades the answer.
- Run 4 (after the calculate step, 2026-11-08): the six original scenarios still pass with Verify reading code-computed facts instead of raw records (20–57 s). The Simulation questions are recorded in `BANKING_AGENT_CALCULATE_PLAN.md` step 7: $100/day works, Christmas and dining need formula/prompt fixes, car loan correctly declines, weather is refused.
- Open from the live run: intermittent provider exceptions are not retried; Checking and Verify prompts are very large (about 110k and 121k characters, because full transaction lists are sent), driving 30–80 s answers; caveats are joined without sentence punctuation; the monthly spending total's stat label is too long.

### 14. Debugging and observability

- [x] Provide a minimal way to inspect branch execution, retries, and termination through graph events.
- [ ] If LangSmith is wanted, configure it through environment settings and settle which data may leave the app before sending traces.
- [x] Verify: execution path is observable and credentials or unnecessary personal data do not appear in logs/traces.
- [x] Check in; do not add another monitoring framework.

Step 14 evidence: added `run_agent(graph, state)` in `backend/agent/graph.py`, used by `POST /api/me/agent`. It streams LangGraph `updates` and `values` and logs one INFO line per node on the existing `waypoint.agent` logger: routed products, each branch's confidence and error count, each Verify round's done flag and fetch targets, and the final block types. It returns the same final state as `invoke`. It never logs the question, user or profile IDs, amounts, summaries, model reasoning, Verify's missing text, or exception messages. One new test runs a failing-then-retrying, capped request and checks the full logged path (three router/Verify rounds, the failed first fetch, the round-three stop with fetch targets cleared, Gen UI last) and the absence of the question, IDs, balance, model text, and the exception message. Full suite: 250 passed; diff checks passed. No monitoring framework, checkpointer, or `get_state` support was added (there is no checkpointer).

LangSmith remains off and unconfigured. Enabling `LANGSMITH_TRACING` would send full prompts, including account records, balances, and transactions, to LangSmith. Do not set it until it is decided which data may leave the app and whether to redact or use synthetic profiles only.

### 15. Connect real read-only data

- [x] Replace fixture-backed access with the existing `ProfileService`/Nessie retrieval path, one product at a time.
- [x] Preserve existing caching, snapshot fallback, pre-seed mode, warnings, and provenance.
- [x] Verify each product against an authorized profile, including unavailable Nessie and stale snapshots; ensure no bank write operations are invoked.
- [x] Run final regression checks and document setup, completed checks, and unresolved live/frontend checks.
- [ ] Final check-in after all required checks pass; blocked work stays explicitly open.

Step 15 evidence: no replacement was needed. Since step 4, every branch has read through `get_data` → `ProfileService.get`, and the API builds the graph with the app's own `ProfileService` (with `NessieGateway` when `NESSIE_API_KEY` is set). Fixtures were only ever injected in tests. Three new tests (`tests/test_agent_nessie.py`) run the full agent graph against the seeded fake Nessie server through the real `ProfileService` and `NessieGateway`:
- All four products plus Other Data for stu-001 return `data_mode: nessie` with no errors; each balance total and the transaction count match the Nessie-backed profile; every Nessie request made during the run is a GET.
- With Nessie returning 503 after a snapshot was saved, the branch serves the stale snapshot with zero confidence, and the UI shows "Nessie unavailable (NessieError); serving last snapshot" and the stale-snapshot caveat; still GET-only.
- An unseeded profile makes no Nessie requests and is labeled synthetic pre-seed data.

Fix made: `ProfileService` built the outage warning from the full exception text, which carried the Nessie request path (including the internal Nessie customer ID) and up to 300 characters of the upstream response body. That warning reached `/api/me/*` responses, the agent's model prompts, and the generated UI. It now records only the exception type (`Nessie unavailable (NessieError)`); full detail stays in the existing server log line. The existing retrieval test (which checks for "Nessie unavailable") passes unchanged. Other mapping warnings still name internal record IDs (for example, "account … is not in the id map") and reach the same places; they contain no credentials but were left unchanged.

README: replaced the outdated agent section with current setup, flow, data, grounding, output, logging, and status notes. Final regression: 253 passed; `pip check` and diff checks passed.

Still open (blocking the final check-in):
- Live Nemotron: no credentials or model IDs are configured, so step 1b's smoke test and live `ProductEvaluation` check, step 13's seven scenarios with real models, and live logs are unverified.
- Real Nessie: all checks here used the fake Nessie server; a run against the live Nessie API with a seeded demo profile is still needed.
- Frontend (11e): rendering, empty states, and unknown-type handling need the frontend code.
- LangSmith (step 14): off until it is decided what data may leave the app.
- Other API (step 7): undefined, returns an explicit unavailable result.

## Scope questions for the first check-in

1. Proposed scope: add this read-only agent to the existing Waypoint backend, using its authenticated profiles. Confirm or adjust before implementation.
2. Where is the frontend and its authoritative `BarChartSpec`? Without them, backend UI output can be built, but actual frontend validation/rendering cannot be marked complete.
3. Is NVIDIA access already configured locally, and are planner/worker model IDs chosen? Share model IDs only; keep keys in the local environment.

Deferred unless needed: self-hosted NIM, new provider integrations, extra chart types, autonomous write actions, simulations, a new frontend application, and generic agent frameworks. Clarify Other Data sources and external tracing when those steps are reached.
