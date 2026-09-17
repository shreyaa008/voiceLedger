-- customers table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    phone TEXT
);

-- transactions table
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    amount NUMERIC NOT NULL,
    type TEXT CHECK (type IN ('credit', 'payment')),
    date DATE NOT NULL,
    raw_text TEXT,
    language TEXT CHECK (language IN ('hi', 'en'))
);
