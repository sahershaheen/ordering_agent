"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth } from "@/lib/api";

type Status = "checking" | "online" | "degraded" | "offline";

const STATUS_STYLES: Record<Status, { dot: string; label: string }> = {
  checking: { dot: "bg-ink-500", label: "Checking…" },
  online: { dot: "bg-emerald-400", label: "All systems online" },
  degraded: { dot: "bg-amber-400", label: "Degraded" },
  offline: { dot: "bg-red-400", label: "Backend offline" },
};

export default function Header() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const health = await getHealth();
        if (!cancelled) {
          setStatus(health.status === "ok" ? "online" : "degraded");
        }
      } catch {
        if (!cancelled) setStatus("offline");
      }
    };
    check();
    const timer = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const { dot, label } = STATUS_STYLES[status];

  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-100">
          Flavour <span className="text-brand-400">&amp;</span> Rush
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          AI-powered ordering &amp; table booking — chat, speak, or use the forms.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Link
          href="/records"
          className="inline-flex items-center gap-2 rounded-full border border-surface-700
                     bg-surface-900 px-3 py-1.5 text-xs text-ink-300 transition
                     hover:border-brand-500 hover:text-brand-300"
          title="All saved orders and reservations"
        >
          Records
        </Link>
        <span
          className="inline-flex items-center gap-2 rounded-full border border-surface-700
                     bg-surface-900 px-3 py-1.5 text-xs text-ink-300"
          title="Live status of the FastAPI backend"
        >
          <span className={`h-2 w-2 rounded-full ${dot}`} />
          {label}
        </span>
      </div>
    </header>
  );
}
