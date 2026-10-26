# Archive fulfillment is a distinct terminal outcome

Ticket D-01 requires existing imagery to fulfill a request without inventing
simulated Satellite imaging. Record `REQUEST_SATISFIED_BY_ARCHIVE`, carrying
the complete normalized evidence, and set `SATISFIED_BY_ARCHIVE` (wire value
`satisfied_by_archive`). Neither `COMPLETED` nor `DROPPED` expresses this outcome.

Only pending or scheduled, unexpired pool members may transition. Evidence
must match the request point, collection and explicit author suitability
profile, pass finite measured quality thresholds, and demonstrate acquisition
and catalogue retrieval no later than the accepted event time. The entire
acquisition interval must fit the profile. Required viewing limits require
measured viewing metadata. An authoritative frozen, started or completed
imaging action in execution history forbids replacement. Validation precedes
all mutation and identifier allocation. Runtime handling uses recorded values
only; it never queries a catalogue or opens a product.

Injection changes the RequestPool and records impact, leaving the active plan
affected. Advancing through that request's obsolete future imaging requires
explicit replan. Replan excludes the terminal request and releases only
unfrozen future work. Frozen actions, consumed resources and the pristine
Scenario remain unchanged (ADR-0002 and ADR-0003). PlanDiff and DecisionTrace
use `SATISFIED_BY_ARCHIVE`, including a status explanation when the request
had no previous action. Repeated replans do not repeat that transition.

Existing mission utility remains planned imaging plus current completed
imaging, and imaging completion/resource metrics keep their meaning. Add
archive-satisfied count and priority utility separately. Total-fulfilled
count/utility use the union of those acquisition-served and archive-satisfied
request identities, once each. This total includes planned acquisition; it is
not a count of delivered imagery. Current fulfillment is visible immediately
after injection. A historical plan includes archive events only if their
impact evaluated an earlier version, even when several versions share the
same simulated timestamp. Historical RequestPool membership never gains
later arrivals. Current acquisition completion semantics remain unchanged.

Archive-satisfied emergency arrivals remain visible; after replan they have
null planned acquisition and always null achieved acquisition/Satellite.
Missing acquisition is never zero latency. Requester utility/fairness remains
acquisition-based; D-01 adds no dependency on requester attribution.

Accepted evidence persists in the event log and reconstructs the terminal
RequestPool state offline. Reset clears it. The source-response digest records
provenance; runtime does not independently verify the original response bytes
or image contents. D-02 owns archive checksum verification and selection.

For D-01, geographic coverage supports a simple Polygon exterior ring without
holes, with straight longitude/latitude edges and boundary-inclusive point
coverage. Invalid rings and longitude spans of 180 degrees or greater fail
closed. Other geometry requires explicit normalization/extension in D-02;
bounding boxes alone are never accepted. Scene cloud percentage describes
catalogue metadata, not cloud-free pixels at the target. The explicit
sensor/product assertion is an author decision, not generic sensor matching.

The bundled fixture is synthetic and makes no real catalogue claims. Real
STAC retrieval, qualification and the capacity-release Example remain D-02.
