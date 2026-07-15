"""Order logic: placing new orders and tracking existing ones (SQLite-backed).

Structured in two layers:
    - Core functions (create_order, find_orders): take/return plain data,
      raise exceptions on failure. Used by BOTH the agent tools and the
      FastAPI endpoints, so there is one source of truth.
    - @tool wrappers (place_order, track_order): translate between the LLM
      (JSON strings in, readable text out) and the core functions.
"""

import json
import sqlite3

from langchain_core.tools import tool

from database.db import get_connection
from ingestion.logger import get_logger

logger = get_logger(__name__)

# The payment options offered to customers, mapped to their database values.
# Keys cover the natural ways a customer/model might phrase each option.
PAYMENT_METHOD_ALIASES = {
    "cash": "cash",
    "credit card": "credit_card",
    "credit_card": "credit_card",
    "debit card": "debit_card",
    "debit_card": "debit_card",
    "card": "credit_card",
    "jazzcash": "jazzcash",
    "jazz cash": "jazzcash",
    "easypaisa": "easypaisa",
    "easy paisa": "easypaisa",
}

# Estimated preparation/delivery windows quoted in the order summary.
# The delivery window matches the restaurant's published delivery policy
# in the knowledge base (standard delivery: 30-50 minutes).
DELIVERY_ESTIMATE = "30-50 minutes"
TAKEAWAY_ESTIMATE = "15-20 minutes"

# Customer-friendly wording for each order status stored in the database
STATUS_LABELS = {
    "preparing": "Preparing — the kitchen has received the order",
    "cooking": "Cooking — the food is being cooked right now",
    "out_for_delivery": "Out for Delivery — the rider is on the way",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


# ---------------------------------------------------------------------------
# Core functions (shared by the agent tools and the API)
# ---------------------------------------------------------------------------

def _get_or_create_customer(
    conn: sqlite3.Connection, full_name: str, phone: str, email: str | None
) -> int:
    """Find a customer by phone number, or create them if new.

    Phone is the natural key: returning customers are recognised by it,
    and their name/email are refreshed with the latest values given.
    """
    row = conn.execute(
        "SELECT customer_id FROM customers WHERE phone = ?", (phone,)
    ).fetchone()

    if row is not None:
        # Existing customer: update details in case they changed
        conn.execute(
            "UPDATE customers SET full_name = ?, email = COALESCE(?, email) "
            "WHERE customer_id = ?",
            (full_name, email, row["customer_id"]),
        )
        return row["customer_id"]

    # New customer: insert and return the generated id
    cursor = conn.execute(
        "INSERT INTO customers (full_name, phone, email) VALUES (?, ?, ?)",
        (full_name, phone, email),
    )
    return cursor.lastrowid


def create_order(
    full_name: str,
    phone: str,
    items: list[dict],
    total_price: float,
    payment_method: str,
    delivery_address: str | None = None,
    email: str | None = None,
) -> dict:
    """Save an order (customer + order + pending payment, one transaction).

    Args:
        full_name: Customer's full name.
        phone: Customer's phone number.
        items: List of {"item": name, "qty": n, "unit_price": price} dicts.
        total_price: Total order price.
        payment_method: One of the accepted payment options (aliases ok).
        delivery_address: Full address for delivery, None for takeaway.
        email: Optional email.

    Returns:
        Dict with order_id, order_type, total_price, payment_method,
        estimated_time, items, and delivery_address.

    Raises:
        ValueError: On an invalid payment method or empty items list.
        RuntimeError: If the database write fails.
    """
    # --- Validate inputs before touching the database ---------------------
    normalized = payment_method.strip().lower()
    if normalized not in PAYMENT_METHOD_ALIASES:
        raise ValueError(
            f"Invalid payment method '{payment_method}'. Accepted: "
            "cash, credit card, debit card, JazzCash, or EasyPaisa."
        )
    payment_method = PAYMENT_METHOD_ALIASES[normalized]

    if not items:
        raise ValueError("An order must contain at least one item.")

    # Total quantity across all line items (schema stores one number)
    total_quantity = sum(int(item.get("qty", 1)) for item in items)

    # --- Save customer, order and pending payment in ONE transaction ------
    try:
        with get_connection() as conn:
            customer_id = _get_or_create_customer(conn, full_name, phone, email)

            cursor = conn.execute(
                "INSERT INTO orders (customer_id, order_items, quantity, "
                "total_price, payment_method, order_status, delivery_address) "
                "VALUES (?, ?, ?, ?, ?, 'preparing', ?)",
                (
                    customer_id,
                    json.dumps(items, ensure_ascii=False),
                    total_quantity,
                    total_price,
                    payment_method,
                    delivery_address,
                ),
            )
            order_id = cursor.lastrowid

            # Record the payment as pending; it is settled on delivery/pickup
            conn.execute(
                "INSERT INTO payments (order_id, payment_method, payment_status) "
                "VALUES (?, ?, 'pending')",
                (order_id, payment_method),
            )
    except sqlite3.Error as exc:
        logger.exception("Failed to save order for phone %s", phone)
        raise RuntimeError("The order could not be saved.") from exc

    logger.info(
        "Order #%d placed: customer=%d, items=%d, total=%.2f, payment=%s",
        order_id,
        customer_id,
        total_quantity,
        total_price,
        payment_method,
    )

    is_delivery = delivery_address is not None
    return {
        "order_id": order_id,
        "order_type": "delivery" if is_delivery else "takeaway",
        "items": items,
        "total_price": total_price,
        "payment_method": payment_method,
        "delivery_address": delivery_address,
        "estimated_time": DELIVERY_ESTIMATE if is_delivery else TAKEAWAY_ESTIMATE,
    }


def find_orders(phone: str | None = None, order_id: int | None = None) -> list[dict]:
    """Look up orders by order id or phone number (most recent first).

    Args:
        phone: Customer's phone number (used if order_id is not given).
        order_id: Specific order number to look up.

    Returns:
        A list of order dicts (empty if nothing matches).

    Raises:
        ValueError: If neither phone nor order_id is provided.
        RuntimeError: If the database read fails.
    """
    if order_id is None and not phone:
        raise ValueError("Provide an order number or a phone number.")

    try:
        with get_connection() as conn:
            if order_id is not None:
                rows = conn.execute(
                    "SELECT o.order_id, o.order_items, o.total_price, "
                    "o.order_status, o.delivery_address, o.created_at "
                    "FROM orders o WHERE o.order_id = ?",
                    (order_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT o.order_id, o.order_items, o.total_price, "
                    "o.order_status, o.delivery_address, o.created_at "
                    "FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
                    "WHERE c.phone = ? ORDER BY o.created_at DESC LIMIT 3",
                    (phone,),
                ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("Order lookup failed")
        raise RuntimeError("Order lookup failed.") from exc

    return [
        {
            "order_id": row["order_id"],
            "order_type": "delivery" if row["delivery_address"] else "takeaway",
            "status": row["order_status"],
            "status_label": STATUS_LABELS.get(row["order_status"], row["order_status"]),
            "items": json.loads(row["order_items"]),
            "total_price": row["total_price"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Agent tools (thin wrappers around the core functions)
# ---------------------------------------------------------------------------

@tool
def place_order(
    full_name: str,
    phone: str,
    items_json: str,
    total_price: float,
    payment_method: str,
    delivery_address: str | None = None,
    email: str | None = None,
) -> str:
    """Save a customer order to the restaurant database.

    Call this once you have collected: the items and quantities (verified
    against the knowledge base), the customer's name and phone, delivery
    address (for delivery orders), and the payment method.

    Args:
        full_name: Customer's full name.
        phone: Customer's phone number.
        items_json: The ordered items as a JSON array string, e.g.
            '[{"item": "Zinger Burger", "qty": 2, "unit_price": 599}]'.
            Item names and prices must come from the knowledge base.
        total_price: Total order price (verified against knowledge-base prices).
        payment_method: One of "cash", "credit card", "debit card",
            "jazzcash", or "easypaisa".
        delivery_address: Full delivery address; omit for takeaway orders.
        email: Customer's email address (optional).

    Returns:
        A full order summary with the order number and estimated time,
        or an error message.
    """
    # --- Parse the LLM's JSON items string --------------------------------
    try:
        items = json.loads(items_json)
        assert isinstance(items, list)
    except (json.JSONDecodeError, AssertionError):
        return "items_json must be a JSON array of order items."

    # --- Delegate to the core function ------------------------------------
    try:
        order = create_order(
            full_name=full_name,
            phone=phone,
            items=items,
            total_price=total_price,
            payment_method=payment_method,
            delivery_address=delivery_address,
            email=email,
        )
    except ValueError as exc:
        return str(exc)  # validation problem the model can fix or relay
    except RuntimeError:
        return "Sorry, the order could not be saved due to a system error. Please try again."

    # --- Format the order summary the agent reads back --------------------
    if order["order_type"] == "delivery":
        estimate_line = f"Estimated delivery time: {order['estimated_time']}"
        address_line = f"Delivering to: {order['delivery_address']}\n"
    else:
        estimate_line = (
            f"Estimated time until ready for pickup: {order['estimated_time']}"
        )
        address_line = ""

    item_lines = "\n".join(
        f"  - {item.get('item', 'item')} x{item.get('qty', 1)}" for item in items
    )
    return (
        f"Order #{order['order_id']} placed successfully ({order['order_type']}).\n"
        f"Items:\n{item_lines}\n"
        f"Total: Rs. {order['total_price']:.0f}\n"
        f"Payment: {order['payment_method']}\n"
        f"{address_line}"
        f"{estimate_line}\n"
        "Read this summary back to the customer, including their order number."
    )


@tool
def track_order(phone: str | None = None, order_id: int | None = None) -> str:
    """Look up the status of a customer's order(s).

    Provide the order_id if the customer knows it; otherwise provide their
    phone number to find their recent orders.

    Possible statuses: Preparing, Cooking, Out for Delivery, Delivered,
    Cancelled.

    Args:
        phone: Customer's phone number (used if order_id is not given).
        order_id: The order number to look up.

    Returns:
        The matching order(s) with status and details, or a not-found message.
    """
    try:
        orders = find_orders(phone=phone, order_id=order_id)
    except ValueError:
        return "Ask the customer for their order number or phone number."
    except RuntimeError:
        return "Sorry, order lookup is currently unavailable. Please try again."

    if not orders:
        # Not found: instruct the model to break the news politely
        if order_id is not None:
            return (
                f"No order found with order number {order_id}. Politely tell "
                "the customer you couldn't find it and ask them to double-check "
                "the order number, or offer to look it up by phone number instead."
            )
        return (
            "No orders found for that phone number. Politely tell the customer "
            "and ask them to double-check the number."
        )

    # --- Format each order into a readable status line ---------------------
    lines = [
        f"Order #{o['order_id']} ({o['order_type']}): status: {o['status_label']}. "
        f"Items: {json.dumps(o['items'])}, total: Rs. {o['total_price']:.0f}, "
        f"placed at {o['created_at']} (UTC)"
        for o in orders
    ]
    return "\n".join(lines)
