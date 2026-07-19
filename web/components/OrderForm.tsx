"use client";

import { useState } from "react";
import { ApiError, placeOrder, type OrderResponse } from "@/lib/api";
import { Card, inputClass, labelClass, Notice, PrimaryButton, Spinner } from "@/components/ui";

interface ItemRow {
  item: string;
  qty: string;
  unit_price: string;
}

const EMPTY_ROW: ItemRow = { item: "", qty: "1", unit_price: "" };

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "credit card", label: "Credit Card" },
  { value: "debit card", label: "Debit Card" },
  { value: "jazzcash", label: "JazzCash" },
  { value: "easypaisa", label: "EasyPaisa" },
];

export default function OrderForm() {
  const [rows, setRows] = useState<ItemRow[]>([{ ...EMPTY_ROW }]);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [orderType, setOrderType] = useState<"delivery" | "takeaway">("delivery");
  const [address, setAddress] = useState("");
  const [payment, setPayment] = useState("cash");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OrderResponse | null>(null);

  const updateRow = (index: number, patch: Partial<ItemRow>) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const total = rows.reduce(
    (sum, row) => sum + (Number(row.qty) || 0) * (Number(row.unit_price) || 0),
    0,
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setResult(null);

    const items = rows
      .filter((row) => row.item.trim())
      .map((row) => ({
        item: row.item.trim(),
        qty: Number(row.qty) || 1,
        unit_price: Number(row.unit_price) || 0,
      }));
    if (items.length === 0) {
      setError("Add at least one item to the order.");
      return;
    }

    setBusy(true);
    try {
      const res = await placeOrder({
        full_name: fullName.trim(),
        phone: phone.trim(),
        items,
        payment_method: payment,
        delivery_address: orderType === "delivery" ? address.trim() : undefined,
        email: email.trim() || undefined,
      });
      setResult(res);
      setRows([{ ...EMPTY_ROW }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not place the order.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Place an order"
      subtitle="Structured checkout — or just ask the assistant in the Chat tab."
    >
      <form onSubmit={submit} className="space-y-4">
        {/* Items */}
        <div className="space-y-2">
          <span className={labelClass}>Items</span>
          {rows.map((row, i) => (
            <div key={i} className="flex gap-2">
              <input
                value={row.item}
                onChange={(event) => updateRow(i, { item: event.target.value })}
                placeholder="Item name (e.g. Rush Fire Burger)"
                className={inputClass}
              />
              <input
                value={row.qty}
                onChange={(event) => updateRow(i, { qty: event.target.value })}
                type="number"
                min={1}
                max={50}
                placeholder="Qty"
                className={`${inputClass} w-20`}
              />
              <input
                value={row.unit_price}
                onChange={(event) => updateRow(i, { unit_price: event.target.value })}
                type="number"
                min={0}
                step="0.01"
                placeholder="Price"
                className={`${inputClass} w-28`}
              />
              {rows.length > 1 && (
                <button
                  type="button"
                  onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                  className="shrink-0 rounded-lg px-2 text-ink-500 transition hover:text-red-400"
                  title="Remove item"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}
              className="text-xs text-brand-400 transition hover:text-brand-300"
            >
              + Add another item
            </button>
            <span className="text-sm text-ink-300">
              Total: <span className="font-semibold text-brand-300">Rs. {total.toFixed(2)}</span>
            </span>
          </div>
        </div>

        {/* Customer */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={labelClass}>Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required maxLength={100} placeholder="Ali Khan" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Phone</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} required minLength={7} maxLength={20} placeholder="+92 300 1234567" className={inputClass} />
          </div>
        </div>
        <div>
          <label className={labelClass}>Email (optional)</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" maxLength={100} placeholder="you@example.com" className={inputClass} />
        </div>

        {/* Delivery / takeaway */}
        <div>
          <span className={labelClass}>Order type</span>
          <div className="flex gap-2">
            {(["delivery", "takeaway"] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setOrderType(type)}
                className={`rounded-lg px-4 py-2 text-sm capitalize transition
                  ${
                    orderType === type
                      ? "bg-brand-500 font-semibold text-surface-950"
                      : "border border-surface-600 bg-surface-800 text-ink-300 hover:border-brand-500"
                  }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>
        {orderType === "delivery" && (
          <div>
            <label className={labelClass}>Delivery address</label>
            <input value={address} onChange={(e) => setAddress(e.target.value)} required maxLength={300} placeholder="House 12, Street 4, Johar Town, Lahore" className={inputClass} />
          </div>
        )}

        {/* Payment */}
        <div>
          <label className={labelClass}>Payment method</label>
          <select value={payment} onChange={(e) => setPayment(e.target.value)} className={inputClass}>
            {PAYMENT_METHODS.map((method) => (
              <option key={method.value} value={method.value}>
                {method.label}
              </option>
            ))}
          </select>
        </div>

        {error && <Notice kind="error">{error}</Notice>}
        {result && (
          <Notice kind="success">
            Order <strong>#{result.order_id}</strong> placed ({result.order_type}) — total Rs.{" "}
            {result.total_price.toFixed(2)}, estimated time {result.estimated_time}.
          </Notice>
        )}

        <PrimaryButton disabled={busy}>
          {busy ? <Spinner /> : "Place order"}
        </PrimaryButton>
      </form>
    </Card>
  );
}
