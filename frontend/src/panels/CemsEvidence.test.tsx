import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MissionEventSchema } from "../api/client";
import { cueEvidence } from "../state/missionEvent";
import { cueMarkers } from "../map/missionMapModel";
import { CueEvidenceDetails } from "./CueEvidence";

// Synthetic evidence only: this code identifies no historical activation.
const event: MissionEventSchema = {
  id: "EVT-CEMS", scenario_id: "SCN-TEST", event_type: "EMERGENCY_TASK",
  event_time: "2026-09-21T10:05:00Z",
  payload: {
    source: "cems", source_event_id: "SYNTHETIC-CEMS-001", alert_level: "unknown",
    category: "Synthetic flood", activation_time: "2026-09-21T10:05:00Z",
    source_event_time: "2026-09-21T09:05:00Z", source_url: "https://mapping.emergency.copernicus.eu/",
    centroid_policy_version: "cems-centroid-v1", windows: [],
    request: { id: "CUE-CEMS", target_lat: 34, target_lon: -118, priority: 5, duration_s: 60,
      energy_cost_wh: 10, storage_cost_mb: 10, deadline: "2026-09-22T10:05:00Z", status: "pending" },
  },
};

describe("CEMS event and map inspection", () => {
  it("shows activation evidence, credit and the point-policy limit", () => {
    const evidence = cueEvidence(event);
    expect(evidence).not.toBeNull();
    render(<CueEvidenceDetails evidence={evidence!} />);
    expect(screen.getByText(/European Union.*SYNTHETIC-CEMS-001/)).toBeTruthy();
    expect(screen.getByText("Category: Synthetic flood")).toBeTruthy();
    expect(screen.getByText(/Activation: 2026-09-21T10:05:00Z/)).toBeTruthy();
    expect(screen.getByText(/Source event: 2026-09-21T09:05:00Z/)).toBeTruthy();
    expect(screen.getByText(/activation centroid; point approximation/)).toBeTruthy();
    expect(screen.getByText(/not source recommendations/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Copernicus EMS source" }).getAttribute("href")).toBe("https://mapping.emergency.copernicus.eu/");
  });

  it("links the centroid marker to the accepted event and request after reload and clears on reset", () => {
    const reloaded: MissionEventSchema = JSON.parse(JSON.stringify(event));
    const markers = cueMarkers([event, reloaded]);
    expect(markers).toHaveLength(1);
    expect(markers[0].coordinate).toEqual([-118, 34]);
    expect(markers[0].evidence.eventId).toBe("EVT-CEMS");
    expect(markers[0].evidence.requestId).toBe("CUE-CEMS");
    expect(cueMarkers([])).toEqual([]);
  });
});
