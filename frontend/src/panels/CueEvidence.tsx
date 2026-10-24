import { CUE_POLICY_NOTICE, type CueEvidence } from "../state/missionEvent";

/**
 * The source evidence an emergency arrival carries, with its credit and the
 * AMIS policy notice beside it. The point is where the cue arrived, never an
 * acquisition: imaging and response are read from the plan, not from here.
 */
export function CueEvidenceDetails({ evidence }: { evidence: CueEvidence }) {
  const facts = [
    `alert ${evidence.alertLevel}`,
    evidence.mag === null ? null : `M${evidence.mag}`,
    evidence.sig === null ? null : `sig ${evidence.sig}`,
  ].filter((part) => part !== null);
  return (
    <div aria-label="Cue evidence" className="text-[10px] text-neutral-400">
      <p>
        <span className="text-neutral-200">{evidence.sourceLabel}</span>
        {` · ${evidence.sourceEventId} · ${facts.join(" · ")}`}
      </p>
      <p className="text-neutral-500">{`Cue arrival for ${evidence.requestId} · ${evidence.eventId}`}</p>
      {evidence.source === "cems" && (
        <>
          <p>{`Category: ${evidence.category}`}</p>
          <p>{`Activation: ${evidence.activationTime}`}</p>
          <p>{`Source event: ${evidence.sourceEventTime ?? "not supplied"}`}</p>
          <p>{`Accepted arrival: ${evidence.arrivalTime}`}</p>
          <p>activation centroid; point approximation. No area-coverage guarantee is modeled.</p>
          <p>{`AMIS policy ${evidence.centroidPolicyVersion}: priority 5; deadline 24 hours after activation.`}</p>
          {evidence.sourceUrl?.startsWith("https://") && (
            <a href={evidence.sourceUrl} target="_blank" rel="noreferrer" className="underline">Copernicus EMS source</a>
          )}
          <p>{`Copernicus Emergency Management Service (\u00a9 ${evidence.activationTime?.slice(0, 4)} European Union), ${evidence.sourceEventId}`}</p>
          {evidence.sourceEventId.startsWith("SYNTHETIC-") && <p>SYNTHETIC fixture; not historical Copernicus evidence.</p>}
        </>
      )}
      <p className="text-amber-300/80">{CUE_POLICY_NOTICE}</p>
    </div>
  );
}
