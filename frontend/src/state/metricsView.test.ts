import { describe, expect, it } from "vitest";
import type { MetricsSchema, PlanDiffSchema } from "../api/client";
import { formatPercent, metricsSubject, metricsView } from "./metricsView";

const before = {
  plan_id: "SCN:PLAN-001",
  mission_utility: 15,
  completion_rate: 0.4,
  violation_count: 0,
  planning_time_ms: 0.18,
  battery_utilisation: 0.16,
  storage_utilisation: 0.1,
  request_pool_size: 5,
  request_pool_ids: ["OBS-A", "OBS-B", "OBS-C", "OBS-D", "OBS-E"],
  measured_at: "2026-09-21T11:05:00Z",
  plan_churn: null,
  explanation_coverage: null,
} satisfies MetricsSchema;

const after = {
  ...before,
  plan_id: "SCN:PLAN-002",
  mission_utility: 17,
  completion_rate: 0.6,
  violation_count: 1,
  planning_time_ms: 0.13,
  plan_churn: 0.25,
  explanation_coverage: 1,
} satisfies MetricsSchema;

const diff = {
  from_plan_id: before.plan_id,
  to_plan_id: after.plan_id,
  entries: [],
  metrics_before: before,
  metrics_after: after,
  request_pool_mismatch: false,
} satisfies PlanDiffSchema;

function row(view: ReturnType<typeof metricsView>, key: string) {
  const found = view.rows.find((candidate) => candidate.key === key);
  if (found === undefined) {
    throw new Error(`no ${key} row`);
  }
  return found;
}

describe("formatPercent", () => {
  it("renders null as N/A, never as 0%", () => {
    expect(formatPercent(null)).toBe("N/A");
    expect(formatPercent(0)).toBe("0%");
  });

  it("never rounds a partial share up to a full score or down to nothing", () => {
    expect(formatPercent(0.996)).toBe(">99%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0.004)).toBe("<1%");
  });
});

describe("metricsSubject", () => {
  it("compares the replan's two plans while its revised plan is current", () => {
    expect(metricsSubject(after.plan_id, after, diff)).toEqual({
      before,
      after,
      requestPoolMismatch: false,
    });
  });

  it("falls back to the current plan alone once the comparison is about another plan", () => {
    const current = { ...after, plan_id: "SCN:PLAN-003" };
    expect(metricsSubject(current.plan_id, current, diff)).toEqual({
      before: null,
      after: current,
      requestPoolMismatch: false,
    });
  });

  it("describes the current plan alone before any replan", () => {
    expect(metricsSubject(before.plan_id, before, null)).toEqual({
      before: null,
      after: before,
      requestPoolMismatch: false,
    });
  });

  it("has nothing to describe without a plan", () => {
    expect(metricsSubject(null, null, null)).toBeNull();
  });

  it("does not show metrics that belong to a plan other than the current one", () => {
    expect(metricsSubject("SCN:PLAN-009", before, null)).toBeNull();
  });
});

describe("metricsView", () => {
  it("shows one plan's values without deltas when no comparison exists", () => {
    const view = metricsView({ before: null, after: before, requestPoolMismatch: false });

    expect(view.beforePlanId).toBeNull();
    expect(view.afterPlanId).toBe(before.plan_id);
    expect(row(view, "utility")).toMatchObject({ before: null, after: "15", delta: null });
    expect(row(view, "churn")).toMatchObject({ after: "N/A", delta: null });
    expect(row(view, "coverage")).toMatchObject({ after: "N/A", delta: null });
  });

  it("gives utility, completion and violations a signed delta and a direction", () => {
    const view = metricsView({ before, after, requestPoolMismatch: false });

    expect(row(view, "utility")).toMatchObject({
      before: "15",
      after: "17",
      delta: "+2",
      trend: "better",
    });
    expect(row(view, "completion")).toMatchObject({
      before: "40% of 5",
      after: "60% of 5",
      delta: "+20 pp",
      trend: "better",
    });
    // Fewer violations is the better direction.
    expect(row(view, "violations")).toMatchObject({ delta: "+1", trend: "worse" });
  });

  it("reports an unchanged metric as unchanged rather than hiding the delta", () => {
    const view = metricsView({
      before,
      after: { ...after, mission_utility: before.mission_utility },
      requestPoolMismatch: false,
    });

    expect(row(view, "utility")).toMatchObject({ delta: "±0", trend: "same" });
  });

  it("gives churn and coverage no delta: each describes its own plan's parent transition", () => {
    const view = metricsView({ before, after, requestPoolMismatch: false });

    expect(row(view, "churn")).toMatchObject({ before: "N/A", after: "25%", delta: null, trend: null });
    expect(row(view, "coverage")).toMatchObject({ before: "N/A", after: "100%", delta: null });
  });

  it("renders completion as N/A over an empty request pool instead of 0%", () => {
    const empty = { ...before, completion_rate: 0, request_pool_size: 0, request_pool_ids: [] };
    const view = metricsView({ before: null, after: empty, requestPoolMismatch: false });

    expect(row(view, "completion").after).toBe("N/A");
  });

  it("flags pool-dependent deltas without judging them when the two plans used different request pools", () => {
    const grown = {
      ...after,
      request_pool_size: 6,
      request_pool_ids: [...before.request_pool_ids, "OBS-EMERGENCY"],
    };
    const view = metricsView({ before, after: grown, requestPoolMismatch: true });

    // The change is still shown, but not called better or worse.
    expect(row(view, "utility")).toMatchObject({ delta: "+2", trend: null, deltaNote: "pools differ" });
    expect(row(view, "completion")).toMatchObject({
      delta: "+20 pp",
      trend: null,
      deltaNote: "pools differ",
    });
    // Violations count the plan's own actions, so the pool does not change what they mean.
    expect(row(view, "violations").delta).toBe("+1");
    expect(view.pool).toEqual({
      before: 5,
      after: 6,
      mismatch: true,
      onlyBefore: [],
      onlyAfter: ["OBS-EMERGENCY"],
    });
  });

  it("warns on violations and on changes left without a decision trace", () => {
    const view = metricsView({
      before,
      after: { ...after, explanation_coverage: 0.5 },
      requestPoolMismatch: false,
    });

    expect(row(view, "violations").warn).toBe(true);
    expect(row(view, "coverage").warn).toBe(true);
    expect(row(view, "utility").warn).toBe(false);
  });

  it("reads resource utilisation once, from the mission state at the measured instant", () => {
    const view = metricsView({ before, after, requestPoolMismatch: false });

    expect(view.measuredAt).toBe("2026-09-21T11:05:00Z");
    expect(view.resources).toEqual({ battery: "16%", storage: "10%" });
    expect(view.rows.map((candidate) => candidate.key)).not.toContain("battery");
  });
});
