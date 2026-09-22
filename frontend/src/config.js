// // One place for app-wide settings.
// //
// // TODO: replace with the logged-in shopkeeper once auth exists.
// // For now this is the id of a row in the "shopkeepers" table in Supabase.
// export const DEMO_SHOPKEEPER_ID = "178a88bd-46ed-45fb-b8a8-2a3949cee6c4";


// One place for app-wide settings.
//
// TODO: replace with the logged-in shopkeeper once auth exists.
// Reads from VITE_SHOPKEEPER_ID if set (see frontend.env.example),
// otherwise falls back to this demo row in Supabase's "shopkeepers" table.
export const DEMO_SHOPKEEPER_ID =
  import.meta.env.VITE_SHOPKEEPER_ID?.trim() || "178a88bd-46ed-45fb-b8a8-2a3949cee6c4";