"use client";

import { useState } from "react";
import { ApiError, searchMenu, type MenuPassage } from "@/lib/api";
import { Card, ConfidenceBar, inputClass, Notice, PrimaryButton, Spinner } from "@/components/ui";

const QUICK_FILTERS = [
  "Full menu with prices",
  "Burgers",
  "Pizza",
  "Spicy dishes",
  "Desserts",
  "Drinks",
  "Deals",
];

export default function Menu() {
  const [query, setQuery] = useState("");
  const [passages, setPassages] = useState<MenuPassage[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async (term: string) => {
    const trimmed = term.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await searchMenu(trimmed);
      setPassages(res.passages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Menu search failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Menu explorer"
      subtitle="Search the restaurant's knowledge base — dishes, prices, deals, and policies."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          search(query);
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. spicy burgers, family deals, vegetarian options…"
          className={inputClass}
        />
        <PrimaryButton disabled={busy || !query.trim()}>
          {busy ? <Spinner /> : "Search"}
        </PrimaryButton>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            disabled={busy}
            onClick={() => {
              setQuery(filter);
              search(filter);
            }}
            className="rounded-full border border-surface-600 bg-surface-800 px-3 py-1 text-xs
                       text-ink-300 transition hover:border-brand-500 hover:text-brand-300
                       disabled:opacity-50"
          >
            {filter}
          </button>
        ))}
      </div>

      {error && <div className="mt-4"><Notice kind="error">{error}</Notice></div>}

      {passages && !error && (
        <div className="mt-4 space-y-3">
          {passages.length === 0 && (
            <p className="text-sm text-ink-500">No matching menu information found.</p>
          )}
          {passages.map((passage, i) => (
            <article
              key={i}
              className="rounded-xl border border-surface-700 bg-surface-800/70 p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-xs font-medium text-brand-300">
                  Page {passage.page}
                </span>
                <ConfidenceBar value={passage.confidence} />
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-100">
                {passage.content}
              </p>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}
