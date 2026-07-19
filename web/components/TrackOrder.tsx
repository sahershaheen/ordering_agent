"use client";

import { useState } from "react";
import { ApiError, trackOrders, type OrderStatus } from "@/lib/api";
import { Card, inputClass, labelClass, Notice, PrimaryButton, Spinner } from "@/components/ui";

/** Order pipeline; cancelled is handled separately since it's not a stage. */
const STAGES = ["preparing", "cooking", "out_for_delivery", "delivered"];
const STAGE_LABELS: Record<string, string> = {
  preparing: "Preparing",
  cooking: "Cooking",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
};

export default function TrackOrder() {
  const [orderId, setOrderId] = useState("");
  const [phone, setPhone] = useState("");
  const [orders, setOrders] = useState<OrderStatus[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!orderId.trim() && !phone.trim()) {
      setError("Enter an order number or a phone number.");
      return;
    }
    setError(null);
    setOrders(null);
    setBusy(true);
    try {
      const res = await trackOrders({
        order_id: orderId.trim() || undefined,
        phone: phone.trim() || undefined,
      });
      setOrders(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("No matching orders found — double-check the order number or phone.");
      } else {
        setError(err instanceof ApiError ? err.message : "Could not look up the order.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Track your order"
      subtitle="Look up by order number, or see all your orders by phone."
    >
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-36 flex-1">
          <label className={labelClass}>Order number</label>
          <input value={orderId} onChange={(e) => setOrderId(e.target.value)} type="number" min={1} placeholder="e.g. 7" className={inputClass} />
        </div>
        <span className="pb-2 text-xs text-ink-500">or</span>
        <div className="min-w-48 flex-1">
          <label className={labelClass}>Phone</label>
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+92 300 1234567" className={inputClass} />
        </div>
        <PrimaryButton disabled={busy}>{busy ? <Spinner /> : "Track"}</PrimaryButton>
      </form>

      {error && <div className="mt-4"><Notice kind="error">{error}</Notice></div>}

      {orders && (
        <div className="mt-5 space-y-4">
          {orders.map((order) => (
            <OrderCard key={order.order_id} order={order} />
          ))}
        </div>
      )}
    </Card>
  );
}

function OrderCard({ order }: { order: OrderStatus }) {
  const cancelled = order.status === "cancelled";
  const currentStage = STAGES.indexOf(order.status);

  return (
    <article className="rounded-xl border border-surface-700 bg-surface-800/70 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="font-semibold text-ink-100">Order #{order.order_id}</span>
          <span className="ml-2 text-xs capitalize text-ink-500">
            {order.order_type} · {order.created_at}
          </span>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium
            ${
              cancelled
                ? "bg-red-500/15 text-red-300"
                : order.status === "delivered"
                  ? "bg-emerald-500/15 text-emerald-300"
                  : "bg-brand-500/15 text-brand-300"
            }`}
        >
          {order.status_label}
        </span>
      </div>

      {/* Progress timeline */}
      {!cancelled && (
        <ol className="mb-3 flex items-center">
          {STAGES.map((stage, i) => {
            const reached = i <= currentStage;
            return (
              <li key={stage} className="flex flex-1 items-center last:flex-none">
                <div className="flex flex-col items-center">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold
                      ${reached ? "bg-brand-500 text-surface-950" : "bg-surface-700 text-ink-500"}`}
                  >
                    {reached ? "✓" : i + 1}
                  </span>
                  <span className={`mt-1 whitespace-nowrap text-[10px] ${reached ? "text-brand-300" : "text-ink-500"}`}>
                    {STAGE_LABELS[stage]}
                  </span>
                </div>
                {i < STAGES.length - 1 && (
                  <span className={`mx-1 mb-4 h-0.5 flex-1 rounded ${i < currentStage ? "bg-brand-500" : "bg-surface-700"}`} />
                )}
              </li>
            );
          })}
        </ol>
      )}

      <ul className="space-y-1 text-sm text-ink-300">
        {order.items.map((item, i) => (
          <li key={i} className="flex justify-between">
            <span>
              {item.qty} × {item.item}
            </span>
            <span>Rs. {(item.qty * item.unit_price).toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 border-t border-surface-700 pt-2 text-right text-sm font-semibold text-brand-300">
        Total: Rs. {order.total_price.toFixed(2)}
      </p>
    </article>
  );
}
