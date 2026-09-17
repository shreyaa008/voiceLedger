-- shopkeepers table (multi-tenancy root)
CREATE TABLE shopkeepers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT UNIQUE,
    preferred_language TEXT CHECK (preferred_language IN ('hi', 'en')) DEFAULT 'hi',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- customers table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopkeeper_id UUID NOT NULL REFERENCES shopkeepers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customers_shopkeeper ON customers(shopkeeper_id);

-- transactions table
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL CHECK (amount > 0),
    type TEXT NOT NULL CHECK (type IN ('credit', 'payment')),
    date DATE NOT NULL,
    due_date DATE,               -- used by check_risk to compute days overdue
    raw_text TEXT,
    language TEXT CHECK (language IN ('hi', 'en')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_customer ON transactions(customer_id);
CREATE INDEX idx_transactions_date ON transactions(date);