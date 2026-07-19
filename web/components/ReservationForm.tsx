"use client";

import { useState } from "react";
import {
  ApiError,
  bookReservation,
  cancelReservation,
  type ReservationResponse,
} from "@/lib/api";
import { Card, inputClass, labelClass, Notice, PrimaryButton, Spinner } from "@/components/ui";

export default function ReservationForm() {
  return (
    <div className="space-y-6">
      <BookSection />
      <CancelSection />
    </div>
  );
}

function BookSection() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [guests, setGuests] = useState("2");
  const [requests, setRequests] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReservationResponse | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const res = await bookReservation({
        customer_name: name.trim(),
        phone: phone.trim(),
        date,
        time,
        guests: Number(guests),
        special_requests: requests.trim() || undefined,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not book the table.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Book a table" subtitle="Reserve for up to 50 guests.">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={labelClass}>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} placeholder="Sara Ahmed" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Phone</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} required minLength={7} maxLength={20} placeholder="+92 300 1234567" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Date</label>
            <input value={date} onChange={(e) => setDate(e.target.value)} required type="date" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Time</label>
            <input value={time} onChange={(e) => setTime(e.target.value)} required type="time" className={inputClass} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
          <div>
            <label className={labelClass}>Guests</label>
            <input value={guests} onChange={(e) => setGuests(e.target.value)} required type="number" min={1} max={50} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Special requests (optional)</label>
            <input value={requests} onChange={(e) => setRequests(e.target.value)} maxLength={300} placeholder="Window seat, birthday cake…" className={inputClass} />
          </div>
        </div>

        {error && <Notice kind="error">{error}</Notice>}
        {result && (
          <Notice kind="success">
            Reservation <strong>#{result.reservation_id}</strong> confirmed for{" "}
            {result.guests} guest{result.guests > 1 ? "s" : ""} on {result.date} at {result.time}.
            Keep the reservation number to modify or cancel.
          </Notice>
        )}

        <PrimaryButton disabled={busy}>{busy ? <Spinner /> : "Book table"}</PrimaryButton>
      </form>
    </Card>
  );
}

function CancelSection() {
  const [reservationId, setReservationId] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setDone(false);
    setBusy(true);
    try {
      await cancelReservation(Number(reservationId), phone.trim());
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not cancel the reservation.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Cancel a reservation"
      subtitle="The phone number must match the one used for booking."
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={labelClass}>Reservation number</label>
            <input value={reservationId} onChange={(e) => setReservationId(e.target.value)} required type="number" min={1} placeholder="e.g. 12" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Phone</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} required minLength={7} maxLength={20} placeholder="+92 300 1234567" className={inputClass} />
          </div>
        </div>

        {error && <Notice kind="error">{error}</Notice>}
        {done && <Notice kind="success">Reservation #{reservationId} has been cancelled.</Notice>}

        <PrimaryButton disabled={busy}>{busy ? <Spinner /> : "Cancel reservation"}</PrimaryButton>
      </form>
    </Card>
  );
}
