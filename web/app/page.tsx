"use client";

import { useEffect, useState } from "react";
import Chat from "@/components/Chat";
import Header from "@/components/Header";
import Menu from "@/components/Menu";
import OrderForm from "@/components/OrderForm";
import ReservationForm from "@/components/ReservationForm";
import TrackOrder from "@/components/TrackOrder";

const TABS = [
  { id: "chat", label: "Chat & Voice" },
  { id: "menu", label: "Menu" },
  { id: "order", label: "Order" },
  { id: "track", label: "Track" },
  { id: "reserve", label: "Reserve" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Home() {
  const [tab, setTab] = useState<TabId>("chat");
  const [sessionId, setSessionId] = useState("");

  // One conversation per browser tab; created client-side after hydration.
  useEffect(() => {
    setSessionId(`web-${crypto.randomUUID().slice(0, 12)}`);
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <Header />

      <nav className="mt-6 flex flex-wrap gap-1 rounded-xl border border-surface-700 bg-surface-900/80 p-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition
              ${
                tab === id
                  ? "bg-brand-500 font-semibold text-surface-950"
                  : "text-ink-300 hover:bg-surface-800 hover:text-ink-100"
              }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-6">
        {/* Chat stays mounted so the conversation survives tab switches */}
        <div className={tab === "chat" ? "" : "hidden"}>
          {sessionId && <Chat sessionId={sessionId} />}
        </div>
        {tab === "menu" && <Menu />}
        {tab === "order" && <OrderForm />}
        {tab === "track" && <TrackOrder />}
        {tab === "reserve" && <ReservationForm />}
      </div>

      <footer className="mt-8 text-center text-xs text-ink-500">
        Powered by GPT-4o · answers grounded in the Flavour &amp; Rush knowledge base
      </footer>
    </main>
  );
}
