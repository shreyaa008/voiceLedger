-- Links each shopkeeper row to a real Supabase Auth user, replacing the
-- old "identify by phone number" stand-in identity system.
--
-- After this migration, a shopkeeper_id is only ever reachable by first
-- proving you own the linked auth.users row (i.e. by holding a valid
-- Supabase Auth access token for that user) — see
-- backend/app/services/auth.py and backend/app/routers/shopkeepers.py.
--
-- Run this once against your Supabase project (SQL editor, or psql/CLI).
-- Existing rows in `shopkeepers`, `customers`, and `transactions` are left
-- untouched; user_id starts NULL for any pre-existing shopkeeper and is
-- filled in the first time that shopkeeper's owner signs up/logs in and
-- calls POST /shopkeepers/bootstrap.

ALTER TABLE shopkeepers
    ADD COLUMN IF NOT EXISTS user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_shopkeepers_user_id ON shopkeepers(user_id);

-- phone is kept (still shown in the shopkeeper's profile / used for
-- WhatsApp reminders to customers) but is no longer how a shopkeeper is
-- identified/authenticated, so it no longer needs to be globally unique.
ALTER TABLE shopkeepers DROP CONSTRAINT IF EXISTS shopkeepers_phone_key;

-- Optional but recommended defense-in-depth: turn on Row Level Security
-- so that even a leaked anon key, or a future bug that swaps to the anon
-- client, can't read/write another shopkeeper's rows. The FastAPI backend
-- in this project enforces ownership itself on every route (see
-- app/services/auth.py) using the service-role key, which bypasses RLS,
-- so this is not required for the backend to be safe — it's an extra
-- layer for defense-in-depth if you ever query Supabase directly from a
-- client with the anon key.
--
-- ALTER TABLE shopkeepers ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY shopkeepers_self ON shopkeepers
--     FOR ALL USING (user_id = auth.uid());
--
-- ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY customers_owner ON customers
--     FOR ALL USING (
--         shopkeeper_id IN (SELECT id FROM shopkeepers WHERE user_id = auth.uid())
--     );
--
-- ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY transactions_owner ON transactions
--     FOR ALL USING (
--         customer_id IN (
--             SELECT c.id FROM customers c
--             JOIN shopkeepers s ON s.id = c.shopkeeper_id
--             WHERE s.user_id = auth.uid()
--         )
--     );