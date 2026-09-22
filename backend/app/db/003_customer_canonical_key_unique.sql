-- Migration 003: enforce customer identity uniqueness at the DB level.
--
-- Run this ONLY after:
--   1. 002_customer_canonical_key.sql has been applied, AND
--   2. python backend/scripts/merge_duplicate_customers.py --apply
--      has merged any existing duplicate customers.
--
-- Until existing duplicates are merged, this constraint will fail to
-- apply (that failure is expected and safe — it just means step 2 above
-- hasn't been done yet; no data is at risk).
--
-- After this, the database itself refuses to create a second customer
-- with the same canonical_key for the same shopkeeper — belt-and-braces
-- alongside the app-level check in transactions.py.

ALTER TABLE customers
    ADD CONSTRAINT customers_shopkeeper_canonical_key_uniq
    UNIQUE (shopkeeper_id, canonical_key);