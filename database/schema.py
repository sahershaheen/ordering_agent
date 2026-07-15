"""SQL schema for the restaurant database.

All statements use CREATE TABLE IF NOT EXISTS so initialization is
idempotent: running it against an existing database changes nothing.
"""

# Customers: one row per known customer, referenced by orders and feedback
CREATE_CUSTOMERS_TABLE = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name    TEXT NOT NULL,
    phone        TEXT NOT NULL UNIQUE,   -- phone is the natural lookup key
    email        TEXT                    -- optional; not every caller has one
);
"""

# Orders: one row per placed order
CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    order_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id      INTEGER NOT NULL,
    order_items      TEXT NOT NULL,       -- JSON string, e.g. '[{"item": "Zinger Burger", "qty": 2}]'
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    total_price      REAL NOT NULL CHECK (total_price >= 0),
    payment_method   TEXT NOT NULL CHECK (payment_method IN ('cash', 'credit_card',
                                                              'debit_card', 'jazzcash', 'easypaisa')),
    order_status     TEXT NOT NULL DEFAULT 'preparing'
                     CHECK (order_status IN ('preparing', 'cooking', 'out_for_delivery',
                                             'delivered', 'cancelled')),
    delivery_address TEXT,                -- NULL for dine-in / pickup orders
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);
"""

# Reservations: table bookings (kept independent of the customers table so
# a booking can be taken with just a name and phone number)
CREATE_RESERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name      TEXT NOT NULL,
    phone              TEXT NOT NULL,
    date               TEXT NOT NULL,     -- ISO format: YYYY-MM-DD
    time               TEXT NOT NULL,     -- 24h format: HH:MM
    guests             INTEGER NOT NULL CHECK (guests > 0),
    special_requests   TEXT,              -- e.g. "window seat, birthday cake"
    reservation_status TEXT NOT NULL DEFAULT 'confirmed'
                       CHECK (reservation_status IN ('confirmed', 'seated',
                                                     'completed', 'cancelled', 'no_show'))
);
"""

# Payments: one row per payment attempt, linked to its order
CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('cash', 'credit_card',
                                                            'debit_card', 'jazzcash', 'easypaisa')),
    payment_status TEXT NOT NULL DEFAULT 'pending'
                   CHECK (payment_status IN ('pending', 'paid', 'failed', 'refunded')),
    FOREIGN KEY (order_id) REFERENCES orders (order_id)
);
"""

# Feedback: customer ratings (1-5 stars) with optional comments
CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comments    TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);
"""

# Executed in this order so referenced tables exist before the tables
# that point at them (customers before orders, orders before payments)
ALL_TABLES: dict[str, str] = {
    "customers": CREATE_CUSTOMERS_TABLE,
    "orders": CREATE_ORDERS_TABLE,
    "reservations": CREATE_RESERVATIONS_TABLE,
    "payments": CREATE_PAYMENTS_TABLE,
    "feedback": CREATE_FEEDBACK_TABLE,
}
