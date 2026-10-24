# AMIS AI integration research

Date: 2026-09-29. Research only; no code changed.

## How to read this report

- **Question answered.** "How can we integrate AI into all this? How will the AI work, on which existing or future features will it work, and how will it impact the project?"
- **Scope.** Large language models (LLMs), machine learning (ML), reinforcement learning (RL), and onboard/edge AI, each tested against AMIS's locked design rules. It builds on `.doc/reference/amis-world-impact-research.md` (features A-I) and connects AI ideas to those features instead of repeating them. References to that report's sources use the form `[W-Sn]`.
- **Source tags.** Every external claim carries a source id `[Sn]`. The source table at the end says how each source was checked:
  - **Fetched**: I read the owning page or document (for papers, the arXiv abstract page unless stated).
  - **Excerpt**: a search-engine excerpt of the owning page. The page itself blocked fetching or was not fetched.
  - **Probe**: I called the live endpoint on 2026-09-29 and looked at the real response.
  - **Biblio**: only the bibliographic record was checked. The paper's content was not read.
- **UNVERIFIED** marks any claim I could not confirm from a primary source.
- **`[Repo]`** marks a claim about this repository, checked by reading the code.
- **`Recommendation:`** marks my own judgement, as distinct from sourced fact.
- **Effort scale** (same as the world-impact report):
  - **S**: one module plus tests, with no new ADR.
  - **M**: a new sub-package or new domain field plus an ADR, about the size of one wave.
  - **L**: changes a locked design rule, or spans several waves.

## 0. Short answer

- **How the AI would work.** In three layers, and nowhere else:
  1. **Advisory layer (LLMs).** A separate assistant service reads AMIS's existing API (traces, diffs, metrics, the request pool) and helps a person understand and drive the mission. It explains in plain language, drafts observation requests, and runs what-if comparisons. It never decides the plan. Every write goes through the existing validated routes after the user confirms it.
  2. **Archive-then-replay layer (ML models as offline producers).** A developer-run script runs a model (for example, an ML weather forecast or a cue-ranking model) and turns its outputs into *recorded MissionEvents* carrying evidence fields. This is exactly how weather already works under ADR-0012. Replay needs neither the model nor the network.
  3. **Planner-assist layer (learned heuristics).** A learned component may *propose* a starting point to the Planner, for example CP-SAT solution hints or a greedy ordering. Validation, the greedy-baseline fallback (ADR-0009), and ReasonCodes stay authoritative. Weights are pinned by checksum, and the planner's name and model hash are recorded on the MissionPlan.
- **Which features it touches.** DecisionTrace/PlanDiff explanation (existing), scenario authoring through `MissionBuilder` (existing), event injection and replan (existing), `CpSatPlanner` and `GreedyPlanner` (existing), weather-driven cloud blocks (existing, ADR-0012), and the future features A (cue replay), B (response latency), F (campaigns), G (training packs), and H (cloud-aware planning).
- **Impact.** AI makes AMIS easier to use and to teach, and it gives a stronger "human in the loop" demo. It also makes the research story sharper: "learned heuristics measured against a verified CP-SAT baseline, with every change still explained by a ReasonCode." The cost is real, though. The project's specs currently **forbid** LLM imports in the core and list RL as a non-goal (§1). Any AI work therefore starts with an ADR that amends those rules explicitly, instead of working around them quietly.

## 1. Design guardrails that decide where AI can go

These come from the repository. Several are stricter than the task brief assumed.

- `[Repo]` **LLMs are currently banned from the core, and a test enforces it.**
  - `tests/test_decision_trace.py:167` (`test_no_language_model_is_imported_anywhere_in_the_codebase`) fails if any file under `amis/` or `tests/` imports `openai`, `anthropic`, `transformers`, `llama_cpp`, `langchain`, `ollama`, `cohere`, or `google.generativeai`.
  - `amis/trace.py:6-8`: "No language model takes part, and the system must work with none present."
  - `.doc/specs/AMIS_Build_Spec.md:169` (story 84), `:425`, and `:529` repeat this rule. `.doc/specs/AMIS_Implementation_Guide.md:996` says "Do not use an LLM to decide the schedule."
  - `.doc/specs/AMIS_PRD.md:148-157` lists "reinforcement learning", "mandatory LLM integration", and "LLM-based planning" as non-goals: "An LLM must never be the core planning engine."
  - The door is left open on purpose: `AMIS_PRD.md:351` lists "optional local-LLM natural-language explanations" as a future extension. `AMIS_SRD.md:527` says: "An LLM is optional after the MVP and shall not be required to derive the planning reason."
  - **Consequence.** An LLM layer must either live *outside* `amis/` (a sibling package or service that talks to the HTTP API) or come with an ADR that amends the test and the Build Spec on purpose. `Recommendation:` the sibling approach. It keeps the ban literally true for the planning core, and the existing test keeps guarding it.
- `[Repo]` **Replay rule.** A replay is the pristine scenario plus the ordered event log (ADR-0002). External data follows archive-then-replay, and "the planner never sees weather" (ADR-0012). Anything a model produces that affects planning must enter as a recorded MissionEvent with evidence fields, or as a pinned, checksummed input stored with the scenario (the ADR-0008 pattern).
- `[Repo]` **Planner determinism.** CP-SAT runs single-threaded with `random_seed = 0` and `max_deterministic_time` (`amis/planning/cp_sat.py:432-435`, ADR-0009). The evaluation suite has blocking gates: `replay_equality`, `byte_identical_reruns`, `frozen_actions_identical`, and `zero_violations` (`amis/evaluation/runner.py:205-239`). It also blocks sockets during runs (`runner.py:44-60`). Every AI feature that touches planning must pass these gates unchanged.
- `[Repo]` **ReasonCodes are the authoritative record.** Trace sentences are rendered from a template per ReasonCode (`amis/trace.py:113`, `render_message`). Unscheduled reasons come from one shared helper (`_unscheduled_reason`, used at `amis/planning/greedy.py:281` and `amis/planning/cp_sat.py:558`). An LLM may rephrase this record. It may not add causes to it.
- `[Repo]` **Single test seam.** `MissionSession` is the facade every integration test drives (ADR-0001). Routes are thin adapters. `MissionSession.restore(...)` (`amis/session.py:536`) rebuilds a session from records, so a throwaway in-memory copy for what-if runs is already possible.
- `[Repo]` **Validation hooks already exist for machine-written input.** `POST /scenarios/validate` (`amis/api.py:210`, used by `frontend/src/panels/MissionBuilder.tsx:109`) previews a scenario without saving it. `POST /scenarios/{id}/events` (`amis/api.py:351`) validates event payloads through the session (`amis/session.py:293`). A model's output can be checked against the same rules as a human's input, with no extra code.
- `[Repo]` **No ML dependency today.** `pyproject.toml` lists FastAPI, SQLAlchemy, Alembic, Skyfield, SGP4, and `ortools==9.15.6755` only.

## 2. Where AI can sit: three integration tiers

| Tier | What runs where | Touches planning? | Determinism argument | Network at runtime |
| --- | --- | --- | --- | --- |
| **T1 Advisory sidecar** | LLM or assistant in a separate package or service (for example `assist/`, outside `amis/`) that calls the AMIS HTTP API | No. It reads records, and it writes only through existing routes after the user confirms | The core is unchanged. Assistant text is presentation and is never stored as a trace | Optional. Local model = none. Cloud API = only in this tier, behind a clear opt-in |
| **T2 Archive-then-replay producer** | A model runs in a developer script. Its output becomes recorded MissionEvents with evidence (model id, weights checksum, input hash, score, threshold) | Only through recorded events, like weather today | Replay reads the event log, so the model is never re-run (ADR-0002, ADR-0012) | None. The script may use the network, like `scripts/fetch_weather_archive.py` |
| **T3 Planner assist** | A pinned model (for example ONNX) inside `amis/planning/` proposes hints or an ordering. CP-SAT or greedy placement and `validate_plan` decide | Yes, but only as a proposal that the Planner verifies | Pinned weights plus checksum, CPU, single thread, deterministic compute flag, and a `byte_identical_reruns` gate. The fallback to the greedy baseline stays | None |

`Recommendation:` start in T1 and T2. Enter T3 only after an ADR, and only for hints and orderings, never for an end-to-end learned plan.

## 3. Candidate AI features

### AI-1. Grounded explanation assistant over DecisionTraces and PlanDiffs

**What it does.** The user asks "Why did REQ-004 move?" or "What did the payload outage cost me?" The assistant answers in plain language, citing trace ids, ReasonCodes, and times. It can also summarise a whole replan: "3 moved, 1 dropped; utility fell from 17 to 14 because of EVT-002."

**How it works in AMIS**
1. The assistant gathers a *closed evidence bundle* from existing routes: `GET /plans/{id}/traces` (`api.py:431`), `GET /plans/{old}/compare/{new}`, `GET /plans/{id}/metrics`, the event log, and the plan's `unscheduled` entries.
2. The prompt says: answer only from the bundle; every sentence must cite a trace id, event id, or metric name; if the bundle has no answer, say "no recorded reason." This is retrieval-augmented generation in its simplest form: the model is grounded in explicit retrieved records and not in its own memory [S38].
3. A **deterministic verifier** (plain Python, no model) checks the answer before display. Every request id, ReasonCode, time, and number it mentions must appear in the bundle. Any mismatch hides the answer and falls back to the template sentence from `trace.py`.
4. Frontend: an "Ask" affordance next to each trace row in `frontend/src/panels/PlanComparisonPanel.tsx:43-68`. The template sentence stays visible, and the assistant's text is labelled "AI paraphrase" under it.

**Serves.** The existing explanation core (DecisionTrace, PlanDiff), feature G (training packs, "why did my request drop?" requester view), and feature C (a fairness-driven move explained in the requester's terms).

**Determinism and offline.** T1 only. Traces, coverage, and the event log do not change. With a local model (llama.cpp or Ollama, §6) it runs offline. Ollama documents reproducible output with a fixed `seed` and `temperature: 0` [S26], but bit-identical output across different hardware and builds is **UNVERIFIED**, so assistant text must never be compared in determinism gates.

**Effort.** **S-M.** The verifier is the real work, plus a small frontend panel. No change to `amis/` if it is built as a sidecar.

**Risks.**
- Hallucination: LLMs produce "plausible yet nonfactual content" [S39]. The verifier and the template fallback are what keep this safe.
- Hard limit: a fluent paraphrase can still *imply* a wrong cause even when every id is correct (for example "because of clouds" when the code is `DISPLACED_BY_COMPETING_REQUEST`). Mitigation: the verifier also checks that the cause phrase maps to the cited ReasonCode's allowed cause vocabulary, taken from `_CAUSE_BY_REASON_CODE` in `amis/trace.py`.

**ADR.** Yes, a short one: "LLM text is presentation, lives outside `amis/`, is never persisted as a DecisionTrace, and must pass the verifier." It amends Build Spec story 84 without weakening the import ban.

---

### AI-2. Natural-language request and scenario authoring

**What it does.** "Image the Huelva fire area at priority 5 before 18:00 UTC tomorrow, with SAT-1 if possible" becomes a draft `ObservationRequest` (or an `EMERGENCY_TASK` payload), which the user reviews in `MissionBuilder`.

**How it works in AMIS**
1. The assistant calls the model with the request JSON schema, derived from `amis/api_schemas.py`, as a strict tool or structured output.
2. Guarantees differ by backend:
   - Anthropic's structured outputs "guarantee schema-compliant responses through constrained decoding" [S22]. But they do not support numerical constraints such as `minimum` and `maximum` [S22], so the priority range 1-5 and latitude/longitude bounds must still be checked afterwards.
   - llama.cpp converts "a subset of" JSON Schema to GBNF grammars that constrain output [S28].
   - Ollama accepts a JSON schema in `format` [S26].
3. The draft goes to `POST /scenarios/validate` (`api.py:210`) or through event validation (`session.py:293`). **AMIS's own validators are the gate, not the model.** On the orbital provider, emergency windows are computed at injection time (`session.py:322-328`), so the model never invents windows.
4. Place names ("Huelva") need geocoding. `Recommendation:` do not let the model guess coordinates. Resolve names from an offline gazetteer, or ask the user to click the map. The model's own coordinates would be a silent source of wrong targets.

**Serves.** Scenario authoring (existing), features A (turning free-text alert bulletins into draft emergency requests for review), F (a sentence like "every 5 days until …" expands into a campaign), and G.

**Determinism and offline.** T1. The *accepted* request becomes part of the scenario or the event log, which is the replay unit. How it was drafted does not matter to replay, so determinism is unaffected. `Recommendation:` record `authored_by: "assistant:<model-id>"` in a metadata field if provenance is wanted. It is optional and omitted when absent, like the cloud-block evidence keys.

**Effort.** **S.**

**Risks.** Wrong coordinates or deadlines that still pass validation; time-zone mistakes (AMIS requires timezone-aware times, per ADR-0012's normaliser rule). Mitigation: show a diff-style preview and require explicit confirmation.

**ADR.** Covered by the AI-1 ADR.

---

### AI-3. Operator copilot and what-if assistant (tool use over the API)

**What it does.** "What happens if SAT-2 loses its payload from 10:00 to 12:00? Compare greedy and CP-SAT." The copilot runs the what-if in a sandbox and reports the utility change, plan churn, the dropped requests, and their ReasonCodes. It changes the real mission only if the user says "apply."

**How it works in AMIS**
1. Tools map one-to-one onto existing facade operations: `inject_event`, `replan`, `compare_versions`, `get_metrics`, `get_traces`, `select_planner`. With the Anthropic API, Claude returns `tool_use` blocks, and the application executes them and returns `tool_result` blocks [S23]. `strict: true` guarantees schema-conforming tool calls [S23]. Local models with tool-calling support (for example Qwen3, which its card says "excels in tool calling" [S35]) can drive the same loop through llama.cpp's OpenAI-compatible server [S27] (tool-call quality on small local models is **UNVERIFIED** for this schema).
2. **Sandbox.** A new read-only route, for example `POST /scenarios/{id}/what-if`. It builds an in-memory `MissionSession` with `restore(...)` (`session.py:536`) from the stored records, applies the hypothetical event, replans, and returns diff, metrics, and traces *without persisting anything*. This is also what feature B's feasibility query needs. It is a non-AI building block, useful on its own.
3. Alternatively, expose the same tools as a Model Context Protocol server. MCP defines hosts, clients, and servers that offer "Tools: Functions for the AI model to execute" [S25]. Its principles say "Hosts must obtain explicit user consent before invoking any tool" [S25]. That fits the "confirm before apply" rule. Any MCP host (for example Claude Code or Claude Desktop) could then drive AMIS, with no chat UI to build.

**Serves.** Event injection, replan, and planner comparison (existing); features B (feasibility), C (trying fairness policies), E (conjunction what-ifs), and G (exercises with a coach).

**Determinism and offline.** Sandbox runs go through the same deterministic Planner, so the *numbers* the copilot quotes are reproducible even if its prose is not. Applied changes are ordinary recorded events. `Recommendation:` show the tool calls, not just the prose, so an examiner can re-run them by hand.

**Effort.** **M.** The what-if route is S. The agent loop, UI, and consent flow are M.

**Risks.**
- The agent could chain many writes. Mitigation: writes allowed only after an explicit "apply", one at a time, each shown as the event JSON.
- MCP tool descriptions "should be considered untrusted, unless obtained from a trusted server" [S25]. Keep the server local.

**ADR.** Yes. The sandbox route semantics: no persistence, and no id consumption, so the next real plan id is unaffected.

---

### AI-4. Learned planning assistance (hints, orderings, and a research-track learned planner)

#### AI-4a. CP-SAT solution hints: greedy first, learned later

**What it does.** Give CP-SAT a starting assignment so that its bounded, deterministic search starts from a good plan.

**Facts.**
- OR-Tools `CpModel.add_hint(var, value)` "Adds 'var == value' as a hint to the solver" [S1].
- Related parameters: `repair_hint` ("tries to repair the solution given in the hint… until the 'hint_conflict_limit' is reached"), `fix_variables_to_their_hinted_value`, and `debug_crash_on_bad_hint` [S2].
- Research on "predict-and-search" uses a GNN to "predict the marginal probability of each variable, and then search for the best feasible solution" near it. It reports primal-gap gains over SCIP and Gurobi on MILP benchmarks [S4]. More broadly, learning is used to replace "handcrafted heuristics" inside solvers, treating "generic optimization problems as data points" [S3].

**How it works in AMIS**
- `[Repo]` `CpSatPlanner.plan` already computes the greedy `baseline` plan (`cp_sat.py:411-412`) but does **not** pass it to the solver as a hint. The fallback only compares utilities after the solve (`cp_sat.py:442`).
- Step 1 (no AI, **S**): for each candidate `present` literal, `add_hint(present, baseline_selects_this_pair)`. This is deterministic, since same inputs give the same hint, and it gives CP-SAT a feasible start under the same `max_deterministic_time`.
- Step 2 (AI, **M**): replace or augment the greedy hint with a learned per-candidate score (a small GNN or gradient-boosted model over request, window, and satellite features). Train offline on AMIS's own evaluation cases and generated instances, and optionally on EOS-Bench (CC BY 4.0 [W-S42]). Export to ONNX and run with ONNX Runtime on CPU, with `use_deterministic_compute` set [S30] and `intra_op_num_threads = 1` [S30]. Record the model hash in `solver_details`, next to the existing `ortools_version`, `seed`, and `max_deterministic_time` (`cp_sat.py:473-482`).

**Determinism.** Hints change the search path, so after step 1 plans may differ from today's for the same inputs. Evaluation fixtures in `amis/data/evaluation/planner_comparison/` would need regenerating once, deliberately. Reruns stay byte-identical. ONNX Runtime's flag only makes compute deterministic "where possible" on GPU kernels (Excerpt of ORT docs; the Python API page says only "Whether to use deterministic compute" [S30]). PyTorch states that "completely reproducible results are not guaranteed across PyTorch releases, individual commits, or different platforms" [S32]. `Recommendation:` run inference on CPU only, and quantise scores to integers before they enter the model, so tiny floating-point differences cannot flip a hint. The `byte_identical_reruns` gate then proves it on each machine.

**Serves.** The planner comparison (`amis/evaluation/comparison.py`), feature I (EOS-Bench), and larger scenarios from features A and F, where CP-SAT hits its deterministic limit and falls back (`solver_details.fallback`).

**Effort.** Step 1 **S**. Step 2 **M**.

**Risks.** A learned hint can make results *worse* inside a fixed work budget. The existing rule, "a CP-SAT plan never scores worse than the greedy plan" (ADR-0009), still guards utility. Report the hint's effect honestly with `optimality_gap`.

**ADR.** Step 1: an amendment note to ADR-0009. Step 2: a new ADR on "pinned learned artefacts" (checksum, CPU-only, integer-quantised outputs, recorded on the plan).

#### AI-4b. Learned greedy ordering

**What it does.** `GreedyPlanner` orders requests by `(-priority, deadline, duration_s, id)` (`greedy.py:159-167`). A learned scoring function could order them better, for example by weighing window scarcity or slew cost, while placement and validation stay exactly as they are.

**How.** A new planner name, for example `"greedy_learned"`, registered in `amis/planning/selection.py` and recorded as `planner_name` (ADR-0009). Unscheduled reasons still come from `_unscheduled_reason`, so ReasonCodes remain honest. The model only changes the *order in which requests are tried*, which is exactly what the stability rule (ADR-0004) already reasons about.

**Effort.** **M.** **ADR.** The same pinned-artefact ADR as AI-4a.

**Risk.** Plan churn. A learned order could reshuffle unaffected requests on every replan. The stability rule (the previous window sorts first while it stays valid) must be applied *before* the learned order, and churn must be reported next to utility.

#### AI-4c. A learned planner (RL, GNN plus search) as a research track

**Facts from the literature**
- Jacquet et al. combine GNNs with deep RL to drive search for oversubscribed EO satellite planning, plus MCTS refinement. They report that the approach can "learn on small problem instances and generalize to larger real-world instances" (IWPSS 2025) [S5]. The abstract does not report a comparison with CP or MILP solvers.
- Herrmann & Schaub compare DQN, A2C, PPO, shielded PPO, and MCTS-trained policies against a genetic algorithm on resource-constrained EO satellite scheduling [S7]. A related journal paper is in *IEEE TAES* 59(5), 2023 [S8] (Biblio only).
- Mercado-Martínez et al. use deep RL for the agile EO scheduling problem with time-dependent profits, reporting fewer low-quality captures (">60%") and less manoeuvre energy waste (up to 78%) [S6]. These results are against their own baselines, not CP-SAT.
- BSK-RL (MIT licence [S9]) provides Gymnasium environments for spacecraft tasking on top of the Basilisk simulator (ISC licence [S10]).
- A 2025 JPL-affiliated study reports that RL and imitation-learning planners beat a heuristic baseline by 13.7% and 10.0% on average for dynamic targeting [S11].

**Honest comparison with CP-SAT (Recommendation).** For AMIS-sized instances (a few satellites, tens of requests, hours to days), CP-SAT already returns `OPTIMAL` or `FEASIBLE` with a recorded bound and gap. A learned policy cannot prove optimality, has no gap, and would need its own ReasonCode story. The literature above generally compares against heuristics or GAs, not an exact solver with a certified bound. **Whether a learned planner beats CP-SAT on AMIS instances is UNVERIFIED and, in my judgement, unlikely at this scale.** Its real value would be speed on very large instances (thousands of requests, as in EOS-Bench [W-S42]) and onboard use (AI-6).

**How it could fit anyway.** As a third Planner behind the same protocol (ADR-0004), with its output passed through `validate_plan` and `_explain`, and the greedy-baseline fallback kept. It is useful as a *baseline row* in the comparison report, not as the default.

**Effort.** **L**. It reopens PRD non-goals (RL is listed as a non-goal, `AMIS_PRD.md:148`). **ADR.** Yes, and a PRD amendment.

---

### AI-5. ML weather forecast feeding cloud-block events (archive-then-replay)

**What it does.** Today the weather archive is Open-Meteo *reanalysis* (`scripts/fetch_weather_archive.py:41`, `archive-api.open-meteo.com`). That is hindsight: it knows what the sky actually did. A planner in the real world only has a *forecast*. AI-5 adds an ML forecast source, so a scenario can show "planned against the forecast, disrupted by the actual weather."

**Facts.**
- ECMWF's AIFS became operational on 25 February 2025 as "the first fully operational weather prediction open model using machine learning". It "outperforms state-of-the-art physics-based models for many measures", with "a reduction of approximately 1,000 times in energy use for making a forecast" [S17].
- AIFS output is licensed "Creative Commons CC-4.0-BY… and also the ECMWF Terms of Use" [S18].
- Probe: Open-Meteo's forecast API with `models=ecmwf_aifs025_single&hourly=cloud_cover` returned 24 hourly cloud-cover values for a Huelva point on 2026-09-29, while `ecmwf_aifs025` returned nulls [S19]. Open-Meteo's free API is non-commercial with CC BY 4.0 data and required attribution [W-S36].

**How it works in AMIS.** No new AI code runs inside AMIS. The ML model is ECMWF's, and AMIS only archives its output:
1. `scripts/fetch_weather_archive.py` gains a `--source forecast:ecmwf_aifs025_single` option that archives the forecast issued before the scenario start, with the issue time in the manifest.
2. The pure threshold rule (`amis/weather/threshold.py:57`) is unchanged. The `source` evidence field says `"ecmwf_aifs025_single forecast issued <time>"`.
3. Two event families become possible: "forecast cloud block" (known at plan time) and "actual cloud block" (from reanalysis, injected at the window time). Their difference is a teachable forecast-error story.

**Serves.** ADR-0012 weather events (existing), feature H (cloud-aware planning). This is the honest input H would need, still without the planner seeing weather. Also features A, D, and G ("cloud-heavy week" pack).

**Determinism and offline.** T2. The same as ADR-0012.

**Effort.** **S** for the archive source. **M** if H's planner-side use is added later, and that part still breaks "planner never sees weather" and needs its own ADR, as the world-impact report said.

**Risks.**
- AIFS cloud cover "displays a noticeably coarser spatial resolution" than other fields (ECMWF newsletter, Excerpt; **UNVERIFIED** in full text).
- A 0.25° grid judging a minutes-long window is even coarser than today's reanalysis. The evidence fields must show this, as ADR-0012 already requires.
- A *self-trained* cloud-forecast model is **not recommended**: it would be a worse copy of AIFS and add a training pipeline for no gain.

**ADR.** An amendment to ADR-0012 (a forecast versus reanalysis source label).

---

### AI-6. Simulated onboard AI: "onboard cloud screening discards the image and frees storage"

**Facts.**
- ESA Φ-sat-1 (launched 3 September 2020) demonstrated "filtering out less than perfect images so that only usable data are returned to Earth" [S13]. Its CNN, CloudScout, ran onboard on an Intel Myriad 2 VPU, and cloudy data was discarded before downlink [S14] (Excerpt; the MDPI page returned 403).
- ESA Φsat-2 (launched 16 August 2024) runs a KP Labs app that can "automatically detect and discard any of the images… where clouds have obscured the view of Earth." It is designed "as a service to support other onboard applications" [S15]. Φsat-2 hosts six onboard applications [S16] (Excerpt).
- NASA JPL's Dynamic Targeting uses "lookahead imagery… to detect clouds… to drive higher quality near nadir imaging". It was prepared to fly on CogniSAT-6, launched March 2024 [S12]. A learning-based follow-up is [S11]. The "<90 seconds, no human input" flight claim appears only in a vendor news release, so it is **UNVERIFIED** from a primary source.

**What it would do in AMIS.** A new MissionEvent, for example `ONBOARD_DISCARD`: at the end of an imaging action, a simulated onboard classifier marks the image unusable. Effects:
1. Storage charged by that action is released immediately, which is the point of onboard screening.
2. The request is *not* completed. It returns to the RequestPool as pending if its deadline allows, and the next replan re-places it.
3. A new ReasonCode, for example `IMAGE_DISCARDED_ONBOARD`, explains the insertion.

**How it works technically.** No real neural network is needed in the simulator. The discard decision is a *recorded* event with evidence (`classifier: "phisat2-style cloud screen (simulated)"`, `cloud_fraction`, `threshold`, `source` = the same weather sample that ADR-0012 uses). It is generated offline by a pure rule from the weather archive, exactly like cloud blocks. `Recommendation:` do not embed a real onboard model. AMIS has no imagery (image processing is a PRD non-goal, `AMIS_PRD.md:146`).

**Design conflict (important).** `[Repo]` Today an action whose start time has passed is Frozen and may never be moved or recosted (ADR-0003). Completion is permanent in the MissionState completed sets. An onboard discard "un-completes" a request. That reopens the one-way completion rule in the same way that ADR-0011 reopened the one-way resource rule for downlinks. It needs an ADR that says:
- the frozen action stays in the plan, and is not edited;
- storage is released by the event, not by recosting;
- the request re-enters the pool as a *new attempt*;
- how utility counts it.

**Serves.** Downlink and storage realism (ADR-0011), the cloud-block work (ADR-0012), feature D ("archive-first", a related "don't waste downlink" story), and feature G. It gives the demo a vivid "the satellite decided for itself" moment that is still fully explained.

**Effort.** **M** (one event type, one ReasonCode, one ADR, the pool re-entry path).

**Risk.** Utility semantics: is a discarded-then-retaken request counted once? It must be, because mission utility deduplicates by request.

---

### AI-7. AI-assisted cue triage for feature A

**What it does.** Feature A turns archived alerts (USGS, GDACS, CEMS, FIRMS) into `EMERGENCY_TASK` events. Its open question 1 was *which priority and deadline each alert gets*: "No source prescribes this" [world-impact report §5]. AI could help in two ways.

1. **ML scoring of structured fields** (for example USGS `sig`, `mmi`, `alert`, GDACS `alertscore` [W-S11][W-S13]) into a suggested priority. `Recommendation:` do *not* train this. The upstream fields are already model outputs. PAGER provides "fatality and economic loss impact estimates" [S43], and GDACS publishes an `alertscore` [W-S13]. A second model on top only hides the policy. A transparent lookup table in `amis/cues/rules.py`, recorded in an ADR, is better.
2. **LLM extraction from free-text bulletins** (for example a Charter or CEMS activation description) into a *draft* cue: coordinates, time, hazard type, AOI. This runs offline in the cue-archive script (T2) with structured output (AI-2 mechanics). The extracted fields are archived with `extracted_by: <model-id, weights sha256>` and reviewed by a person before they become recorded events.

**Determinism and offline.** T2. The event log carries the result, and replay never re-runs extraction.

**Effort.** **S** on top of feature A's M.

**Risks.**
- Fairness and ethics: an ML priority for disasters encodes whose disaster "matters more." It must be a visible policy, never a hidden model. This is the same argument as feature C's fairness measure.
- Licence: GDACS reuse is **UNVERIFIED** [W-S14].

**ADR.** Part of feature A's ADR. It should state that "no learned model sets priority."

---

### AI-8. Anomaly detection on simulated resource telemetry

**What it does.** Flag unusual battery or storage behaviour in the simulated resource walk (for example, a drop larger than any scheduled spend) and suggest the matching MissionEvent to the operator.

**Facts.**
- NASA JPL's Hundman et al. used LSTMs with nonparametric dynamic thresholding on labelled SMAP and Curiosity telemetry to "lessen the monitoring burden placed on operations engineers" (KDD 2018) [S40].
- ESA-ADB (2024-2025) is a benchmark with real annotated ESA mission telemetry. It found existing methods insufficient for operational needs [S41].
- scikit-learn's `IsolationForest` (Liu, Ting & Zhou 2008) gives reproducible results when `random_state` is an int [S42].

**Honest assessment (Recommendation).** In AMIS, resource telemetry is *generated by AMIS itself*. Every change is caused by a scheduled action, sunlight recharge, a downlink, or a recorded event such as `BATTERY_DROP`. So anomaly detection would only find what the simulator was told to inject. It is circular, and it adds little beyond a rule ("residual = observed − projected"). **Drop it as a core feature.** It becomes meaningful only if AMIS imports *real* telemetry, for example ESA-ADB [S41] as replay input. That is a different product.

Useful small remnant (**S**, no ML): a "projection residual" check in `amis/metrics.py` that compares `ResourceProjection` with the stepped `MissionState`. This is a correctness guard for ADR-0013's recharge model, not an AI feature.

A **terminology note**: CONTEXT.md lists "anomaly" as an *avoided* synonym for MissionEvent. A detector finding must not be called a MissionEvent. It should *suggest* one.

---

### AI-9. Evaluation: measuring AI features with AMIS's metrics

| Feature | Existing metric used | New metric proposed | Gate |
| --- | --- | --- | --- |
| AI-1 explanations | Explanation coverage (must stay 1.0; LLM text never counts) | **Grounding precision**: the share of AI answers that pass the verifier; **fallback rate** | The verifier is deterministic. A fixed question set per evaluation case under `amis/data/evaluation/explanation/` |
| AI-2 authoring | none | **First-pass validity**: the share of drafts accepted by `/scenarios/validate` without edits; **field accuracy** against a hand-labelled set | Offline test set; model outputs recorded as fixtures (record-and-replay, so CI needs no model) |
| AI-3 copilot | Utility, churn (reported *by* the copilot) | **Numeric fidelity**: the copilot's quoted numbers equal the sandbox's returned numbers | Same as AI-1's verifier |
| AI-4 hints and ordering | Mission utility, plan churn, `optimality_gap`, `fallback` rate, `planning_time_ms` | **Utility at equal deterministic budget**; **churn per disruption** | All four existing gates, plus a model checksum check |
| AI-5 forecast events | Utility, churn | **Forecast-induced churn**: the churn caused by actual-versus-forecast blocks | `replay_equality` with the socket guard (`tests/test_weather_replay.py` pattern) |
| AI-6 onboard discard | Utility, storage utilisation, downlink volume | **Storage saved by discard**; **re-acquisition latency** (feature B's metric) | Same as the existing event cases |

`Recommendation:` AI outputs used in tests are *recorded fixtures* (the model id, prompt hash, and output stored as JSON). CI then stays offline and deterministic, and a "live model" evaluation is a separate, opt-in script. This mirrors how weather archives are committed.

## 4. Ranked shortlist (impact to effort, given the constraints)

1. **AI-4a step 1 + AI-3's sandbox route: greedy-hinted CP-SAT and a non-persisting what-if endpoint. Effort S + S.**
   - Neither is "AI" yet, but both are the foundation every AI feature needs. Hints are the only safe entry point for learned planning [S1][S2]. The sandbox is the only safe way for an agent to explore.
   - Both are deterministic, testable through `MissionSession`, and useful on their own (feature B's feasibility query rides on the sandbox).
2. **AI-1: Grounded explanation assistant (T1 sidecar, verifier-gated). Effort S-M.**
   - Highest visible value per unit of effort. It answers "why did my request move?" in plain language while ReasonCodes stay the record.
   - It fits the door the PRD left open ("optional local-LLM natural-language explanations", `AMIS_PRD.md:351`) and keeps the import-ban test green by living outside `amis/`.
   - It runs fully offline with an Apache-2.0 or MIT local model (§6).
3. **AI-5: AIFS forecast archive as a second cloud source. Effort S.**
   - A real, operational ML model [S17] with an open CC BY 4.0 licence [S18], verified live through Open-Meteo [S19], added with zero new runtime code. It is ADR-0012's pipeline with a new `source`.
   - It creates the forecast-versus-actual story that feature H needs.
4. **AI-6: Simulated onboard cloud screening event. Effort M.**
   - The strongest *space-AI* story, grounded in flown missions (Φ-sat-1 [S13], Φsat-2 [S15], CogniSAT-6 DT [S12]).
   - It ranks below 1-3 because it reopens completion semantics (an ADR on par with ADR-0011).
5. **AI-3: Operator copilot (tool use or MCP). Effort M.**
   - Strong demo and training value (feature G), but it depends on #1's sandbox and #2's verifier, and needs a consent UI [S25].

Honourable mentions:
- **AI-2 (NL authoring)**: S. Cheap once #2 exists. Best paired with an offline gazetteer.
- **AI-4a step 2 / AI-4b (learned hints and ordering)**: M. A good research contribution *if* measured at equal deterministic budget against the greedy-hinted baseline.
- **AI-7 (LLM bulletin extraction)**: S on top of feature A. The priority mapping stays a rule, never a model.

Not recommended now:
- **AI-4c (learned end-to-end planner)**: L. It reopens a PRD non-goal and is unlikely to beat CP-SAT at AMIS's scale (UNVERIFIED).
- **AI-8 (anomaly detection)**: circular on simulated telemetry.

## 5. How AI changes the project

### Architecture

```
            +-------------------- assist/ (NEW, outside amis/) --------------------+
 user ----> | chat / "Ask" UI -> LLM (local llama.cpp/Ollama, or opt-in cloud API)  |
            |      |  tool calls (validated JSON)        ^ answers                    |
            |      v                                     | deterministic verifier     |
            +------|-------------------------------------|---------------------------+
                   v HTTP (existing routes + /what-if)   |
            +-------------------------- amis/ (core, unchanged rules) -------------+
            | MissionSession -> Planner (greedy | cp_sat [+ hints]) -> validate_plan |
            | -> diff -> build_traces (ReasonCode templates) -> metrics            |
            +-----------------------------------------------------------------------+
                   ^ recorded MissionEvents (with model evidence)
            +------|---------------- scripts/ (developer-run, may use network) -----+
            | fetch_weather_archive --source aifs | build_*_events | cue extraction  |
            +-----------------------------------------------------------------------+
```

- `amis/` keeps its no-LLM test. The only ML that may enter `amis/` is a pinned, CPU-only ONNX scorer for hints (T3), and only after an ADR.
- The assistant is a client of the API, as the frontend is. ADR-0001's rule, that routes hold no logic, also covers AI: no route calls a model.
- New ADRs expected: (1) AI layers and the LLM presentation boundary (amends Build Spec story 84 and PRD non-goals); (2) the sandbox what-if route; (3) the ADR-0009 hint amendment; (4) pinned learned artefacts; (5) onboard discard and completion semantics; (6) the ADR-0012 forecast-source amendment.

### UX

- "Ask why" on every trace row. The template sentence always stays visible, and AI text is labelled.
- A copilot drawer with "Try it (sandbox)" versus "Apply". The event JSON is shown before apply.
- A plain-language request box that fills `MissionBuilder` fields and never saves directly.
- An "onboard AI" badge on discard events in the timeline and `EventControl.tsx`.

### Demo story

1. Load the "Huelva wildfire" Example (feature A). Ask, "Add an urgent image of the fire front before 16:00." The assistant drafts an `EMERGENCY_TASK` and validation shows its windows.
2. Replan and ask, "Why did REQ-003 drop?" The answer cites `TRACE-007` and `DISPLACED_BY_COMPETING_REQUEST`, and the verifier's green tick shows it is grounded.
3. Inject the AIFS-forecast cloud blocks, then the actual reanalysis blocks, and show forecast-induced churn.
4. The onboard screen discards a cloudy image. Storage is freed, the request is re-placed, and it is explained by a new ReasonCode.
5. The closing line: "Every number came from the deterministic core. The AI only drafted, asked, and explained, and the event log replays byte-identically with the network unplugged."

### Test strategy

- Keep `test_no_language_model_is_imported_anywhere_in_the_codebase` unchanged for `amis/`. Add the mirror test for `assist/`: no import of `amis.planning` internals, so the assistant can only use the API.
- **Verifier unit tests** with adversarial fixtures: a wrong ReasonCode phrase, an invented request id, a wrong time.
- **Record-and-replay model fixtures**: CI never calls a model. A separate `scripts/run_ai_evaluation.py` runs live models and reports grounding precision and first-pass validity.
- For T3: extend `byte_identical_reruns` to assert that the model checksum is on `solver_details`, and run the gate on two OS images (Windows dev and Linux Docker) to catch cross-platform float drift [S32].

### Dependencies and licensing

| Component | Licence | Verdict |
| --- | --- | --- |
| llama.cpp runtime | MIT [S27] | OK. Runs on CPU, OpenAI-compatible server [S27] |
| Ollama runtime | MIT (Probe) | OK |
| ONNX Runtime | MIT [S31] | OK for T3 scorers |
| Qwen3-4B | Apache 2.0 [S35] | **Recommended** small local model (tool calling claimed [S35]) |
| Qwen2.5-7B-Instruct | Apache 2.0 [S33] | OK, heavier |
| **Qwen2.5-3B-Instruct** | **`qwen-research`** [S34] | **Avoid.** A trap: a different licence from its 7B sibling |
| Phi-3.5-mini-instruct | MIT [S36] | OK, 3.8B parameters, 128K context [S36] |
| Llama 3.2 3B Instruct | Llama 3.2 Community License, gated, with an acceptable-use policy [S37] | Usable but adds gating and AUP obligations. Not preferred |
| BSK-RL / Basilisk | MIT [S9] / ISC [S10] | OK for research track AI-4c |
| s2cloudless | CC BY-SA 4.0 [S20] | Share-alike. Not needed, since AMIS has no imagery |
| CloudSEN12+ | CC0 [S21] | OK if ever needed |
| ECMWF AIFS output | CC BY 4.0 plus ECMWF Terms of Use [S18] | OK with attribution. Open-Meteo's free tier is non-commercial [W-S36] |
| OR-Tools | Apache 2.0 (Probe) | Already a dependency; hints need no new dependency |
| scikit-learn | BSD-3-Clause (Probe) | OK if a simple scorer is preferred over ONNX |

Model weights (several GB) should **not** be committed. Record them like orbital snapshots: a manifest with source URL, licence, and SHA-256, and a developer script that downloads and verifies them. This is the ADR-0008 pattern. Weight sizes for quantised 3-4B models are **UNVERIFIED** here.

### Cost

- **Local model: no per-call cost.** It needs RAM and CPU time on the laptop. Latency on a CPU-only student laptop is **UNVERIFIED** and should be measured before promising an interactive UX.
- **Cloud API (opt-in, T1 only).** Claude Haiku 4.5 costs $1 per million input tokens and $5 per million output tokens [S24]. Tool definitions add a system-prompt overhead (496 tokens for Haiku 4.5 with `auto`) [S24]. `Recommendation / estimate:` a trace question with a ~3,000-token evidence bundle and a ~300-token answer costs about $0.0045 on Haiku 4.5, so a 50-question demo costs about $0.25. This is my arithmetic from [S24], not a quoted figure.
- **Engineering cost** is the main cost: about one wave for #1-#3, and one more for #4-#5.
- **Maintenance cost:** model upgrades change assistant text. That is acceptable only because assistant text is never part of the replay unit or a test oracle.

## 6. Local versus cloud models

| Option | Offline | Structured output | Determinism note | Fit |
| --- | --- | --- | --- | --- |
| llama.cpp + GGUF model | Yes | JSON-Schema subset → GBNF grammar [S28] | Seeded sampling. Cross-hardware bit-equality **UNVERIFIED** | Best for the default offline build |
| Ollama | Yes | `format` takes a JSON schema [S26] | Docs: set `seed` and `temperature: 0` "for reproducible outputs" [S26]. Cross-hardware **UNVERIFIED** | Easiest developer setup |
| ONNX Runtime (non-LLM scorers) | Yes | n/a | `use_deterministic_compute` flag [S30]; use CPU and a single thread | T3 hint and ordering models only |
| Anthropic API (Claude) | No | Strict tool use and JSON outputs via constrained decoding [S22][S23] | Not reproducible by design; that is acceptable only in T1 | Opt-in "enhanced assistant", or offline T2 extraction whose outputs are archived |

`Recommendation:` ship the local path as default and the cloud path as an explicitly configured option. Cloud output enters AMIS state only through the same validated routes, or as archived T2 artefacts with the model id recorded.

## 7. Open questions

1. **Amending the no-LLM rule.** Will the project owner accept an ADR that keeps `amis/` LLM-free but allows an `assist/` sibling? The Build Spec acceptance line "No language model is imported anywhere in the codebase" (`AMIS_Build_Spec.md:529`) would need rewording to "in the planning core."
2. **Is RL still a non-goal?** `AMIS_PRD.md:148` lists it. AI-4c needs an explicit decision.
3. **Hint-induced fixture churn.** Adding greedy hints changes CP-SAT plans once. Is regenerating the planner-comparison fixtures acceptable, and should the hint be switchable (`hint: "none" | "greedy" | "learned"`) and recorded in `solver_details`?
4. **Onboard discard and completion.** Does a discarded image count toward completion rate? Is the retake the same request (deduplicated) or a new attempt id?
5. **Verifier strictness.** Should AI-1 reject any sentence without a citation (strict), or only reject mismatched citations (lenient)? Strict is safer for an examiner. Lenient reads better.
6. **Local model performance.** Which 3-4B model gives acceptable tool-calling accuracy on AMIS's schemas on a CPU-only laptop? This is UNVERIFIED and needs a small benchmark using the record-and-replay fixtures.
7. **Cross-platform float determinism for T3.** Does an ONNX scorer give identical integer-quantised outputs on Windows and in the Linux Docker image? It is UNVERIFIED until the gate runs on both.
8. **AIFS cloud-cover quality at target scale.** The coarseness claim is from an ECMWF newsletter excerpt only (UNVERIFIED). Is a 0.25° forecast meaningful for minutes-long windows, or only as a teaching contrast with reanalysis?
9. **CloudScout and "<90 s" claims.** The CloudScout paper (MDPI, 403) and the CogniSAT-6 timing claim (vendor release) should be read in full before being quoted in a presentation.
10. **Privacy and data egress for the cloud path.** If a user enables the cloud assistant, scenario coordinates leave the laptop. Should the assistant redact target names, or warn once per session?

## 8. Sources

| Id | Source (owning organisation) | URL | Check | Supports |
| --- | --- | --- | --- | --- |
| S1 | Google OR-Tools, `ortools/sat/python/cp_model.py` (`add_hint`, `clear_hints`) | https://github.com/google/or-tools/blob/stable/ortools/sat/python/cp_model.py | Fetched (source docstring) | CP-SAT solution hints API |
| S2 | Google OR-Tools, `sat_parameters.proto` | https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto | Fetched | `repair_hint`, `hint_conflict_limit`, `fix_variables_to_their_hinted_value`, `random_seed`, `max_deterministic_time` |
| S3 | Bengio, Lodi, Prouvost, "Machine Learning for Combinatorial Optimization: a Methodological Tour d'Horizon," arXiv:1811.06128 | https://arxiv.org/abs/1811.06128 | Fetched (abstract) | ML replacing handcrafted solver heuristics |
| S4 | Han et al., "A GNN-Guided Predict-and-Search Framework for Mixed-Integer Linear Programming," ICLR 2023, arXiv:2302.05636 | https://arxiv.org/abs/2302.05636 | Fetched (abstract) | Learned warm-start and predict-and-search; gains vs SCIP and Gurobi |
| S5 | Jacquet et al., "Earth Observation Satellite Scheduling with Graph Neural Networks and Monte Carlo Tree Search," IWPSS 2025, arXiv:2408.15041 | https://arxiv.org/abs/2408.15041 | Fetched (abstract) | GNN + DRL + MCTS for EO satellite planning; generalisation claim |
| S6 | Mercado-Martínez, Soret, Jurado-Navas, "An energy-efficient learning solution for the Agile Earth Observation Satellite Scheduling Problem," arXiv:2503.04803 | https://arxiv.org/abs/2503.04803 | Fetched (abstract) | DRL for AEOSSP; >60% and 78% figures |
| S7 | Herrmann & Schaub, "A comparative analysis of reinforcement learning algorithms for earth-observing satellite scheduling," *Frontiers in Space Technologies* (2023) | https://www.frontiersin.org/journals/space-technologies/articles/10.3389/frspt.2023.1263489/full | Fetched (summary) | DQN/A2C/PPO/SPPO/MCTS-Train vs genetic algorithm |
| S8 | Herrmann & Schaub, "Reinforcement Learning for the Agile Earth-Observing Satellite Scheduling Problem," *IEEE TAES* 59(5) (2023) 5235-5247 | https://hanspeterschaub.info/Papers/Herrmann2023a.pdf | Biblio (PDF text did not extract) | Existence of the journal RL paper |
| S9 | AVS Lab (CU Boulder), BSK-RL repository | https://github.com/AVSLab/bsk_rl | Fetched | Gymnasium environments for spacecraft tasking; MIT licence |
| S10 | AVS Lab, Basilisk repository licence | https://github.com/AVSLab/basilisk | Probe (GitHub licence API: ISC) | Basilisk licence |
| S11 | Breitfeld et al., "Learning-Based Planning for Improving Science Return of Earth Observation Satellites," arXiv:2509.07997 | https://arxiv.org/abs/2509.07997 | Fetched (abstract) | RL +13.7%, imitation learning +10.0% vs heuristic for dynamic targeting |
| S12 | Chien et al., "Flight of Dynamic Targeting on the CogniSAT-6 Spacecraft," arXiv:2509.05304 | https://arxiv.org/abs/2509.05304 | Fetched (abstract) | JPL dynamic targeting; cloud avoidance; CogniSAT-6 launched March 2024 |
| S13 | ESA, "Φ-sat" (Φ-sat-1) | https://www.esa.int/Applications/Observing_the_Earth/Ph-sat | Fetched | Onboard filtering of unusable images; launch 3 Sep 2020 |
| S14 | Giuffrida et al., "CloudScout: A Deep Neural Network for On-Board Cloud Detection on Hyperspectral Images," *Remote Sensing* 12(14) 2205 (2020) | https://www.mdpi.com/2072-4292/12/14/2205 | Excerpt (HTTP 403 on fetch) | CloudScout CNN on Myriad 2; cloudy data discarded |
| S15 | ESA, "AI for cloud detection" (Φsat-2) | https://www.esa.int/Applications/Observing_the_Earth/Phsat-2/AI_for_cloud_detection | Fetched | Detect and discard cloudy images; service to other apps; KP Labs |
| S16 | ESA, Φsat-2 launch and applications pages | https://www.esa.int/Applications/Observing_the_Earth/Phsat-2/New_satellite_to_show_how_AI_advances_Earth_observation | Excerpt | Launch 16 Aug 2024; six onboard apps |
| S17 | ECMWF, "ECMWF's AI forecasts become operational" (25 Feb 2025) | https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwfs-ai-forecasts-become-operational | Fetched | AIFS operational; skill and energy claims |
| S18 | ECMWF, "AIFS Machine Learning data" | https://www.ecmwf.int/en/forecasts/dataset/aifs-machine-learning-data | Fetched | AIFS output licence CC BY 4.0 plus ECMWF Terms of Use |
| S19 | Open-Meteo forecast API, `models=ecmwf_aifs025_single&hourly=cloud_cover` | https://api.open-meteo.com/v1/forecast?latitude=37.26&longitude=-6.95&hourly=cloud_cover&models=ecmwf_aifs025_single&forecast_days=1 | Probe (24 hourly values; `ecmwf_aifs025` returned nulls) | AIFS cloud cover is archivable through the existing Open-Meteo path |
| S20 | Sinergise / Sentinel Hub, s2cloudless repository | https://github.com/sentinel-hub/sentinel2-cloud-detector | Fetched | LightGBM pixel cloud detector; CC BY-SA 4.0 |
| S21 | CloudSEN12+ dataset card | https://huggingface.co/datasets/tacofoundation/cloudsen12 | Fetched | Cloud and shadow labels; CC0 |
| S22 | Anthropic, "Structured outputs" | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | Fetched | Constrained decoding guarantee; unsupported numeric and string constraints |
| S23 | Anthropic, "Tool use with Claude" | https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview | Fetched | `tool_use` / `tool_result` loop; `strict: true` |
| S24 | Anthropic, "Pricing" | https://platform.claude.com/docs/en/about-claude/pricing | Fetched | Haiku 4.5 $1/$5 per MTok; tool-use system-prompt tokens |
| S25 | Model Context Protocol specification (2025-06-18) | https://modelcontextprotocol.io/specification/2025-06-18 | Fetched | Hosts, clients, servers; tools; user-consent and tool-safety principles |
| S26 | Ollama, API documentation | https://github.com/ollama/ollama/blob/main/docs/api.md | Fetched; licence MIT by GitHub API Probe | JSON-schema `format`; `seed` + `temperature` for reproducible outputs |
| S27 | ggml-org, llama.cpp repository | https://github.com/ggml-org/llama.cpp | Fetched | MIT; CPU inference; OpenAI-compatible server |
| S28 | ggml-org, llama.cpp `grammars/README.md` | https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md | Fetched | GBNF grammars; JSON Schema subset conversion |
| S29 | Microsoft, ONNX Runtime documentation | https://onnxruntime.ai/docs/ | Fetched | Cross-platform inference; Python API |
| S30 | Microsoft, ONNX Runtime Python API summary (`SessionOptions`) | https://onnxruntime.ai/docs/api/python/api_summary.html | Fetched | `use_deterministic_compute`, `intra_op_num_threads` |
| S31 | Microsoft, onnxruntime repository | https://github.com/microsoft/onnxruntime | Fetched | MIT licence |
| S32 | PyTorch, "Reproducibility" notes | https://docs.pytorch.org/docs/2.14/notes/randomness.html | Fetched | No reproducibility guarantee across releases, platforms, CPU/GPU |
| S33 | Qwen, Qwen2.5-7B-Instruct model card | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct | Fetched | Apache 2.0 |
| S34 | Qwen, Qwen2.5-3B-Instruct model card | https://huggingface.co/Qwen/Qwen2.5-3B-Instruct | Fetched | `qwen-research` licence; 3.09B parameters; JSON output claim |
| S35 | Qwen, Qwen3-4B model card | https://huggingface.co/Qwen/Qwen3-4B | Fetched | Apache 2.0; 4.0B parameters; tool-calling claim |
| S36 | Microsoft, Phi-3.5-mini-instruct model card | https://huggingface.co/microsoft/Phi-3.5-mini-instruct | Fetched | MIT; 3.8B parameters; 128K context |
| S37 | Meta, Llama-3.2-3B-Instruct model card | https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct | Fetched | Llama 3.2 Community License; gated; acceptable-use policy |
| S38 | Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," arXiv:2005.11401 | https://arxiv.org/abs/2005.11401 | Fetched (abstract) | Grounding generation in retrieved records; provenance problem |
| S39 | Huang et al., "A Survey on Hallucination in Large Language Models," ACM TOIS, arXiv:2311.05232 | https://arxiv.org/abs/2311.05232 | Fetched (abstract) | "Plausible yet nonfactual content"; mitigation limits |
| S40 | Hundman et al., "Detecting Spacecraft Anomalies Using LSTMs and Nonparametric Dynamic Thresholding," KDD 2018, arXiv:1802.04431 | https://arxiv.org/abs/1802.04431 | Fetched (abstract) | NASA SMAP and Curiosity telemetry anomaly detection |
| S41 | Kotowski et al., "European Space Agency Benchmark for Anomaly Detection in Satellite Telemetry," arXiv:2406.17826 | https://arxiv.org/abs/2406.17826 | Fetched (abstract) | ESA-ADB; existing methods insufficient operationally |
| S42 | scikit-learn, `IsolationForest` documentation | https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html | Fetched; licence BSD-3-Clause by GitHub API Probe | Liu, Ting & Zhou 2008; `random_state` reproducibility |
| S43 | USGS, PAGER | https://earthquake.usgs.gov/data/pager/ | Fetched | PAGER gives fatality and economic-loss impact estimates (alert thresholds not on this page) |

Cross-references to `.doc/reference/amis-world-impact-research.md`: [W-S11] USGS GeoJSON feed, [W-S13] GDACS API, [W-S14] GDACS terms, [W-S36] Open-Meteo licence, [W-S42] EOS-Bench.

Licence probes (GitHub `/repos/{repo}/license`, 2026-09-29): ollama/ollama MIT, AVSLab/basilisk ISC, scikit-learn/scikit-learn BSD-3-Clause, google/or-tools Apache-2.0.
