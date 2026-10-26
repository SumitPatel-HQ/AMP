# Synthetic archive fulfillment walkthrough (D-01)

This is a **synthetic catalogue fixture**, not a historical scene or a real
imagery product. `example.org` is a placeholder source link. The digest is
synthetic. No product download or product-content verification occurs. Scene
cloud cover does not guarantee cloud-free target pixels. The profile explicitly
asserts the author's simulated sensor/product suitability.

Run from the repository root, with the existing development environment:

```powershell
.venv\Scripts\python -m scripts.archive_fulfillment_demo
```

The script loads `scenario.json`, generates the canonical synthetic windows,
plans, advances five minutes, injects the complete `event-input.json`, inspects
impact and the still-active old plan, then **explicitly** replans. OBS-B gains
the distinct archive outcome; its future imaging is released. OBS-A's already
started action and consumed resources stay intact. This fixture demonstrates
the transition, not D-02's real catalogue capacity-release Example.

To submit through the dashboard, load `scenario.json` with the mission builder,
plan, step five minutes, select **Event → Archive fulfillment**, and paste the
`payload` object from `event-input.json`. Record it, inspect the evidence, then
use Replan. The event time is the current simulated clock; do not shift the
fixture's acquisition/retrieval/profile dates to fit another mission.

The equivalent API operation is `POST /scenarios/SCN-002/events` with the full
contents of `event-input.json`, after creating this Scenario and planning and
advancing it to the same instant. Then inspect `/events`, `/impact`, `/requests`
and `/plans/{plan_id}/metrics`; separately POST `/replan` with the current
`expected_parent_plan_id`. Invalid/duplicate transitions record nothing.

Replay needs only the pristine Scenario and accepted event records; the
catalogue, archive files and network are unnecessary. Existing mission utility
and completion mean simulated acquisition. Archive fulfillment and the labelled
union-based total (planned/completed acquisition plus archive, once per request)
are reported separately. A historical plan excludes later archive transitions.
