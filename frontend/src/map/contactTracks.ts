import type { ContactWindowSchema, GroundStationSchema, GroundTrackPointSchema, MissionPlanSchema } from "../api/client";
import type { Coordinate } from "./missionMapModel";

const EARTH_RADIUS_M = 6_371_000;

/** The stretch of ground track flown during one ground-station contact (ADR-0011). */
export interface MapContactTrack {
  contactId: string;
  stationId: string;
  valid: boolean;
  /** A downlink action in the current plan uses this contact. */
  downlink: boolean;
  /** Antimeridian-split pieces of the track inside the contact window. */
  paths: Coordinate[][];
}

/** A station's visibility footprint: ground range at which the satellite clears the mask. */
export interface MapStationFootprint {
  stationId: string;
  coordinate: Coordinate;
  radiusM: number;
  /** A valid contact spans the current simulated time. */
  inContact: boolean;
}

function splitAtAntimeridian(points: readonly GroundTrackPointSchema[]): Coordinate[][] {
  const paths: Coordinate[][] = [];
  for (const point of points) {
    const last = paths.at(-1);
    if (last === undefined || Math.abs(last.at(-1)![0] - point.lon) > 180) {
      paths.push([[point.lon, point.lat]]);
    } else {
      last.push([point.lon, point.lat]);
    }
  }
  return paths;
}

export function contactTracks(
  groundTrack: readonly GroundTrackPointSchema[],
  contacts: readonly ContactWindowSchema[],
  plan: MissionPlanSchema | null,
): MapContactTrack[] {
  const downlinkContacts = new Set(
    (plan?.actions ?? []).filter((action) => action.kind === "downlink").map((action) => action.window_id),
  );
  return contacts.flatMap((contact) => {
    const start = Date.parse(contact.start);
    const end = Date.parse(contact.end);
    const inside = groundTrack.filter((point) => {
      const time = Date.parse(point.time);
      return time >= start && time <= end;
    });
    const paths = splitAtAntimeridian(inside).filter((path) => path.length > 1);
    if (paths.length === 0) return [];
    return [{
      contactId: contact.id,
      stationId: contact.station_id,
      valid: contact.valid,
      downlink: downlinkContacts.has(contact.id),
      paths,
    }];
  });
}

/**
 * Earth-central angle to the mask horizon: acos(Re cos(e) / (Re + h)) - e,
 * using the mean sampled altitude. Zero without a ground track.
 */
export function stationFootprints(
  stations: readonly GroundStationSchema[],
  groundTrack: readonly GroundTrackPointSchema[],
  contacts: readonly ContactWindowSchema[],
  simulatedTime: string | null,
): MapStationFootprint[] {
  const altitudeM = groundTrack.length === 0
    ? 0
    : (groundTrack.reduce((sum, point) => sum + point.altitude_km, 0) / groundTrack.length) * 1000;
  const now = simulatedTime === null ? NaN : Date.parse(simulatedTime);
  return stations.map((station) => {
    const mask = (station.min_elevation_deg * Math.PI) / 180;
    const angle = altitudeM > 0
      ? Math.acos((EARTH_RADIUS_M * Math.cos(mask)) / (EARTH_RADIUS_M + altitudeM)) - mask
      : 0;
    const inContact = contacts.some((contact) =>
      contact.station_id === station.id && contact.valid
      && Date.parse(contact.start) <= now && now <= Date.parse(contact.end));
    return {
      stationId: station.id,
      coordinate: [station.lon, station.lat],
      radiusM: Math.max(0, angle) * EARTH_RADIUS_M,
      inContact,
    };
  });
}
