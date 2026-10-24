# Briefing: USGS M6.3 Vanuatu earthquake replay

## Archived earthquake facts (source: U.S. Geological Survey)

- Event: magnitude 6.3 earthquake, "102 km NE of Norsup, Vanuatu".
- Source event identifier: `us6000u0xi`.
- Source: U.S. Geological Survey, GeoJSON summary feed
  `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson`,
  archived at `amis/data/cues/vanuatu-us6000u0xi-20261008/` with its retrieval
  manifest and SHA-256 checksum.
- Event time: 2026-10-08T09:00:07.768Z. Epicenter: -15.5411 lat,
  168.1889 lon (depth 10 km; depth is not used as an imaging coordinate).
- USGS alert level: `green`. Significance: 614. These are the only USGS
  facts this replay carries as evidence.

## What is a simulator assumption, not a source fact

- **Priority and deadline are AMIS simulation policy, not source
  recommendations.** USGS does not publish an imaging deadline. AMIS's
  `usgs-earthquake-v1` policy maps a `green` alert to priority 2 and a
  48-hour deadline from the earthquake time, but this earthquake's
  magnitude (6.3, at least 6) raises its priority to 5 under that same
  policy. The deadline is unchanged by magnitude.
- **The satellite, its imaging duration, and its resource costs are
  hypothetical.** This replay uses a hypothetical agile imager on the
  Landsat 8 orbit (stored orbital elements, not a real tasking
  commitment of that spacecraft). The 120-second imaging duration, 50 Wh
  energy cost, and 200 MB storage cost are an explicit author-supplied
  imaging profile for this Example, not a real sensor's rated capability
  and not derived from the earthquake's severity.
- **The earthquake is modeled as a single point target.** The request
  targets the reported epicenter coordinates only. AMIS has no area or
  polygon request type; a real damage assessment would image a wider
  area around the epicenter.

## What this replay demonstrates

The mission starts on 2026-10-07T12:00Z (before the earthquake) and ends
2026-10-08T22:30Z, so a baseline plan exists first. Advancing to the
earthquake's exact recorded time and injecting it exposes Impact against
that baseline plan without changing it. A later manual replan schedules
the emergency request through the ordinary planner and produces an
explained PlanDiff and DecisionTrace,
alongside the routine demand already in the mission.
