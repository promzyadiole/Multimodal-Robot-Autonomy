type StatusCardProps = {
  title: string;
  value: string;
  description?: string;
  tone?: "neutral" | "good" | "warn";
};

/** A single instrument readout: label above, value in the display face. */
export default function StatusCard({
  title,
  value,
  description,
  tone = "neutral",
}: StatusCardProps) {
  const valueTone =
    tone === "good" ? "text-scan" : tone === "warn" ? "text-signal" : "text-ink";
  return (
    <div className="rounded-sm border border-rule bg-panel p-5">
      <p className="font-data text-[10px] tracking-[0.18em] text-muted uppercase">
        {title}
      </p>
      <p className={`mt-2 font-display text-[1.75rem] leading-none tabular-nums ${valueTone}`}>
        {value}
      </p>
      {description ? (
        <p className="mt-2.5 text-[12.5px] leading-snug text-muted">{description}</p>
      ) : null}
    </div>
  );
}
