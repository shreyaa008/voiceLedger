-- Migration 002: add canonical_key to customers.
--
-- Purpose: "Shreya", "SHREYA", "shreya" and "श्रेया" are the same customer
-- but were, before this fix, matched with an exact/case-sensitive name
-- compare and so could each create a separate row. canonical_key stores a
-- script/case-insensitive identity key (see
-- backend/app/services/customer_identity.py for how it's computed) so
-- lookups and a future uniqueness constraint can rely on it directly.
--
-- SAFE TO RUN ANY TIME — purely additive, no existing data is changed or
-- deleted. New/updated customer rows get canonical_key automatically once
-- this column exists (backend/app/routers/transactions.py degrades
-- gracefully if it doesn't). Existing customer rows get it via the
-- one-time backfill in scripts/merge_duplicate_customers.py.
--
-- Run this BEFORE running:
--   python backend/scripts/merge_duplicate_customers.py --apply

ALTER TABLE customers ADD COLUMN IF NOT EXISTS canonical_key TEXT;

CREATE INDEX IF NOT EXISTS idx_customers_canonical_key
    ON customers(shopkeeper_id, canonical_key);

-- Do NOT add a UNIQUE constraint here yet if you already have duplicate
-- customers in the table — it will fail to apply until they're merged.
-- Once scripts/merge_duplicate_customers.py --apply has run, see
-- 003_customer_canonical_key_unique.sql to lock this in at the DB level.