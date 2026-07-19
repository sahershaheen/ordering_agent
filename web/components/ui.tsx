/** Tiny shared building blocks so every panel looks consistent. */

export const inputClass =
  "w-full rounded-lg border border-surface-600 bg-surface-800 px-3 py-2 text-sm " +
  "text-ink-100 placeholder-ink-500 outline-none transition " +
  "focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50";

export const labelClass = "mb-1 block text-xs font-medium text-ink-300";

export function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-surface-700 bg-surface-900/80 p-5 shadow-lg shadow-black/30 backdrop-blur">
      <h2 className="font-display text-xl text-brand-300">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function PrimaryButton({
  children,
  disabled,
  type = "submit",
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  type?: "submit" | "button";
  onClick?: () => void;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2
                 text-sm font-semibold text-surface-950 transition hover:bg-brand-400
                 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

export function Notice({
  kind,
  children,
}: {
  kind: "error" | "success";
  children: React.ReactNode;
}) {
  const styles =
    kind === "error"
      ? "border-red-500/40 bg-red-500/10 text-red-300"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>
      {children}
    </div>
  );
}

export function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 animate-spin rounded-full border-2
                 border-surface-950/40 border-t-surface-950"
      aria-label="Loading"
    />
  );
}

/** 0..1 confidence rendered as a small labelled bar. */
export function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-500">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-700">
        <span
          className="block h-full rounded-full bg-brand-500"
          style={{ width: `${percent}%` }}
        />
      </span>
      {percent}% match
    </span>
  );
}
