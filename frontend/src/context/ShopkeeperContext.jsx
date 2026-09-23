import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { identifyShopkeeper } from "../services/api";
import { DEMO_SHOPKEEPER_ID } from "../config";

// Root cause of the shared-ledger bug: every browser used the same
// hardcoded DEMO_SHOPKEEPER_ID, so two different shopkeepers were, as
// far as the backend/database were concerned, literally the same
// shopkeeper. There's no auth system in this project yet, so this is
// the smallest safe stand-in: each device remembers its own
// shopkeeper identity (get-or-created by phone number via
// POST /shopkeepers/identify) in localStorage, and every API call uses
// that instead of the shared constant.
const STORAGE_KEY = "voiceledger_shopkeeper";

const ShopkeeperContext = createContext(null);

function loadStored() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveStored(shopkeeper) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(shopkeeper));
  } catch {
    // localStorage unavailable (private mode, etc.) — identity just
    // won't persist across reloads; not fatal.
  }
}

export function ShopkeeperProvider({ children }) {
  const [shopkeeper, setShopkeeper] = useState(() => loadStored());
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const signIn = useCallback(async (name, phone) => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await identifyShopkeeper(name, phone);
      setShopkeeper(res.shopkeeper);
      saveStored(res.shopkeeper);
    } catch (err) {
      setError(err.message || "Could not sign in");
    } finally {
      setSubmitting(false);
    }
  }, []);

  // Explicit opt-in, not a default: lets whoever owns the pre-existing
  // demo data (created under the old shared id before this fix) get
  // back to it on one device. Everyone else picks their own name/phone
  // above and gets a real, isolated shopkeeper_id.
  const continueAsDemo = useCallback(() => {
    const demo = { id: DEMO_SHOPKEEPER_ID, name: "Demo Shop", phone: null };
    setShopkeeper(demo);
    saveStored(demo);
  }, []);

  if (!shopkeeper) {
    return (
      <SignInGate
        onSignIn={signIn}
        onContinueAsDemo={continueAsDemo}
        error={error}
        submitting={submitting}
      />
    );
  }

  return (
    <ShopkeeperContext.Provider value={shopkeeper}>
      {children}
    </ShopkeeperContext.Provider>
  );
}

export function useShopkeeper() {
  const shopkeeper = useContext(ShopkeeperContext);
  if (!shopkeeper) {
    throw new Error("useShopkeeper() must be used inside <ShopkeeperProvider>");
  }
  return shopkeeper;
}

function SignInGate({ onSignIn, onContinueAsDemo, error, submitting }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !phone.trim()) return;
    onSignIn(name.trim(), phone.trim());
  }

  return (
    <div className="page" style={{ maxWidth: 360, margin: "10vh auto" }}>
      <div className="page-header">
        <h2>Welcome to VoiceLedger</h2>
        <p className="page-subtitle">Tell us who's keeping this khata.</p>
      </div>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input
          className="search-input"
          placeholder="Your name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Your name"
        />
        <input
          className="search-input"
          placeholder="Phone number"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          aria-label="Phone number"
        />
        {error && <p className="inline-error">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Signing in..." : "Continue"}
        </button>
      </form>
      <button
        className="btn btn-secondary"
        style={{ marginTop: 12 }}
        onClick={onContinueAsDemo}
        type="button"
      >
        Continue as Demo Shop (existing sample data)
      </button>
    </div>
  );
}