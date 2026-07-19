"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  listAllOrders,
  listAllReservations,
  type OrderRecord,
  type ReservationRecord,
} from "@/lib/api";
import { Notice, PrimaryButton, Spinner } from "@/components/ui";

const ORDER_STATUS_STYLES: Record<string, string> = {
  preparing: "bg-brand-500/15 text-brand-300",
  cooking: "bg-brand-500/15 text-brand-300",
  out_for_delivery: "bg-sky-500/15 text-sky-300",
  delivered: "bg-emerald-500/15 text-emerald-300",
  cancelled: "bg-red-500/15 text-red-300",
};

const RESERVATION_STATUS_STYLES: Record<string, string> = {
  confirmed: "bg-emerald-500/15 text-emerald-300",
  seated: "bg-sky-500/15 text-sky-300",
  completed: "bg-surface-600 text-ink-300",
  cancelled: "bg-red-500/15 text-red-300",
  no_show: "bg-amber-500/15 text-amber-300",
};

export default function RecordsPage() {
  const [orders, setOrders] = useState<OrderRecord[] | null>(null);
  const [reservations, setReservations] = useState<ReservationRecord[] | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [orderRows, reservationRows] = await Promise.all([
        listAllOrders(),
        listAllReservations(),
      ]);
      setOrders(orderRows);
      setReservations(reservationRows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the records.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-100">
            Records
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Every order and reservation saved in the database — for cross-checking.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-sm text-brand-400 transition hover:text-brand-300"
          >
            ← Back to app
          </Link>
          <PrimaryButton type="button" onClick={load} disabled={busy}>
            {busy ? <Spinner /> : "Refresh"}
          </PrimaryButton>
        </div>
      </header>

      {error && (
        <div className="mt-6">
          <Notice kind="error">{error}</Notice>
        </div>
      )}

      <section className="mt-8">
        <h2 className="font-display text-xl text-brand-300">
          Orders {orders && <span className="text-sm text-ink-500">({orders.length})</span>}
        </h2>
        <div className="mt-3 overflow-x-auto rounded-2xl border border-surface-700 bg-surface-900/80">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-xs uppercase tracking-wide text-ink-500">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Items</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Payment</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Placed (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {orders?.length === 0 && (
                <EmptyRow colSpan={9} label="No orders yet." />
              )}
              {orders?.map((order) => (
                <tr key={order.order_id} className="border-b border-surface-800 align-top last:border-0">
                  <td className="px-4 py-3 font-semibold text-brand-300">{order.order_id}</td>
                  <td className="px-4 py-3 text-ink-100">{order.customer_name}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink-300">{order.phone}</td>
                  <td className="px-4 py-3 text-ink-300">
                    <ul className="space-y-0.5">
                      {order.items.map((item, i) => (
                        <li key={i}>
                          {item.qty} × {item.item}
                          <span className="text-ink-500"> @ {item.unit_price}</span>
                        </li>
                      ))}
                    </ul>
                    {order.delivery_address && (
                      <p className="mt-1 text-xs text-ink-500">→ {order.delivery_address}</p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink-100">
                    Rs. {order.total_price.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 capitalize text-ink-300">
                    {order.payment_method.replace("_", " ")}
                  </td>
                  <td className="px-4 py-3 capitalize text-ink-300">{order.order_type}</td>
                  <td className="px-4 py-3">
                    <StatusPill status={order.status} styles={ORDER_STATUS_STYLES} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink-500">{order.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-xl text-brand-300">
          Reservations{" "}
          {reservations && <span className="text-sm text-ink-500">({reservations.length})</span>}
        </h2>
        <div className="mt-3 overflow-x-auto rounded-2xl border border-surface-700 bg-surface-900/80">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-xs uppercase tracking-wide text-ink-500">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Guests</th>
                <th className="px-4 py-3">Special requests</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {reservations?.length === 0 && (
                <EmptyRow colSpan={8} label="No reservations yet." />
              )}
              {reservations?.map((reservation) => (
                <tr
                  key={reservation.reservation_id}
                  className="border-b border-surface-800 last:border-0"
                >
                  <td className="px-4 py-3 font-semibold text-brand-300">
                    {reservation.reservation_id}
                  </td>
                  <td className="px-4 py-3 text-ink-100">{reservation.customer_name}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink-300">{reservation.phone}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-ink-300">{reservation.date}</td>
                  <td className="px-4 py-3 text-ink-300">{reservation.time}</td>
                  <td className="px-4 py-3 text-ink-300">{reservation.guests}</td>
                  <td className="px-4 py-3 text-ink-500">
                    {reservation.special_requests ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill
                      status={reservation.status}
                      styles={RESERVATION_STATUS_STYLES}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function StatusPill({
  status,
  styles,
}: {
  status: string;
  styles: Record<string, string>;
}) {
  return (
    <span
      className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium capitalize
        ${styles[status] ?? "bg-surface-700 text-ink-300"}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-8 text-center text-sm text-ink-500">
        {label}
      </td>
    </tr>
  );
}
