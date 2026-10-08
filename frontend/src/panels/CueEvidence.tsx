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
      <p className="text-amber-300/80">{CUE_POLICY_NOTICE}</p>
    </div>
  );
}
