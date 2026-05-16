type MetricProps = {
  label: string;
  value: string;
  tone?: "neutral" | "risk" | "safe";
};

export function Metric({ label, value, tone = "neutral" }: MetricProps) {
  const toneClass = {
    neutral: "text-ink",
    risk: "text-risk",
    safe: "text-safe"
  }[tone];

  return (
    <div className="rounded-md border border-line bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}
