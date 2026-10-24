import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cueEvent, plan } from "../test/mapFixtures";
import { ImpactPanel } from "./ImpactPanel";

afterEach(cleanup);

describe("cue evidence in event inspection", () => {
  it("shows the recorded evidence, USGS credit and policy notice beside the impact's event", () => {
    render(
      <ImpactPanel
        impact={{
          id: "IMP-001",
          event_id: cueEvent.id,
          evaluated_plan_id: plan.id,
          frozen_action_ids: [],
          valid_unfrozen_action_ids: [],
          invalid_unfrozen_action_ids: [],
          reason_codes: {},
        }}
        events={[cueEvent]}
        plans={[plan]}
        earlier={false}
        selectedRequestId={null}
        onSelectRequest={() => {}}
      />,
    );

    const evidence = screen.getByLabelText("Cue evidence");
    expect(evidence.textContent).toContain("U.S. Geological Survey");
    expect(evidence.textContent).toContain("us7000test");
    expect(evidence.textContent).toContain("alert orange");
    expect(evidence.textContent).toContain("M6.4 · sig 650");
    expect(evidence.textContent).toContain("Cue arrival for CUE-1 · EVT-004");
    expect(evidence.textContent).toContain(
      "Priority and deadline are AMIS simulation policy, not source recommendations.",
    );
  });
});
