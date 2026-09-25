# 14: Decision trace panel, metrics panel, and trace to timeline linking

**What to build:** A reviewer reads why each request moved, inserted, or dropped, sees the two plans compared as numbers, and clicks any explanation to find the request it refers to on both timelines.

This completes the demonstration. After this ticket a reviewer can run the entire research claim from a browser with no terminal and no API documentation open.

**Blocked by:** 13.

**Status:** ready-for-agent

- [ ] A decision trace panel lists each change with its reason code and generated sentence, in chronological order
- [ ] A metrics panel compares the two plan versions side by side
- [ ] The request pool size appears beside every metric that depends on it, so a number is never read without its basis
- [ ] A comparison whose two sides used different request pools is flagged in the interface
- [ ] Churn and coverage render as not applicable when null, never as a zero or a perfect score
- [ ] Clicking a trace entry highlights the matching request on both timelines
- [ ] A reviewer completes the entire demo from the browser without opening a terminal or the API documentation
- [ ] One command starts the whole stack
