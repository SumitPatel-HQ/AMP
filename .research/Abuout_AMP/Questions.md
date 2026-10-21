Extended to fullest. File is live.

- Path: `D:\LearningHub\CollegeProjects\AMP\amis_presentation.html` - 39,547 bytes, verified with `Test-Path` true
- Open: double click, or `start amis_presentation.html` from project folder, works on phone browser too
- Now has 68 questions, each 3 to 4 simple points, search filter on top, expand all and print buttons
- New sections added from web research: numbers to memorize, file map, Skyfield traps, benchmarks, 21 extra Q and A

New 21 added, each in short points:

- 48. ADR-0001 session seam
  - One facade owns all state
  - API rebuilds per request, acts, saves
  - Tests inject providers directly
  - Planner stays free of web and DB

- 49. ADR-0002 immutable replay
  - Scenario never edited
  - Event log in order is replay unit
  - Emergency windows stored in event
  - No provider call on replay

- 50. ADR-0003 frozen exempt
  - Started past not re validated
  - Avoids false faults after state moves
  - Replan carries frozen unchanged
  - Projection still reserves cost

- 51. ADR-0004 same protocol
  - Replan calls planner with previous plan
  - Greedy and CP-SAT share signature
  - No sim or UI change for new planner
  - Stability lives in ordering

- 52. ADR-0007 window meaning
  - Orbital window is VTW for one request
  - Must fit duration and daylight if optical
  - Action is OTW inside it
  - Planner tries several starts inside

- 53. ADR-0008 offline snapshots
  - Dated OMM plus manifest committed
  - Small ephemeris excerpt with hash
  - Never fetch in request path
  - Mission dated to epoch week

- 54. ADR-0009 planner choice
  - Pick by name per run
  - Store name plus solver details
  - Single worker and fixed seed
  - Fallback keeps baseline safe

- 55. ADR-0011 downlink rule
  - Downlink is reservation, not booking
  - Re derived each plan
  - Ignored in diff, churn, traces
  - Opens one way rule safely

- 56. find_events edge at t0 and t1
  - Old search centered on culmination
  - Open at start or clipped at end could vanish
  - You clamp at t0 and t1
  - 1 s sampler guards edges

- 57. Double culmination
  - Two peaks without set possible
  - Docs warn this case
  - Do not assume strict 0, 1, 2 order
  - Pair intervals defensively

- 58. High threshold fix
  - 45 to 70 deg once gave wrong set time
  - Root was uneven halving in search
  - Fixed in later Skyfield
  - Your 56 deg case is why cross check matters

- 59. OMM future proof
  - TLE stops near 99999, OMM uses 9 digits
  - ISO dates fix 2 digit year
  - JSON 3 times CSV size, CSV smallest
  - Check time, fetch at most every 2 hours

- 60. Proactive vs reactive
  - Proactive uses chance or robust forecast
  - Reactive repairs with insertion
  - Best is both in loop
  - Yours is reactive demo, forecast is next

- 61. Benchmark lesson
  - EOS-Bench has 1390 scenarios, 13900 cases
  - MIP best small, blows up large
  - Greedy ms but weak, meta better but slow
  - Clustered targets hurt all methods

- 62. Time dependence
  - Slew depends on start times, not fixed
  - Profit depends on angle, oblique worse
  - Both raise hardness past simple routing
  - Your gap plus peak are simplified forms

- 63. Error codes
  - INVALID_SCENARIO for bad mission
  - INVALID_EVENT for bad payload
  - PLAN_INFEASIBLE when nothing fits
  - Plus violation, not found, sim errors

- 64. Frontend pieces
  - Scenario controls, map, state panel
  - Event panel, timeline, compare
  - Trace panel, metrics panel
  - 2D now, 3D later

- 65. Persistence
  - Tables for all plus experiment results
  - Memory for tests, Postgres for app
  - One transaction per save
  - 0002 adds orbit, policy, geometry

- 66. Failure story 1 to admit first
  - Reuse OBS-A to OBS-E ids gets demo windows
  - Fix is policy based dispatch
  - Tests keep legacy path
  - Tell before examiner finds it

- 67. Failure story 2 to admit first
  - 60 s grid on 120 s window loses edges
  - Fix is root find plus inward seconds
  - Sampler bounds error
  - Shows you read reference code

- 68. If asked anything unknown
  - Say what you know in 3 points
  - Name file and line of truth
  - Admit limit plus next test
  - Offer to show code live

No room left for complaint:

- Origin covers 7 papers plus CASPER, EO-1, Ferrari, Wang, Gu, Pleiades, Skyfield, CP-SAT, EOS-Bench
- Numbers cover 705 km, 56.3 deg, 120 s, 7 and 14 days, 1 worker seed 0, 152 and 139, 51.1 percent, cloud stats
- Traps cover culmination rule, double peak, high threshold bug, TLE limits
- Demo covers clicks, words to say, run commands, checklist