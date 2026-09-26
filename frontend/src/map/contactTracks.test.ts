import { describe, expect, it } from "vitest";
import type { ContactWindowSchema, GroundStationSchema, GroundTrackPointSchema, MissionPlanSchema } from "../api/client";
import { contactTracks, stationFootprints } from "./contactTracks";

const point = (minute: number, lon: number): GroundTrackPointSchema => ({
  time: new Date(Date.UTC(2026, 0, 1, 0, minute)).toISOString(),
  lat: 70,
  lon,
  altitude_km: 700,
});

const contact = (id: string, from: number, to: number, valid = true): ContactWindowSchema => ({
  id,
  station_id: "SVALSAT",
  satellite_id: "SAT",
  start: new Date(Date.UTC(2026, 0, 1, 0, from)).toISOString(),
  end: new Date(Date.UTC(2026, 0, 1, 0, to)).toISOString(),
  peak_elevation_deg: 40,
  peak_time: new Date(Date.UTC(2026, 0, 1, 0, from + 1)).toISOString(),
  valid,
});

const track = [point(0, 0), point(1, 10), point(2, 20), point(3, 30), point(4, 40)];

describe("contactTracks", () => {
  it("keeps only the track inside each contact and flags downlinks and lost contacts", () => {
    const plan = { actions: [{ kind: "downlink", window_id: "CON-A" }] } as unknown as MissionPlanSchema;
    const result = contactTracks(track, [contact("CON-A", 1, 3), contact("CON-B", 3, 4, false)], plan);
    expect(result.map((item) => [item.contactId, item.downlink, item.valid, item.paths])).toEqual([
      ["CON-A", true, true, [[[10, 70], [20, 70], [30, 70]]]],
      ["CON-B", false, false, [[[30, 70], [40, 70]]]],
    ]);
  });
});

describe("stationFootprints", () => {
  it("sizes the footprint from mask and altitude and marks a live contact", () => {
    const station = { id: "SVALSAT", name: "Svalbard", lat: 78, lon: 15, altitude_m: 0, min_elevation_deg: 5 } as GroundStationSchema;
    const [footprint] = stationFootprints([station], track, [contact("CON-A", 1, 3)], track[2]!.time);
    // 700 km at a 5 degree mask: acos(6371 cos 5° / 7071) - 5° = 21.16° = about 2,353 km.
    expect(footprint!.radiusM / 1000).toBeCloseTo(2353, -1);
    expect(footprint!.inContact).toBe(true);
  });
});
