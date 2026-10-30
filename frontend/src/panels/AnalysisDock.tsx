import { ChartNoAxesCombined, ChevronDown, ChevronUp, GitCompareArrows, TriangleAlert } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
const icons = [<TriangleAlert key="impact" size={14} aria-hidden="true" />, <GitCompareArrows key="comparison" size={14} aria-hidden="true" />, <ChartNoAxesCombined key="evaluation" size={14} aria-hidden="true" />];
const labels = ["Impact", "Plan Comparison", "Mission Evaluation"];
export function AnalysisDock({ impact, comparison, evaluation, impactRevision, comparisonRevision }: {
 impact: ReactNode; comparison: ReactNode; evaluation: ReactNode; impactRevision: unknown; comparisonRevision: unknown;
}) {
 const id = useId();
 const [active, setActive] = useState(0);
 const [expanded, setExpanded] = useState(false);
 const [seen, setSeen] = useState<unknown[]>([null, null]);
 const revisions = [impactRevision, comparisonRevision];
 const open = (index: number) => { setActive(index); setExpanded(true); setSeen(previous => previous.map((value, i) => i === index ? revisions[i] : value)); };
 return <section aria-label="Analysis dock" className={`amis-analysis-dock col-span-3 ${expanded ? "is-expanded" : ""}`}>
 <div className="amis-dock-bar"><span className="px-3 text-xs text-neutral-400">Analysis</span>
 <div role="tablist" aria-label="Mission analysis" className="flex min-w-0 flex-1">
 {labels.map((label, index) => <button key={label} type="button" role="tab" id={`${id}-tab-${index}`} aria-controls={`${id}-panel-${index}`} aria-selected={active === index} tabIndex={active === index ? 0 : -1}
 onClick={() => open(index)} onKeyDown={event => {
 const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : null;
 if (next === null) return; event.preventDefault(); open(next); document.getElementById(`${id}-tab-${next}`)?.focus();
 }}>{icons[index]}{label}{index < 2 && revisions[index] != null && revisions[index] !== seen[index] && !(expanded && active === index) ? <span className="amis-new">New</span> : null}</button>)}
 </div><button type="button" className="px-3 text-xs" aria-expanded={expanded} aria-controls={`${id}-content`} onClick={() => expanded ? setExpanded(false) : open(active)}>{expanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronUp size={14} aria-hidden="true" />}{expanded ? "Collapse analysis" : "Expand analysis"}</button></div>
 <div id={`${id}-content`} hidden={!expanded} className="amis-dock-content">{[impact, comparison, evaluation].map((content, index) => <div key={index} role="tabpanel" id={`${id}-panel-${index}`} aria-labelledby={`${id}-tab-${index}`} tabIndex={0} hidden={!expanded || active !== index} className="amis-dock-panel">{content}</div>)}</div>
 </section>;
}
