Updated. No simple bullets now. Every answer is story plus tech.

File: `D:\LearningHub\CollegeProjects\AMP\amis_presentation.html` - 31,111 bytes, verified. Open by double click. Search filters all 68. Print saves PDF.

How to speak each answer from now:

**1. What is AMIS**

Say: AMIS plans satellite photo tasks, breaks the plan with controlled events, fixes it, and explains every change in codes, sentences, and scores.

Tech backup if pushed: input is a scenario with one satellite plus requests carrying priority, duration, deadline, and costs. Output is versioned plans with actions placed inside windows. The loop runs through windows, plan, step, event, impact, replan, diff, trace, metrics, each as a separate tested module. This is decision support, not flight control, which keeps it repeatable offline under PRD section 6 and SRD 22. Proof to open is PRD sections 2 to 5 plus `amis/demo.py:362`.

**3. Greedy in full**

Say: rank wishes by importance and urgency, put each in the earliest workable gap, keep the old spot if still good, give a clear reason if left out.

Tech backup if pushed: the sort key is minus priority, then deadline, then duration, then id in `amis/planning/greedy.py:118-126`, so ties never resolve at random. Starts tried are the window start clamped to now, the peak centered start when culmination placement is on and fits, then the instant right after each already placed action plus the settling gap, and only starts that still end inside the window survive. Checks run in the order containment, deadline, availability plus outage intervals, projected battery and storage through `check_commit` in timeline order, then overlap plus gap, and the first passing slot wins. Zero windows maps to an honest no window code rather than a generic fallback. Proof to open is `amis/planning/greedy.py:146-222` and `_candidate_starts_in_window`.

**4. CP-SAT in full**

Say: the same problem written as math with true or false picks plus integer times, solved with a proven engine under a fixed budget, never worse than greedy because it falls back.

Tech backup if pushed: time is normalized to integer seconds from scenario start, low is the ceiling of the max of window start, now, and origin, high is the floor of the min of window end, deadline, and scenario end minus ceiled duration. Each feasible window gets a bool present plus an integer start plus an optional interval, at most one per request, with a global NoOverlap over frozen plus optionals. Outages use before and after bools gated by present. Battery and storage use exact Fraction scaling to integers with an overflow guard, budgeted as state minus frozen committed, conservative on downlink release with gains kept through fallback. The objective maximizes priority times weight plus a small same window bonus scaled above any geometry penalty. Solver runs one worker, seed zero, deterministic time limit, and only OPTIMAL or FEASIBLE is accepted, else the greedy baseline is kept, with status, objective, bound, gap, fallback, and versions stored. Proof to open is `amis/planning/cp_sat.py:54-163`.

**9. Skyfield traps**

Say: the finder looks for peaks first, so clipped edges and odd peaks need care, which is why we clamp edges and verify with a second sampler.

Tech backup if pushed: events are 0 rise, 1 culmination, 2 set at about one second accuracy. Older behavior missed passes without a culmination inside the range, so code clamps open at start and end and pairs defensively. Multiple culminations in a row without a set are documented and must not be assumed as strict order. High thresholds near 45 to 70 degrees once returned wrong set times due to uneven halving, fixed in later releases, which matters directly to your 56 degree case. Guard is an independent one second sampler that must agree within two seconds plus generate twice equals JSON plus a ground track from the same elements. Proof is Skyfield api-satellites plus issues 550, 996, 1000, 1017 and `amis/orbital/geometry.py`.

All 68 in the file now follow this shape: one spoken story line in green, deep tech backup in dark, file proof in blue margin. Use search for frozen, churn, coverage, find_events, solver_details, WindowPolicy during the viva.
