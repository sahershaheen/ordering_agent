"""Reservation logic: booking, viewing, modifying and cancelling tables.

Structured in two layers:
    - Core functions (create_reservation, list_reservations,
      update_reservation, cancel_reservation_record): take/return plain
      data, raise exceptions on failure. Used by BOTH the agent tools and
      the FastAPI endpoints, so there is one source of truth.
    - @tool wrappers: translate between the LLM and the core functions.
"""

import sqlite3
from datetime import date, datetime

from langchain_core.tools import tool

from database.db import get_connection
from ingestion.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Core functions (shared by the agent tools and the API)
# ---------------------------------------------------------------------------

def _validate_date_time(date_iso: str | None, time_24h: str | None) -> None:
    """Validate date/time formats and reject past dates. Raises ValueError."""
    if date_iso is not None:
        try:
            parsed = datetime.strptime(date_iso, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.") from None
        if parsed < date.today():
            raise ValueError("The reservation date must not be in the past.")

    if time_24h is not None:
        try:
            datetime.strptime(time_24h, "%H:%M")
        except ValueError:
            raise ValueError("Invalid time format. Use HH:MM (24-hour).") from None


def create_reservation(
    customer_name: str,
    phone: str,
    date_iso: str,
    time_24h: str,
    guests: int,
    special_requests: str | None = None,
) -> dict:
    """Save a new reservation.

    Returns:
        Dict with the saved reservation's details, including its id.

    Raises:
        ValueError: On invalid date/time/guests.
        RuntimeError: If the database write fails.
    """
    _validate_date_time(date_iso, time_24h)
    if guests < 1:
        raise ValueError("Number of guests must be at least 1.")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO reservations (customer_name, phone, date, time, "
                "guests, special_requests, reservation_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'confirmed')",
                (customer_name, phone, date_iso, time_24h, guests, special_requests),
            )
            reservation_id = cursor.lastrowid
    except sqlite3.Error as exc:
        logger.exception("Failed to book reservation for %s", phone)
        raise RuntimeError("The reservation could not be saved.") from exc

    logger.info(
        "Reservation #%d booked: %s, %s %s, %d guests, requests=%s",
        reservation_id, customer_name, date_iso, time_24h, guests, special_requests,
    )
    return {
        "reservation_id": reservation_id,
        "customer_name": customer_name,
        "phone": phone,
        "date": date_iso,
        "time": time_24h,
        "guests": guests,
        "special_requests": special_requests,
        "status": "confirmed",
    }


def list_reservations(phone: str) -> list[dict]:
    """Return a customer's reservations (most recent first, up to 5).

    Raises:
        RuntimeError: If the database read fails.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT reservation_id, customer_name, phone, date, time, guests, "
                "special_requests, reservation_status FROM reservations "
                "WHERE phone = ? ORDER BY date DESC, time DESC LIMIT 5",
                (phone,),
            ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("Reservation lookup failed for %s", phone)
        raise RuntimeError("Reservation lookup failed.") from exc

    return [
        {
            "reservation_id": row["reservation_id"],
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "date": row["date"],
            "time": row["time"],
            "guests": row["guests"],
            "special_requests": row["special_requests"],
            "status": row["reservation_status"],
        }
        for row in rows
    ]


def update_reservation(
    reservation_id: int,
    phone: str,
    new_date_iso: str | None = None,
    new_time_24h: str | None = None,
    new_guests: int | None = None,
    new_special_requests: str | None = None,
) -> dict:
    """Modify an existing reservation. Only non-None fields are changed.

    Returns:
        The updated reservation details.

    Raises:
        ValueError: On invalid new values, no changes, or a cancelled booking.
        LookupError: If no reservation matches the id + phone.
        RuntimeError: If the database write fails.
    """
    _validate_date_time(new_date_iso, new_time_24h)
    if new_guests is not None and new_guests < 1:
        raise ValueError("Number of guests must be at least 1.")
    if all(v is None for v in (new_date_iso, new_time_24h, new_guests, new_special_requests)):
        raise ValueError("No changes were given.")

    try:
        with get_connection() as conn:
            # Verify the reservation exists, belongs to this phone number,
            # and is still active (cancelled bookings can't be modified)
            row = conn.execute(
                "SELECT reservation_status FROM reservations "
                "WHERE reservation_id = ? AND phone = ?",
                (reservation_id, phone),
            ).fetchone()

            if row is None:
                raise LookupError("No reservation found with that number and phone.")
            if row["reservation_status"] == "cancelled":
                raise ValueError(
                    f"Reservation #{reservation_id} was cancelled and cannot be modified."
                )

            # COALESCE keeps the current value for any field passed as None
            conn.execute(
                "UPDATE reservations SET "
                "date = COALESCE(?, date), "
                "time = COALESCE(?, time), "
                "guests = COALESCE(?, guests), "
                "special_requests = COALESCE(?, special_requests) "
                "WHERE reservation_id = ?",
                (new_date_iso, new_time_24h, new_guests, new_special_requests,
                 reservation_id),
            )

            # Read back the updated row so callers can confirm the details
            updated = conn.execute(
                "SELECT customer_name, phone, date, time, guests, special_requests, "
                "reservation_status FROM reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        logger.exception("Failed to modify reservation #%s", reservation_id)
        raise RuntimeError("The change could not be saved.") from exc

    logger.info("Reservation #%d modified", reservation_id)
    return {
        "reservation_id": reservation_id,
        "customer_name": updated["customer_name"],
        "phone": updated["phone"],
        "date": updated["date"],
        "time": updated["time"],
        "guests": updated["guests"],
        "special_requests": updated["special_requests"],
        "status": updated["reservation_status"],
    }


def cancel_reservation_record(reservation_id: int, phone: str) -> None:
    """Cancel a reservation (kept in the table for record-keeping).

    Raises:
        LookupError: If no reservation matches the id + phone.
        ValueError: If the reservation is already cancelled.
        RuntimeError: If the database write fails.
    """
    try:
        with get_connection() as conn:
            # Verify the reservation exists and belongs to this phone number
            row = conn.execute(
                "SELECT reservation_status FROM reservations "
                "WHERE reservation_id = ? AND phone = ?",
                (reservation_id, phone),
            ).fetchone()

            if row is None:
                raise LookupError("No reservation found with that number and phone.")
            if row["reservation_status"] == "cancelled":
                raise ValueError(f"Reservation #{reservation_id} is already cancelled.")

            conn.execute(
                "UPDATE reservations SET reservation_status = 'cancelled' "
                "WHERE reservation_id = ?",
                (reservation_id,),
            )
    except sqlite3.Error as exc:
        logger.exception("Failed to cancel reservation #%s", reservation_id)
        raise RuntimeError("The cancellation could not be processed.") from exc

    logger.info("Reservation #%d cancelled", reservation_id)


# ---------------------------------------------------------------------------
# Agent tools (thin wrappers around the core functions)
# ---------------------------------------------------------------------------

@tool
def book_reservation(
    customer_name: str,
    phone: str,
    date_iso: str,
    time_24h: str,
    guests: int,
    special_requests: str | None = None,
) -> str:
    """Book a table reservation after the customer confirms the details.

    Always ask the customer if they have any special requests (e.g. window
    seat, birthday arrangement, high chair) before booking; pass None if
    they have none.

    Args:
        customer_name: Name the reservation is under.
        phone: Customer's phone number.
        date_iso: Reservation date in YYYY-MM-DD format.
        time_24h: Reservation time in HH:MM 24-hour format.
        guests: Number of guests (must be at least 1).
        special_requests: Any special requests, or None.

    Returns:
        A confirmation with the reservation number, or an error message.
    """
    try:
        res = create_reservation(
            customer_name, phone, date_iso, time_24h, guests, special_requests
        )
    except ValueError as exc:
        return str(exc)  # validation problem the model can fix or relay
    except RuntimeError:
        return "Sorry, the reservation could not be saved. Please try again."

    requests_line = (
        f" Special requests: {res['special_requests']}." if res["special_requests"] else ""
    )
    return (
        f"Reservation #{res['reservation_id']} confirmed for {res['customer_name']}: "
        f"{res['date']} at {res['time']}, {res['guests']} guest(s).{requests_line} "
        "Tell the customer their reservation number."
    )


@tool
def get_reservations(phone: str) -> str:
    """Find a customer's reservations by phone number.

    Args:
        phone: The phone number the reservation was booked with.

    Returns:
        The customer's reservations (most recent first), or a not-found message.
    """
    try:
        reservations = list_reservations(phone)
    except RuntimeError:
        return "Sorry, reservation lookup is currently unavailable. Please try again."

    if not reservations:
        return (
            "No reservations found for that phone number. Politely tell the "
            "customer and ask them to double-check the number."
        )

    lines = [
        f"Reservation #{r['reservation_id']}: {r['customer_name']}, "
        f"{r['date']} at {r['time']}, {r['guests']} guest(s), "
        f"special requests: {r['special_requests'] or 'none'}, "
        f"status: {r['status']}"
        for r in reservations
    ]
    return "\n".join(lines)


@tool
def modify_reservation(
    reservation_id: int,
    phone: str,
    new_date_iso: str | None = None,
    new_time_24h: str | None = None,
    new_guests: int | None = None,
    new_special_requests: str | None = None,
) -> str:
    """Change the details of an existing reservation.

    Only pass the fields the customer wants to change; leave the rest as
    None to keep their current values. The phone number must match the one
    on the reservation.

    Args:
        reservation_id: The reservation number to modify.
        phone: The phone number the reservation was booked with.
        new_date_iso: New date in YYYY-MM-DD format, or None to keep.
        new_time_24h: New time in HH:MM 24-hour format, or None to keep.
        new_guests: New number of guests, or None to keep.
        new_special_requests: New special requests text, or None to keep.

    Returns:
        The updated reservation details, or an error/not-found message.
    """
    try:
        res = update_reservation(
            reservation_id, phone, new_date_iso, new_time_24h,
            new_guests, new_special_requests,
        )
    except LookupError:
        return (
            "No reservation found with that number and phone. "
            "Double-check the details with the customer."
        )
    except ValueError as exc:
        return str(exc)
    except RuntimeError:
        return "Sorry, the change could not be saved. Please try again."

    return (
        f"Reservation #{res['reservation_id']} updated: {res['customer_name']}, "
        f"{res['date']} at {res['time']}, {res['guests']} guest(s), "
        f"special requests: {res['special_requests'] or 'none'}. "
        "Confirm the updated details with the customer."
    )


@tool
def cancel_reservation(reservation_id: int, phone: str) -> str:
    """Cancel a reservation after the customer confirms they want to cancel.

    The phone number must match the one on the reservation, so customers
    can only cancel their own bookings.

    Args:
        reservation_id: The reservation number to cancel.
        phone: The phone number the reservation was booked with.

    Returns:
        A cancellation confirmation, or an error/not-found message.
    """
    try:
        cancel_reservation_record(reservation_id, phone)
    except LookupError:
        return (
            "No reservation found with that number and phone. "
            "Double-check the details with the customer."
        )
    except ValueError as exc:
        return str(exc)
    except RuntimeError:
        return "Sorry, the cancellation could not be processed. Please try again."

    return f"Reservation #{reservation_id} has been cancelled."
