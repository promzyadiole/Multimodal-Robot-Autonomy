type TopbarProps = {
  title: string;
  subtitle?: string;
};

/** Page header: an eyebrow rule, the title in the display face, then the note. */
export default function Topbar({ title, subtitle }: TopbarProps) {
  return (
    <header className="mb-8 border-b border-rule pb-5">
      <h2 className="font-display text-[2rem] leading-none tracking-[-0.01em] text-ink">
        {title}
      </h2>
      {subtitle ? (
        <p className="mt-2.5 max-w-2xl text-[13.5px] leading-relaxed text-ink-soft">
          {subtitle}
        </p>
      ) : null}
    </header>
  );
}
