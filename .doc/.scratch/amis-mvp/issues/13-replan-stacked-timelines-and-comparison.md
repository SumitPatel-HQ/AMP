# 13: Replan, stacked timelines, comparison, and unscheduled lists

**What to build:** A reviewer clicks replan and sees the before and after side by side, with the moved request obvious, the executed work marked as untouchable, and everything each plan failed to fit listed with its reason.

This is the moment the research claim becomes visible rather than described.

**Blocked by:** 12.

**Status:** ready-for-agent

- [ ] Replanning works from the browser and sends the plan version currently displayed, so a stale view cannot overwrite a newer plan
- [ ] The initial and revised timelines stack vertically so they compare by eye without switching views
- [ ] Changed requests are marked on the revised timeline
- [ ] Frozen actions are drawn differently from unfrozen ones, so a reviewer can see what replanning was never allowed to touch
- [ ] Each timeline carries an unscheduled list beneath it showing the request id, priority, and reason code for everything that plan did not fit
- [ ] Unscheduled requests are not drawn on the timeline itself, since any position would imply a time they do not have
- [ ] A plan version conflict response appears as a readable message rather than a silent failure
