

# AMIS Frontend Redesign — Alignment Pass

Context:
- Prompt 1 is already implemented.
- Prompt 2 is already implemented.
- Do NOT redo them.
- Do NOT implement Prompt 3 yet.
- A generated AMIS concept image is attached. Use it as the primary visual reference.

Before editing:
1. Inspect the current frontend implementation.
2. Read `AMIS_REDESIGN_CONTEXT.md`.
3. Preserve all working functionality and existing backend/API behavior.

## Goal

Make the frontend clearly communicate:

Mission
→ Current Plan
→ Event
→ Impact
→ Replan
→ New Plan
→ Explanation
→ Evaluation

The current problem is comprehension, hierarchy, and density — not missing features.

The UI should feel like one dense mission-control workspace, not a collection of cards.

---

## Visual Target

Use the attached generated concept image for:

- overall hierarchy
- panel proportions
- density
- dark mission-control styling
- mission transition summary
- relationship between Requests, Map, Mission State, Timeline and Analysis

Do NOT copy fake text, timestamps, plan IDs, or example values from the image.

All displayed data must come from the real AMIS backend.

---

## Layout

Target roughly:

┌─────────────────────────────────────────────────────────────┐
│ AMIS | Mission | Time | Plan | Step | Event | Replan       │
├─────────────────────────────────────────────────────────────┤
│ PLAN BEFORE → EVENT → IMPACT → CURRENT PLAN                │
├────────────┬───────────────────────────┬────────────────────┤
│ REQUESTS   │            MAP            │ MISSION STATE      │
├────────────┴───────────────────────────┴────────────────────┤
│                    MISSION TIMELINE                        │
├────────────────────────────────────┬────────────────────────┤
│ IMPACT / DECISION CONTEXT          │ MISSION EVALUATION     │
└────────────────────────────────────┴────────────────────────┘

Do not reproduce exact dimensions blindly.

---

## Mission Transition Summary

Add a compact summary below the top bar.

Example:

PLAN V3
2/5 scheduled
    →
CLOUD_BLOCK · EVT-001
OBS-B / WIN-B-1
    →
IMPACT
1 action invalid
    →
PLAN V4
2/5 scheduled

Lifecycle variants:

- before event: current plan only
- after event: Plan → Event → Impact → Awaiting Replan
- after replan: Previous Plan → Event → Impact → Current Plan

Use real backend data only.

---

## Plan Context

Make plan context consistent across:

- top bar
- mission summary
- timeline header
- impact
- trace
- metrics

Avoid confusing mismatches like:

top bar = V4
timeline = V3
impact = PLAN-001
metrics = PLAN-003 → PLAN-004

unless clearly explained.

Do not change backend IDs.

---

## Requests

Keep the left panel compact.

Example:

OBS-A   P5   COMPLETED
OBS-B   P4   PLANNED
OBS-C   P3   UNSCHEDULED

Fix duplicated labels such as:

completed completed

Keep reason codes secondary.

Preserve request selection and map highlighting.

---

## Map

Prompt 2 is already implemented.

Do NOT rewrite the map.

Preserve:
- React-Leaflet
- current viewport logic
- targets
- satellite context
- selection/highlighting
- real API data

Only adjust layout/styling as needed.

---

## Mission State

Keep persistent telemetry visible:

- Battery
- Storage
- Availability
- Completed requests
- Active Event
- Simulation time
- Current MissionPlan

Keep it compact and scannable.

---

## Timeline

DO NOT implement Prompt 3.

Preserve the current timeline functionality.

Only:
- keep it in a dominant region
- fix surrounding layout/chrome
- ensure no clipping

Do NOT:
- redesign timeline internals
- add time axis
- add event markers
- add observation-window bands
- add Plan V1/V2 diff visuals
- deepen the current custom SVG implementation

The current hand-written SVG timeline is TEMPORARY.

Do not add new SVG-specific architecture.

Reserve space for the future timeline:

        10:00   10:15   10:30   10:45

OBS-A   █████
OBS-B      ░░████░░░
OBS-C           ░░░░░░

              │ NOW
                 ◆ EVENT

Reference only. Do not implement yet.

---

## Lower Analysis Area

Make Impact / Decision Context and Mission Evaluation feel related to the current mission transition.

Example:

IMPACT / DECISION CONTEXT
- Event
- Evaluated plan
- Invalid actions
- Relevant reason

MISSION EVALUATION
- Utility before/after
- Completion before/after
- Violations
- Resources

Do not deeply redesign comparison, trace, or metrics yet.

Improve only:
- hierarchy
- density
- empty states
- plan/event context

---

## Visual Rules

Prefer:

- dark operational UI
- compact spacing
- thin separators
- small section headers
- clear status colors
- minimal wasted space
- map + timeline dominance

Avoid:

- giant rounded cards
- excessive padding
- large blank areas
- oversized headings
- decorative gradients
- equal-weight panels
- generic SaaS-dashboard look

---

## Viewport

Treat AMIS as a fixed desktop mission-control workspace.

Use proper Grid/Flex with:

- `100dvh`
- `min-height: 0`
- `min-width: 0`
- internal scrolling where needed

Avoid body-level vertical scrolling.

Test:

- 1366×768
- 1440×900
- 1920×1080

Nothing should be clipped at the bottom.

---

## Preserve

Do not break:

- scenario loading
- requests/windows
- mission state
- map
- Generate Plan
- Step
- Event injection
- Impact
- Replan
- plan versions
- Decision Trace data
- Metrics
- TanStack Query/API integration

No mock data.

No backend redesign.

No polling.

---

## Acceptance Test

A reviewer should quickly answer:

1. What mission is running?
2. What plan is active?
3. What event occurred?
4. What did it affect?
5. Has replanning happened?
6. What is the satellite state?
7. Where are the targets?
8. Where will timeline analysis happen?

If these are not obvious, the redesign is incomplete.

---

## Validation

Run:

- frontend typecheck
- frontend build
- relevant frontend tests

Verify:

Load scenario
→ Generate Plan
→ Step
→ Inject Event
→ Inspect Impact
→ Replan

Check for:
- clipping
- incorrect plan context
- duplicated statuses
- stale UI
- broken queries

---

## Final report

Stop after this task.

Report:

- files changed
- main UI changes
- mission summary implementation
- plan-context fixes
- API gaps
- build/test results
- remaining issues before Prompt 3

DO NOT start Prompt 3.