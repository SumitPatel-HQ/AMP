# AMIS world-impact feature research

Date: 2026-09-28. Research only; no code changed.

## How to read this report

- **Scope.** This report covers what AMIS could add that matters outside the classroom: disaster response, climate, food, oceans, forests, space safety, fairness, and training. It builds on two earlier documents and does not repeat them:
  - `.doc/reference/amis-new-feature.md` covers UI features only (Mission Timeline after NASA Open MCT, Mission Map after World Monitor). Nothing here repeats it. The features below give that timeline and map real-world content to show.
  - `.doc/specs/AMIS_Real_Scenario_Research.md` §10 and §13 covered realism: orbits, downlink, CP-SAT, cloud weather, and multiple satellites. All of that has shipped in Waves 1-7 (`.doc/status/feature-implementation-status.md`). This report starts where that work stopped.
- **Source tags.** Every external claim carries a source id `[Sn]`. The source table at the end says how each source was checked:
  - **Fetched**: I read the owning page or document.
  - **Excerpt**: a search-engine excerpt of the owning page. The page itself blocked fetching (HTTP 403 or a paywall) or was not fetched.
  - **Probe**: I called the live endpoint on 2026-09-28 and looked at the real response.
  - **Biblio**: only the bibliographic record (Crossref or OpenAlex) was checked. The paper's content was not read.
- **UNVERIFIED** marks any claim I could not confirm from a primary source.
- **`[Repo]`** marks a claim about this repository, checked by reading the code.
- **Effort scale** (relative to the Wave 1-7 slices):
  - **S**: one module plus tests, with no new ADR.
  - **M**: a new sub-package or new domain field plus an ADR, about the size of one wave.
  - **L**: changes a locked design rule, or spans several waves.

## 1. Design guardrails every feature must respect

These come from the repository. They decide *how* each world-facing idea can land.

- `[Repo]` **Replay rule.** A replay is the pristine scenario plus the ordered event log (ADR-0002).
  - Orbital inputs are dated snapshots copied into the scenario (ADR-0008).
  - External environmental data follows **archive-then-replay** (ADR-0012):
    1. Only a developer-run script touches the network (`scripts/fetch_weather_archive.py`).
    2. Raw responses are committed with a manifest (URL, retrieval time, SHA-256).
    3. A pure offline rule turns the archive into *recorded events* that carry evidence fields.
    4. The planner never sees the raw data.
- `[Repo]` **Emergency requests in orbital mode are already solved.** When an `EMERGENCY_TASK` payload has no windows and the scenario is orbital, `MissionSession.inject_event` generates the windows at injection time (`amis/session.py:322-328`) and stores them in the event payload. Any external cue can therefore become an `EMERGENCY_TASK` event without touching the planner.
- `[Repo]` **Point targets only.** `ObservationRequest` is a point target with priority 1-5, a duration, a deadline, and costs (`amis/domain/scenario.py:53-66`). It has no requester, no area geometry, no sensor type, and no recurrence. Several features below need one optional field each. The pattern already used for `CloudBlockPayload.to_dict` applies: keys are omitted when absent, so older serialized shapes stay the same (ADR-0012 Consequences).
- `[Repo]` **Night imaging is already possible.** `WindowPolicy.min_sun_elevation_deg` accepts `None` (`amis/domain/orbit.py:52`). A scenario can already model a sensor that images at night, such as radar-like, without a daylight limit.

## 2. Candidate features

### A. Cue-to-request replay: turning real alert feeds into emergency requests

**What it is.** A generic pipeline:

1. A developer script archives an external *cue* feed: earthquakes, disaster alerts, fire detections, methane plumes, vessel detections, or forest-loss alerts.
2. A pure rule converts each archived cue into an `EMERGENCY_TASK` event at a recorded simulated time. The event carries evidence fields (`source`, `source_event_id`, `alert_level`), much like the cloud-block evidence triple.
3. The existing loop runs unchanged: impact, replan, diff, traces, metrics.

This mirrors the real workflow:

- Charter process: an Authorized User reports a disaster. An Emergency On-Call Officer then "identifies timeliest and most appropriate satellite resources" and prepares acquisition plans. Member agencies task their satellites against that plan [S2].
- Sentinel Asia runs a similar request-to-provider flow [S8].

AMIS would let a user replay *real* past activations and watch the plan adapt, with every change explained.

**Who it helps and why it matters**
- Disaster managers and trainees.
  - Charter usage: triggered for 941 disasters in 147 countries between 2000 and the end of 2024, with 85 activations in 52 countries in 2024 alone. It is "the second year in a row" of record activations [S1].
  - Copernicus EMS Rapid Mapping is free and available 24/7/365. Its first situational report comes within 4 hours of activation [S4][S5].
  - Losses: weather, climate, and water hazards caused over 11,000 reported disasters, about 2 million deaths, and US$3.64 trillion in losses in 1970-2019 [S18] (Excerpt).

**Domain adapters.** Each adapter is a script plus a normalizer plus a rule. They are listed in order of readiness.

| Adapter | Feed (verified) | What it returns | Licence / terms | Fit notes |
| --- | --- | --- | --- | --- |
| A1 Earthquakes | USGS GeoJSON summary feeds, `/earthquakes/feed/v1.0/summary/{significant\|4.5\|2.5\|1.0\|all}_{hour\|day\|week\|month}.geojson`, updated every minute [S11] | Point `[lon, lat, depth]`, `time` (epoch ms), `mag`, `alert` (probe saw `"green"`), `tsunami`, `sig`, `mmi`, `status` [S11] (Probe: `significant_month` returned 7 events) | USGS-authored data is U.S. public domain; credit "U.S. Geological Survey" requested [S12] (Excerpt) | Cleanest first adapter: point targets fit `ObservationRequest` directly. |
| A2 Multi-hazard | GDACS API `https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP` with event types EQ, TC, FL, VO, DR, WF and alert levels Red/Orange/Green [S13] | Probe fields: `eventtype`, `eventid`, `glide`, `alertlevel`, `alertscore`, `fromdate`, `todate`, `country`, `iso3`, `severitydata` (Probe) | Terms page gives disclaimers only ("purely indicative… should not be used for any decision making without alternate sources"). **No explicit reuse licence found: redistribution is UNVERIFIED** [S14] | Store only derived fields plus the source URL until the licence is confirmed. The `glide` id gives a cross-reference to other systems. |
| A3 Copernicus EMS activations | `https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/` and `…/public-activations/?code={code}` [S6] | JSON: code (probe latest `EMSR932`, "Wildfire in Huelva Province, Spain"), `eventTime`, `activationTime`, `category`, WKT `centroid`, AOIs as WKT polygons [S6] (Probe) | "Free, full and open access", with a citation notice required [S7] | The gap between `eventTime` and `activationTime` gives a real injection time. AOIs are polygons, so see the risks below. |
| A4 Active fire | NASA FIRMS area API `/api/area/csv/[MAP_KEY]/[SOURCE]/[west,south,east,north]/[1-5 days]/[date]`. Sources: VIIRS (SNPP, NOAA-20, NOAA-21), MODIS, Landsat (US/Canada only). Limit 5000 transactions per 10 minutes [S15] | CSV fire detections. Near-real-time data within 3 hours of observation [S16] (Excerpt) | Free MAP_KEY registration [S15]. NASA Earth science data are open for any use [S17] (Excerpt) | Many points per fire, so cluster them into one request per fire. The MAP_KEY must stay in the developer script's environment and never enter the repo. |
| A5 Methane super-emitters | Carbon Mapper public portal (Tanager-1, EMIT) [S21] (Excerpt) | Plume location, emission estimate, sector [S21] | Non-commercial use; data published 30 days after detection; commercial use requires contact [S21] (Excerpt) | Models UNEP MARS "tip and cue": global mappers detect, then higher-resolution satellites attribute the source [S19]. |
| A6 Dark vessels | Global Fishing Watch APIs [S23] | Datasets not enumerated on the licence page (**UNVERIFIED which endpoints expose SAR detections**) | CC BY-NC 4.0, non-commercial only, "Powered by Global Fishing Watch" attribution, 50,000 requests/day [S23] | Moving targets break the fixed-point request model, so treat this as area revisit. Radar-like imaging uses `min_sun_elevation_deg=None`. |
| A7 Forest loss | GFW integrated alerts (GLAD-L 30 m Landsat, GLAD-S2 10 m Sentinel-2, RADD 10 m Sentinel-1, DIST-ALERT) [S24] (Excerpt) | Alert rasters/points | **Licence UNVERIFIED** (the dataset page did not render; the redirect goes to globalnaturewatch.org) | Lower urgency, so a better fit for campaigns (feature F) than emergencies. |

**Impact statistics for the non-disaster adapters**
- **Methane.**
  - MARS launched at COP27 in 2022 and uses more than 30 satellite instruments [S19] (Excerpt).
  - UNEP reports that responses to its more than 3,500 alerts rose from 1% to 12%, with 88% of detected sources still unanswered [S20] (Excerpt; the page returned 403 to the fetcher, so this rests on the UNEP search excerpt).
- **Fishing.** "About 75 percent of the world's industrial fishing vessels are not publicly tracked." Source: a GFW-led study in *Nature*, 3 Jan 2024, using ESA radar and optical imagery [S22] (Fetched press release; the Nature page was paywall-redirected).

**How it maps onto AMIS**
- New `amis/cues/` package, a sibling of `amis/weather/` (`archive.py`, `samples.py`, `threshold.py`):
  - `archive.py`: manifest plus checksum verification (copy `load_archive`).
  - `normalize.py`: one normalizer per adapter, producing `CueSample(source, source_event_id, lat, lon, event_time, alert_level)`.
  - `rules.py`: a pure mapping from cue to an `ObservationRequest` plus an injection time.
- Data under `amis/data/cues/`. Scripts `scripts/fetch_cue_archive.py` and `scripts/build_cue_events.py`, mirroring `build_weather_events.py`.
- `EmergencyRequestPayload` (`amis/domain/event.py:82`) gains optional evidence keys. Validation goes in `session._validate_emergency_request`, and the schema in `amis/api_schemas.py:344`.
- `amis/examples.py` gains replay Examples such as "Huelva wildfire EMSR932".
- Frontend: `panels/EventControl.tsx` shows the evidence, and `MissionMap` shows cue markers.
- **The priority and deadline mappings are AMIS assumptions, not source facts.** For example, GDACS Red maps to priority 5, and the deadline is event time plus N hours. They must be written down in an ADR as assumptions. No cited source prescribes an imaging deadline for a given alert level. That is UNVERIFIED and should be treated as policy.

**Offline and deterministic fit.** Same shape as ADR-0012:
- The fetch happens only in the script.
- The event log carries the request and the windows computed at injection, so replay needs neither the archive nor the network. `tests/test_weather_replay.py` already shows how to prove this with a socket guard.

**Effort and risks**
- Effort:
  - **M** for the mechanism plus A1 (USGS).
  - **S** for each further adapter (A3 CEMS, A4 FIRMS).
  - **A5-A7** are S each for code but are gated on licensing.
- **Risk: area versus point.** CEMS AOIs are polygons [S6], but requests are points. Using the centroid is honest but crude. Tiling an AOI into several point requests inflates the request count and blurs mission utility. Either way the choice must be written down.
- **Risk: sensor modality.** Methane needs a hyperspectral imager and dark-vessel work uses radar. AMIS has no sensor type, so pinning `satellite_id` is the only lever today.
- **Risk: licences.** GDACS and GFW alerts are unclear or non-commercial (A2, A7, A6). Keep only derived coordinates and ids, and record the licence in `THIRD_PARTY_NOTICES.md`.
- **Risk: sensitive data.** CEMS marks some activations sensitive [S6]. Archive only the public (non-sensitive) activations.

---

### B. Response-latency metric and "who can image it first" feasibility report

**What it is.** Two small additions:
1. **Time to first acquisition** for every request that entered through an `EMERGENCY_TASK` event: the planned (or completed) imaging start minus the event's simulated time. A companion value says which satellite achieved it.
2. **A feasibility query**: for one candidate request, list each satellite's earliest valid orbital window without planning. This answers the Charter duty officer's question, "identify the timeliest and most appropriate satellite resources" [S2].

It follows the OGC Sensor Planning Service EO profile (OGC 10-135). That profile defines `GetFeasibility` alongside `Submit` and `Reserve` for EO tasking [S34] (Excerpt).

**Impact.** Speed is what emergency users measure:
- The Charter delivers maps "within a matter of hours or days" [S3].
- CEMS promises a first report within 4 hours [S5].

Today AMIS measures utility, churn, and explanation coverage, but not *how fast* an urgent request gets served. With this metric, planner comparison (`amis/evaluation/comparison.py`) can show whether CP-SAT or greedy serves emergencies sooner. That is a result with real consequences, not just a higher objective value.

**How it maps onto AMIS**
- `amis/metrics.py`: a new field on `MetricsResult` (`amis/domain/metrics.py`), null when there are no emergency requests, following the existing null-on-zero rule.
- Feasibility: a read-only route in `amis/api.py`. It calls the session's window provider for one hypothetical request, which the session already does at `session.py:326`, and records nothing.
- A timeline marker from event time to first action.

**Data.** None new.

**Effort.** **S**.

**Risks.**
- "First acquisition" is a planned time until the clock passes it. Report both the planned and the achieved value.
- Feasibility must not mutate the session. It should be a pure function over the scenario.

---

### C. Fair multi-requester tasking

**What it is.**
- Give each `ObservationRequest` an optional `requester_id`, for example a national disaster agency or a co-funding partner.
- Add per-requester metrics: each requester's share of mission utility, plus a fairness indicator.
- Optionally add a fairness-aware objective mode to `CpSatPlanner`.
- When fairness moves a request, the DecisionTrace must say so with its own ReasonCode. Otherwise explanation coverage would be dishonest, the same point GAP-10 made for `HIGHER_PRIORITY_TASK_INSERTED` (`amis/domain/enums.py:53-59`).

**Who it helps.** Countries that depend on shared, donated capacity:
- The Charter's Universal Access initiative had registered and trained mandated organisations from 43 disaster-prone countries as Authorized Users by the end of 2024 [S1].
- Pure priority-sum scheduling favours whichever requester files the most high-priority requests. Fair sharing is an established research problem:
  - Bianchessi et al., multi-satellite, multi-orbit, **multi-user** management of EO satellites, *EJOR* 177 (2007) 750-762 [S37] (Biblio).
  - Tangpattanakul, Jozefowiez & Lopez (2012) optimise total profit together with fairness among users, stated as minimising the maximum profit difference between users [S40]. This is Biblio only; the objective wording comes from an index summary and was not read in the paper.
  - Picard (IWPSS 2021): constellation scheduling with multiple users and exclusive orbit portions [S39].
  - Krigman, Grinshpoun & Dery, *Sci. Rep.* (2026): scheduling "must balance efficiency and fairness across stakeholders," and each proposed algorithm shows "a unique trade-off between efficiency and fairness" [S38].

**How it maps onto AMIS**
- `ObservationRequest` (`amis/domain/scenario.py`): optional `requester_id`, omitted from `to_dict` when absent.
- `amis/metrics.py`: per-requester utility and a fairness number.
  - Candidates: minimum requester share, or the max-min utility gap used in [S40].
  - Jain's index is common in networking, but its original source was **not verified** here.
- `amis/planning/cp_sat.py`: an optional secondary objective, for example maximising the minimum requester utility after a primary-utility bound, recorded in `solver_details` (ADR-0009).
- `amis/planning/greedy.py`: an optional round-robin tie-break between requesters of equal priority. The ordering is currently priority, deadline, duration, id.
- A new ReasonCode such as `REBALANCED_FOR_REQUESTER_SHARE`, with its template sentence in `amis/trace.py`.
- A frontend panel showing per-requester bars.

**Data.** None external. Evaluation cases in `amis/data/evaluation/planner_comparison/`.

**Effort.** **M**. It needs an ADR because it changes what "optimal" means.

**Risks.**
- Fairness conflicts with the stability rule and with churn. A fairness-driven replan can move many actions.
- Frozen actions already count toward each requester's share, so they must be included in the fairness calculation.
- The choice of fairness measure is a value judgement. Present it as a selectable, visible policy, never as a hidden default.

---

### D. Archive-first check: don't spend tasking on what open data already covers

**What it is.**
- A developer script queries an open catalogue for recent, low-cloud scenes over each target.
- An offline rule then emits a recorded event, for example `REQUEST_SATISFIED_BY_ARCHIVE`, carrying evidence (`catalogue`, `item_id`, `datetime`, `eo:cloud_cover`).
- On replan the request leaves the plan with its own reason code. That frees capacity for requests that truly need new imaging.

**Why it matters.**
- Sentinel data is free, full, and open for any user and any purpose, with a simple attribution notice [S27] (Excerpt).
- About 67% of Earth is cloud-covered on average (MODIS) [S43] (Excerpt). Usable clear scenes are therefore valuable, and new acquisitions often fail. The cloud-block work already models that failure (ADR-0012).
- Every tasking slot freed this way can go to a disaster or humanitarian request.

**Data source (verified).**
- Copernicus Data Space Ecosystem STAC API at `https://stac.dataspace.copernicus.eu/v1/`.
  - Supports CQL2 filtering such as `eo:cloud_cover <= 10`, with no authentication needed for catalogue search [S26].
  - Probe: `GET /collections/sentinel-2-l2a` returned 200.
- The STAC `view` extension defines `view:off_nadir` and `view:sun_elevation` [S28]. AMIS's `max_off_nadir_deg` and `min_sun_elevation_deg` map directly onto these for a "was it good enough" rule.

**How it maps onto AMIS**
- New `amis/archive_check/`, the same shape as `amis/weather/`.
- New `EventType` and payload in `amis/domain/event.py`.
- `RequestStatus` gains a terminal state, or reuses `DROPPED` with a distinct ReasonCode. **An ADR must decide whether a satisfied request counts toward mission utility.** Arguably yes: the need was met.
- `amis/diff.py` classification, `amis/trace.py` template, and a frontend badge.

**Effort.** **M**.

**Risks.**
- "Satisfied" depends on the user's need. Resolution, recency, and sensor all matter, and a 10 m Sentinel-2 scene does not replace a 50 cm damage image. Keep the rule's thresholds explicit and record them in the evidence.
- The catalogue changes over time, so replay must rely only on the archived response. The ADR-0012 pattern covers this.

---

### E. Conjunction-avoidance manoeuvre as a MissionEvent

**What it is.**
- Archive CelesTrak SOCRATES Plus conjunction reports.
- A pure rule converts any conjunction for a scenario satellite whose `MAX_PROB` meets a threshold into a recorded `SATELLITE_UNAVAILABLE` outage around TCA. The outage carries evidence: `source`, `tca`, `tca_range_km`, `max_prob`, `threshold`.
- The existing payload-outage machinery handles impact, replan, and traces (`session.inject_satellite_outage`, `amis/session.py:430`).

**Why it matters.**
- ESA's 2025 report counts about 40,000 tracked objects, about 11,000 of them active payloads, and over 1.2 million debris objects larger than 1 cm [S31].
- A typical LEO satellite receives "hundreds of alerts… every week." ESA performs "more than one collision avoidance maneuver per satellite annually," and these "delay scientific observations" [S32].
- ESA uses a 1-in-10,000 probability threshold before preparing a manoeuvre [S32]. That gives a defensible default for the rule.
- Showing space-safety cost inside an EO plan is both educational and realistic.

**Data (verified).**
- SOCRATES screens active satellites against the full public catalogue for approaches within 5 km over the next 7 days. There are "no fees or restrictions" [S29].
- Probe of `sort-minRange.csv` confirmed the header: `NORAD_CAT_ID_1, OBJECT_NAME_1, DSE_1, NORAD_CAT_ID_2, OBJECT_NAME_2, DSE_2, TCA, TCA_RANGE, TCA_RELATIVE_SPEED, MAX_PROB, DILUTION`.
- Usage policy [S30]:
  - SOCRATES updates every 10-11 hours. The SOCRATES page says three runs per day; the two statements are roughly consistent.
  - Scripts must not re-query inside that interval.
  - Ignoring errors gets the IP address firewalled.
- Space-Track CDMs are **not** suitable. The handbook limits CDM sharing to the operator organisation and its contractors [S33] (Excerpt).

**How it maps onto AMIS**
- `amis/conjunction/` with archive, normalizer, and rule.
- `scripts/fetch_socrates_archive.py`, following the existing CelesTrak fetch discipline.
- Optional evidence fields on `SatelliteOutagePayload` (`amis/domain/event.py:105`), all-or-nothing like the cloud-block triple.
- Optionally a distinct ReasonCode such as `COLLISION_AVOIDANCE_OUTAGE`, so traces read "moved because SAT-1 was manoeuvring to avoid NORAD 12345," not just "unavailable."

**Effort.** **S-M**.

**Risks.**
- SOCRATES is a 7-day look-ahead that is replaced every run. An archive only matches scenarios whose time range falls inside its capture, so real replays need matched dates.
- Hypothetical satellites, such as the "Hypothetical agile imager on Landsat 8 orbit" example (`amis/examples.py:49`), only match if they reuse a real NORAD id.
- The manoeuvre's own delta-v, fuel use, and orbit change are out of scope. The scenario orbit would stay unchanged. State that simplification.
- SOCRATES leaves out intra-fleet Starlink and OneWeb conjunctions [S29].

---

### F. Recurring monitoring campaigns (agriculture and food security, forests)

**What it is.** A `Campaign` input that expands deterministically, when the scenario is built, into ordinary `ObservationRequest`s. For example: "image region R every 5 days until date D, priority 3." The planner stays unchanged.

The CCSDS mission-planning report lists "expanding a single Planning Request into multiple activities based on repeat rules" as a standard pattern [S35] (Fetched, §4 text).

**Who it helps.** Food-security monitoring:
- The GEOGLAM Crop Monitor for Early Warning has run since February 2016.
- Its monthly consensus bulletins, built with FAO, WFP, FEWS NET, JRC and others, cover countries at risk of food insecurity and are "often used to inform humanitarian organization decisions on food allocation and assistance" [S25] (Excerpt).

Forest-alert follow-up (A7) also fits here better than emergency tasking.

**How it maps onto AMIS**
- Scenario builder and `Scenario.from_dict` expansion: request ids like `CMP-1-003`, with the campaign id kept on each request.
- Metrics: campaign completion, meaning the share of occurrences served.
- Timeline grouping in the frontend.

**Effort.** **S-M**.

**Risks.**
- Horizon size: AMIS demos run over hours to days, but crop campaigns span weeks, and window generation cost grows with the horizon (Phase 2 spec, Further Notes: "sparse short windows need multi-day demo horizons").
- **The expanded requests must be stored in the scenario, not re-expanded on replay** (ADR-0002).

---

### G. Training packs for emerging space agencies and disaster managers

**What it is.** Curated Examples built from features A to E, each with a briefing, a disruption script, and an explicit "why did my request drop?" requester view:
- A real past activation.
- A conjunction outage.
- A cloud-heavy week.

Scoring uses the existing metrics plus B and C. No new planning logic is needed.

**Who it helps.**
- UN-SPIDER (established 2006) focuses on "capacity-building and institutional strengthening, in particular for developing countries" [S9] (Excerpt).
- The Charter's Universal Access path requires "a registration and training process" [S1].
- UNOOSA's Access to Space for All has given 30 awards to countries with no or emerging space capability [S44] (Excerpt).
- An African Space Agency is being built in Cairo, with an AU-EU space partnership running to 2028 [S47] (Excerpt).

An offline, free, explainable simulator that runs on a laptop with Docker suits exactly these settings.

**Why AMIS is well placed.** CCSDS says feedback on each Planning Request's state, and traceability back to the requester, are core planning-service information. It also notes that "no standards exist" yet for exchanging planning data [S35] (Fetched, Foreword and §6.4). AMIS's DecisionTrace and ReasonCodes already give that feedback. A requester-facing view is mostly presentation work.

**Mapping.**
- `amis/examples.py`.
- A new `amis/data/exercises/` folder with briefing text.
- A frontend "exercise" mode.
- An optional export of plan and traces in a documented JSON profile that uses CCSDS terms (Planning Request, Plan, feedback).

**Effort.** **M**, mostly content.

**Risks.**
- Pedagogical value needs validation with real users. UNVERIFIED demand.
- Keep the scenarios honest: packs must say what is simplified (point targets, no sensor types, approximate slew per ADR-0013).

---

### H. Cloud-probability-aware planning (contrast option, not recommended now)

**What it is.** Let the planner prefer windows with lower archived or climatological cloud probability, instead of reacting only after a cloud block.

**Evidence.**
- Global cloud fraction is about 67% [S43].
- Scheduling under cloud uncertainty is an established topic. Wang, Demeulemeester et al. (2019, *IEEE Systems Journal* 13:3556-3567) give exact and heuristic algorithms for multiple satellites under cloud uncertainty [S46] (Biblio only, from a search listing, UNVERIFIED content).
- The 20-year AEOS survey reviews the formulations [S41].

**Why not now.** It breaks ADR-0012's central rule that "the planner never sees weather." It would need a new ADR, planner inputs beyond windows, and a new determinism argument. Effort **L**. The impact is real, but features A to E deliver more per unit of effort without reopening a locked decision.

---

### I. Benchmark alignment (enabler, not a feature)

EOS-Bench (April 2026) publishes 13,900 instances (up to 1,000 satellites and 10,000 requests) under CC BY 4.0. Its five metrics include **workload balance** and **timeliness** [S42]. Those are the same axes as features C and B.

Importing a small subset into `amis/data/evaluation/` would let AMIS report against a public yardstick. Effort **S-M**.

Risk: the instance format may assume agile-attitude models that AMIS approximates differently (ADR-0013). **UNVERIFIED** until the repo format is read.

---

## 3. Side finding

The prior research left Open-Meteo's licence "not confirmed" (`AMIS_Real_Scenario_Research.md` §13). The Open-Meteo licence page states:
- The data is offered under **CC BY 4.0**.
- The free API is for **non-commercial** use, up to 10,000 calls per day.
- Attribution "Weather data by Open-Meteo.com" is required where the data is displayed [S36] (Excerpt).

Recommended follow-up: add this to `.doc/reference/THIRD_PARTY_NOTICES.md` and show the attribution wherever cloud-block evidence is displayed.

## 4. Ranked shortlist (impact to effort)

1. **A1+A3: Real-disaster cue replay (USGS earthquakes and Copernicus EMS activations). Effort M.**
   - This turns AMIS from a planning demo into a tool that replays the actual Charter/CEMS workflow ("identify timeliest… satellite resources" [S2]) on real events, with every plan change explained.
   - Both feeds are verified live, open for reuse (public domain [S12] and free, full and open [S7]), and point- or centroid-shaped.
   - The key enabler already exists: orbital emergency windows are computed at injection and recorded in the log (`amis/session.py:322-328`). The work is an `amis/cues/` sibling of `amis/weather/` plus an ADR that states the priority and deadline mapping as assumptions.
   - Impact is the highest on the list: 941 Charter activations in 147 countries, rising year on year [S1].
2. **B: Response-latency metric and feasibility query. Effort S.**
   - The cheapest item, and it multiplies the value of #1. Emergency users judge service by hours [S3][S5], and AMIS currently cannot say how fast it served an urgent request.
   - One metric field, one read-only route, and one timeline marker. Planner comparison then gains a metric that matters to people, not just to the objective.
   - It follows the OGC SPS `GetFeasibility` idea [S34] without adopting the whole standard.
3. **E: Conjunction-avoidance outage events from SOCRATES. Effort S-M.**
   - Adds space sustainability to AMIS using an input that is verified, free, and unrestricted [S29], and a threshold ESA publishes (1 in 10,000 [S32]).
   - It reuses the existing outage event, needing only an evidence block and possibly one ReasonCode.
   - The traces then teach something real: collision avoidance "delay[s] scientific observations" [S32], and the user sees exactly which observations and why.
   - The main cost is matching archive dates to scenario dates.
4. **C: Fair multi-requester tasking. Effort M.**
   - The strongest *values* feature. Shared and donated capacity (Charter Universal Access, 43 countries [S1]) should not go only to whoever files the most priority-5 requests.
   - It needs an ADR, one optional request field, per-requester metrics, and an optional CP-SAT objective term. Research grounding is solid [S37][S38][S39][S40].
   - It fits AMIS's explainability core: a fairness move must be a named ReasonCode, never a silent side effect.
   - It ranks fourth only because it redefines "good plan" and interacts with churn.
5. **D: Archive-first check against Copernicus STAC. Effort M.**
   - Saves scarce tasking for requests that truly need new imaging, using data that is free for any purpose [S27] and a catalogue verified live [S26].
   - It needs a new event type and a decision on how "satisfied by archive" counts in utility, which is the main design cost.
   - It ranks below E and C because what counts as "good enough" depends heavily on the user's need.

Honourable mentions:
- **F (campaigns)**: S-M. A clear food-security story [S25]; mainly limited by horizon length.
- **G (training packs)**: M. Best done *after* 1-4, since it packages them.

## 5. Open questions

1. **Priority and deadline mapping.** Which alert fields (GDACS `alertlevel`, USGS `alert`/`sig`) map to which AMIS priority and deadline? No source prescribes this (UNVERIFIED). It needs an explicit, cited-as-assumption ADR, ideally checked with a practitioner.
2. **Area targets.** Centroid, tiling, or a new area-request concept for CEMS AOIs? Tiling changes mission utility semantics.
3. **Sensor modality.** Should `Satellite` gain a sensor type (optical, radar, hyperspectral) so methane and vessel cues route correctly? Today only `satellite_id` pinning is available.
4. **GDACS reuse licence.** The terms page states no licence [S14]. Ask JRC before committing raw archives. The GFW integrated-alerts licence [S24] is also unconfirmed.
5. **Fairness measure.** Which one: max-min share, a max-difference bound [S40], or something else? Does fairness apply per replan or over the whole mission?
6. **Archive satisfaction and utility.** Does a request satisfied from the archive count toward mission utility and completion rate?
7. **SOCRATES date matching.** Should the project keep a rolling committed archive so that future scenarios have matching conjunction data, and how large may it grow in the repo?
8. **Demand validation for training packs.** Would UN-SPIDER-style trainees or a university EO course actually use them? No evidence was gathered (UNVERIFIED).
9. **MARS figures.** UNEP pages returned HTTP 403 to the fetcher. The figures [S19][S20] come from UNEP search excerpts and should be re-read in a browser before being quoted in a presentation.

## 6. Sources

| Id | Source (owning organisation) | URL | Check |
| --- | --- | --- | --- |
| S1 | International Charter, "24th Annual Report of the Charter" (2024 data) | https://disasterscharter.org/news/24th-annual-report-of-the-charter | Fetched |
| S2 | International Charter, "Activating the Charter" | https://disasterscharter.org/charter-activation-process | Fetched |
| S3 | International Charter, About | https://disasterscharter.org/web/guest/about-the-charter | Fetched (statistics counters did not render) |
| S4 | Copernicus EMS On Demand Mapping, About | https://mapping.emergency.copernicus.eu/about/ | Fetched |
| S5 | Copernicus EMS, Rapid Mapping portfolio | https://mapping.emergency.copernicus.eu/about/rapid-mapping-portfolio/ | Fetched |
| S6 | Copernicus EMS, "Emergency Response data" (harvest API) | https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/ | Fetched + Probe |
| S7 | Copernicus EMS, Terms and conditions | https://mapping.emergency.copernicus.eu/terms-and-conditions/ | Fetched |
| S8 | Sentinel Asia, About; UN-SPIDER Sentinel Asia page | https://sentinel-asia.org/aboutsa/AboutSA.html ; https://un-spider.org/sentinel-asia | Fetched (About); Excerpt (request flow via ADRC to Data Provider Nodes) |
| S9 | UNOOSA, UN-SPIDER | https://www.unoosa.org/unoosa/en/ourwork/un-spider/index.html | Excerpt |
| S11 | USGS, GeoJSON Summary Format | https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php | Fetched + Probe |
| S12 | USGS, Copyrights and Credits | https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits | Excerpt |
| S13 | GDACS, API quick start | https://www.gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf | Fetched + Probe |
| S14 | GDACS, Terms of Use | https://www.gdacs.org/About/termofuse.aspx | Fetched |
| S15 | NASA FIRMS, Area API | https://firms.modaps.eosdis.nasa.gov/api/area/ | Fetched |
| S16 | NASA Earthdata, Data Latency | https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/data-latency | Excerpt |
| S17 | NASA Earthdata, Open Data, Services, and Software Policies | https://www.earthdata.nasa.gov/engage/open-data-services-software-policies | Excerpt |
| S18 | WMO, Atlas of Mortality and Economic Losses (1970-2019) news release | https://wmo.int/media/news/weather-related-disasters-increase-over-past-50-years-causing-more-damage-fewer-deaths | Excerpt |
| S19 | UNEP, Methane Alert and Response System (MARS) | https://www.unep.org/topics/energy/methane/methane-alert-and-response-system-mars | Excerpt (HTTP 403 on fetch) |
| S20 | UNEP press release, "Better data driving action on methane emissions, but more work needed" | https://www.unep.org/news-and-stories/press-release/better-data-driving-action-methane-emissions-more-work-needed | Excerpt (HTTP 403 on fetch) |
| S21 | Carbon Mapper, Data | https://carbonmapper.org/data | Excerpt |
| S22 | Global Fishing Watch press release on Paolo, Kroodsma et al., *Nature* (2024), doi:10.1038/s41586-023-06825-8 | https://globalfishingwatch.org/press-release/new-research-harnesses-ai-and-satellite-imagery-to-reveal-the-expanding-footprint-of-human-activity-at-sea/ | Fetched (press release); paper paywalled |
| S23 | Global Fishing Watch API, License and Rate Limits | https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits | Fetched |
| S24 | Global Forest Watch, Integrated deforestation alerts | https://data.globalforestwatch.org/datasets/gfw::integrated-deforestation-alerts/about | Excerpt; licence UNVERIFIED |
| S25 | GEOGLAM Crop Monitor for Early Warning | https://www.cropmonitor.org/crop-monitor-for-early-warning | Excerpt |
| S26 | Copernicus Data Space Ecosystem, STAC product catalogue docs | https://documentation.dataspace.copernicus.eu/APIs/STAC.html | Fetched + Probe |
| S27 | European Commission, Legal notice on the use of Copernicus Sentinel Data | https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice | Excerpt |
| S28 | STAC `view` extension (stac-extensions/view) | https://github.com/stac-extensions/view | Excerpt |
| S29 | CelesTrak, SOCRATES Plus | https://celestrak.org/SOCRATES/ | Fetched + Probe (CSV header) |
| S30 | CelesTrak, Usage Policy | https://celestrak.org/usage-policy.php | Fetched |
| S31 | ESA, Space Environment Report 2025 | https://www.esa.int/Space_Safety/Space_Debris/ESA_Space_Environment_Report_2025 | Fetched |
| S32 | ESA, Automating collision avoidance | https://www.esa.int/Space_Safety/Space_Debris/Automating_collision_avoidance | Fetched |
| S33 | Space-Track, Spaceflight Safety Handbook for Operators v1.7 | https://www.space-track.org/documents/SFS_Handbook_For_Operators_V1.7.pdf | Excerpt |
| S34 | OGC 10-135, EO Satellite Tasking Extension for SPS | https://portal.ogc.org/files/?artifact_id=40185 | Excerpt |
| S35 | CCSDS 529.0-G-1, Mission Planning and Scheduling (Green Book, June 2018) | https://ccsds.org/Pubs/529x0g1.pdf | Fetched (full text extracted; Foreword, §4, §6.4) |
| S36 | Open-Meteo, Licence | https://open-meteo.com/en/licence | Excerpt |
| S37 | Bianchessi, Cordeau, Desrosiers, Laporte, Raymond, *EJOR* 177 (2007) 750-762, doi:10.1016/j.ejor.2005.12.026 | https://doi.org/10.1016/j.ejor.2005.12.026 | Biblio (abstract withheld by publisher) |
| S38 | Krigman, Grinshpoun, Dery, "Efficiency-fairness tradeoff in distributed satellite scheduling," *Sci. Rep.* (2026), doi:10.1038/s41598-026-61619-y | https://doi.org/10.1038/s41598-026-61619-y | Biblio + abstract (OpenAlex) |
| S39 | Picard, "Auction-based and Distributed Optimization Approaches for Scheduling Observations in Satellite Constellations with Exclusive Orbit Portions," IWPSS 2021 | https://arxiv.org/abs/2106.03548 | Fetched (abstract) |
| S40 | Tangpattanakul, Jozefowiez, Lopez, "Multi-objective Optimization for Selecting and Scheduling Observations by Agile Earth Observing Satellites," LNCS (2012), doi:10.1007/978-3-642-32964-7_12 | https://doi.org/10.1007/978-3-642-32964-7_12 | Biblio; fairness objective wording from index summary only |
| S41 | Wang, Wu, Xing, Pedrycz, "Agile Earth observation satellite scheduling over 20 years," *IEEE Systems Journal* 15(3) (2021) | https://arxiv.org/abs/2003.06169 | Fetched (abstract) |
| S42 | Yin et al., "EOS-Bench: A Comprehensive Benchmark for Earth Observation Satellite Scheduling" (2026) | https://arxiv.org/abs/2604.25782 | Fetched (abstract) |
| S43 | King, Platnick, Menzel, Ackerman, Hubanks, *IEEE TGRS* 51 (2013) 3826-3852 | https://atmosphere-imager.gsfc.nasa.gov/sites/default/files/ModAtmo/King_et_al.2013.pdf | Excerpt |
| S44 | UNOOSA, Access to Space for All | https://www.unoosa.org/oosa/en/ourwork/access2space4all/index.html | Excerpt |
| S46 | Wang, Demeulemeester, Hu, Qiu, Liu, *IEEE Systems Journal* 13 (2019) 3556-3567 | (bibliographic listing only) | Biblio via search listing; UNVERIFIED |
| S47 | African Union, "AUC-EU Launch Space Partnership Programme" (2025) | https://au.int/en/pressreleases/20250512/auc-eu-launch-space-partnership-programme-space-technologies-and-related | Excerpt |

Live probes run on 2026-09-28:
- USGS `significant_month.geojson` returned 7 features, including properties `alert`, `sig`, `tsunami`, `mmi`.
- GDACS `EVENTS4APP` returned HTTP 200 with fields `eventtype`, `alertlevel`, `glide`, `fromdate`, `todate`, and others.
- CEMS `public-activations-info` returned the latest code `EMSR932`, with a WKT centroid.
- CelesTrak SOCRATES `sort-minRange.csv` header matched the one listed in E.
- CDSE STAC `collections/sentinel-2-l2a` returned HTTP 200.
