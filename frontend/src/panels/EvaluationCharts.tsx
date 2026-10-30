import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const tones = { sky: "var(--color-mission-accent)", green: "var(--timeline-completed-border)", amber: "var(--timeline-started-border)" };
/** Shared chart scale, tooltip and accessibility; null never becomes a zero bar. */
export function EvaluationBar({ label, value, maximum = 1, text, tone = "sky" }: { label: string; value: number | null | undefined; maximum?: number; text: string; tone?: keyof typeof tones }) {
  const available = value != null && Number.isFinite(value) && maximum > 0;
  const scale = Math.max(maximum, value ?? 0);
  return <figure className="evaluation-bar" aria-label={`${label}: ${text}`}>
    <figcaption><span>{label}</span><strong>{text}</strong></figcaption>
    {available ? <ResponsiveContainer width="100%" height={64} minWidth={0} initialDimension={{ width: 360, height: 64 }}>
      <BarChart layout="vertical" data={[{ label, value }]} margin={{ left: 0, right: 12, top: 2, bottom: 0 }} accessibilityLayer>
        <CartesianGrid stroke="var(--amis-border)" horizontal={false} strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, scale]} tick={{ fill: "var(--color-mission-muted)", fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => maximum === 1 ? `${Number(v) * 100}%` : String(v)} />
        <YAxis type="category" dataKey="label" hide />
        <Tooltip formatter={() => text} cursor={false} contentStyle={{ background: "var(--amis-surface)", borderColor: "var(--amis-border)", color: "var(--color-mission-text)" }} />
        <Bar dataKey="value" name={label} fill={tones[tone]} barSize={12} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer> : <p>No applicable measurement</p>}
  </figure>;
}
