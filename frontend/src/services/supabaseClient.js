// frontend/src/services/supabaseClient.js
//
// The ONE place the frontend talks to Supabase Auth directly (sign up,
// log in, log out, session). VoiceLedger's own backend never sees a
// password — it only ever verifies the access_token this client hands
// it, via `Authorization: Bearer <token>` (see api.js).
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  // Fails loudly at startup rather than mysteriously later — every
  // Auth call would otherwise throw deep inside supabase-js.
  console.error(
    "Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY. Copy frontend/frontend.env.example to frontend/.env and fill them in."
  );
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);