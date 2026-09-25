# 06: Replan, plan comparison, decision trace, and replanning metrics

**What to build:** A researcher triggers replanning after a cloud block and gets a revised plan that leaves executed work untouched, moves the displaced request into a later window, says why in a readable sentence, and reports what the disruption cost.

This closes the adaptive loop and is the project's research demonstration. The four parts stay in one ticket because none of them is verifiable alone: a comparison with no trace explains nothing, and a trace with no metric measures nothing.

Follow ADR-0003 on validation scope.

**Blocked by:** 04 and 05.

**Status:** ready-for-agent

- [ ] Replanning freezes every started action, and each frozen action is identical in the new version
- [ ] Unfrozen actions rebuild from every unexpired unfrozen request, including ones the previous plan dropped
- [ ] When sorting candidate windows for a request, its previous window comes first if still valid, then the rest by earliest start
- [ ] Validation covers unfrozen actions only, so a plan cannot fail permanently over an action nobody can change
- [ ] A new immutable plan version is created naming its parent, and the previous version is not mutated
- [ ] Plan comparison keys on request id, never on list position, and reordering a plan's action list does not change the result
- [ ] Each request is classified unchanged, moved, inserted, dropped, or completed, with old and new start times on a move and a reason code on every entry
- [ ] Comparison works between any two versions, not only adjacent ones
- [ ] Every moved, inserted, and dropped result has a decision trace carrying a reason code from the fixed vocabulary, the triggering event, the broken constraint, the previous action, and the new action
- [ ] Trace messages render from templates keyed by reason code, and no language model is imported anywhere in the codebase
- [ ] Replanning time is recorded separately from initial planning time
- [ ] Churn counts changed unfrozen actions over unfrozen actions in the earlier version, and coverage counts changed actions with a trace over changed actions
- [ ] Churn and coverage both return null when their denominator is zero, never a score
- [ ] The canonical demo runs: the request scheduled at 10:20 in version 1 sits at 11:15 in version 2, the reason is that its window was invalidated, coverage reaches 1.0, and churn stays near zero because nothing else moved
- [ ] When no later window fits, the request is dropped with the no alternative window reason instead
- [ ] Replanning with no event injected produces a new version identical to its parent, with a churn of zero and every request unchanged
- [ ] Generated ids are sequential per scenario and recovered from persisted records rather than held in memory
- [ ] Two runs of the demo produce identical JSON once creation timestamps and timing measurements are removed
