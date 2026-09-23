// One place for app-wide settings.
//
// DEMO_SHOPKEEPER_ID used to be applied to every device (see git history)
// — that was the root cause of the shared-ledger bug, since every
// shopkeeper was then the same row as far as the backend was concerned.
// Per-device identity now lives in ShopkeeperContext.jsx instead. This
// constant is kept only as the id of the pre-existing demo row in
// Supabase's "shopkeepers" table, offered as an explicit opt-in
// ("Continue as Demo Shop") on the sign-in screen so nobody loses access
// to data that was already saved under it.
export const DEMO_SHOPKEEPER_ID =
  import.meta.env.VITE_SHOPKEEPER_ID?.trim() || "178a88bd-46ed-45fb-b8a8-2a3949cee6c4";