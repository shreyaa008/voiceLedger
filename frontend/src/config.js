// One place for app-wide settings.
//
// The old DEMO_SHOPKEEPER_ID / "Continue as Demo Shop" stand-in identity
// system is gone now that VoiceLedger uses real Supabase Auth (see
// ShopkeeperContext.jsx) — every shopkeeper_id now comes from an
// authenticated session, never a constant baked into the frontend.
export {};