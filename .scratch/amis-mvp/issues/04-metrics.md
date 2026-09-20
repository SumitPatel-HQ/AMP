# 04: Metrics

**What to build:** A researcher reads a plan's quality as numbers rather than by eye. Utility, completion, violations, planning time, and resource use, each returned as plain data that can go into a paper, a notebook, or a CSV.

This establishes the baseline the replanning comparison measures against later. Churn and explanation coverage are defined here but have no second plan version to compare against yet.

**Blocked by:** 03.

**Status:** ready-for-agent

- [ ] Mission utility is the sum of priorities across the deduplicated set of requests a plan schedules or has already completed, so a request that is both counts once
- [ ] The completion rate, violation count, planning time in milliseconds, and battery and storage utilisation relative to capacity are all computed
- [ ] Expired requests stay in the request pool and count against the completion rate, so a mission that loses everything cannot report perfect completion
- [ ] Every metrics result carries the request pool it was computed over, as both a size and an id set
- [ ] Churn and coverage fields exist and return null here, since no second version exists to compare against
- [ ] Metrics return a plain serialisable object with no UI dependency
- [ ] The demo script prints the metrics for the plan
