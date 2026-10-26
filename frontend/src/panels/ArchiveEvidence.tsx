import type { MissionEventSchema } from "../api/client";

export const ARCHIVE_APPROXIMATION = "Scene cloud cover is catalogue-reported, not a guarantee of cloud-free target pixels. Metadata qualification does not verify image product contents.";

/** Accepted evidence is self-contained; inspection never loads a remote product. */
export function ArchiveEvidenceDetails({ event }: { event: MissionEventSchema | undefined }) {
  if (event?.event_type !== "REQUEST_SATISFIED_BY_ARCHIVE") return null;
  const p = event.payload;
  return (
    <div aria-label="Archive fulfillment evidence" className="text-[10px] text-neutral-400">
      <p className="text-violet-300">Satisfied by archive imagery · {p.request_id}</p>
      <p>{p.catalogue_source} · {p.collection_id} / {p.item_id}</p>
      <p>Fulfilled {event.event_time} · acquired {p.acquisition_start} to {p.acquisition_end}</p>
      <p>Catalogue retrieved {p.retrieved_at}</p>
      <p>Point coverage: {p.target_lat}, {p.target_lon} · geographic polygon, boundary included</p>
      <p>Cloud {p.cloud_cover_pct}% ≤ {p.profile.max_cloud_cover_pct}% · GSD {p.gsd_m} m ≤ {p.profile.max_gsd_m} m</p>
      {p.profile.max_view_angle_deg == null ? null : <p>View angle {p.view_angle_deg}° ≤ {p.profile.max_view_angle_deg}°</p>}
      <p>Profile {p.profile.version} · policy {p.policy_version}</p>
      <p>Allowed collections: {p.profile.allowed_collections.join(", ")}</p>
      <p>Allowed acquisition: {p.profile.acquisition_start} to {p.profile.acquisition_end}</p>
      <p>{p.profile.sensor_product_assertion}</p>
      <p className="text-amber-300/80">{ARCHIVE_APPROXIMATION}</p>
      <p>Credit: {p.source_credit}</p>
      <p className="break-all">Source response SHA-256: {p.source_response_sha256}</p>
      {p.source_url.startsWith("https://") ? <a href={p.source_url} target="_blank" rel="noreferrer" className="underline">Source item</a> : null}
    </div>
  );
}
