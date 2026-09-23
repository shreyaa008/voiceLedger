import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { supabase } from "../services/supabaseClient";
import { bootstrapShopkeeper, getMyShopkeeper } from "../services/api";

// Real identity, backed by Supabase Auth.
//
// Root cause of the old shared-ledger bug: every browser used the same
// hardcoded DEMO_SHOPKEEPER_ID, so two different shopkeepers were, as
// far as the backend/database were concerned, literally the same
// shopkeeper. The per-device localStorage identity that replaced it was
// only ever a stand-in — anyone could open devtools and set any
// shopkeeper_id they liked. This is the real fix: a shopkeeper now signs
// up / logs in with Supabase Auth (email + password), and every
// shopkeeper_id used anywhere in the app comes from the backend, which
// derives it from the verified session — never from anything stored on
// the device.
const ShopkeeperContext = createContext(null);

export function ShopkeeperProvider({ children }) {
  // session: undefined = not checked yet, null = signed out, object = signed in
  const [session, setSession] = useState(undefined);
  const [shopkeeper, setShopkeeper] = useState(null);
  const [shopkeeperLoading, setShopkeeperLoading] = useState(false);
  const [shopkeeperError, setShopkeeperError] = useState(null);

  // Track the Supabase Auth session itself — sign up, log in, log out,
  // and token refresh all flow through this one listener.
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  // Once signed in, resolve (or create) this account's shopkeeper row.
  // GET /shopkeepers/me 404s the first time a brand-new account logs in
  // — that's expected right after sign up, and onboarding (below)
  // completes it via POST /shopkeepers/bootstrap.
  const loadShopkeeper = useCallback(async () => {
    setShopkeeperLoading(true);
    setShopkeeperError(null);
    try {
      const res = await getMyShopkeeper();
      setShopkeeper(res.shopkeeper);
    } catch (err) {
      if (err.kind === "not_found") {
        setShopkeeper(null); // needs onboarding
      } else {
        setShopkeeperError(err.message || "Could not load your shop");
      }
    } finally {
      setShopkeeperLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session) {
      loadShopkeeper();
    } else {
      setShopkeeper(null);
    }
  }, [session, loadShopkeeper]);

  const completeOnboarding = useCallback(async (name, phone) => {
    setShopkeeperLoading(true);
    setShopkeeperError(null);
    try {
      const res = await bootstrapShopkeeper(name, phone);
      setShopkeeper(res.shopkeeper);
    } catch (err) {
      setShopkeeperError(err.message || "Could not set up your shop");
    } finally {
      setShopkeeperLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setShopkeeper(null);
  }, []);

  // Still resolving the initial session — avoid flashing the login screen.
  if (session === undefined) {
    return null;
  }

  if (!session) {
    return <AuthGate />;
  }

  if (shopkeeperLoading && shopkeeper === null) {
    return <div className="page" style={{ maxWidth: 360, margin: "10vh auto" }}>Loading your shop…</div>;
  }

  if (!shopkeeper) {
    return (
      <OnboardingGate
        email={session.user?.email}
        onComplete={completeOnboarding}
        error={shopkeeperError}
        submitting={shopkeeperLoading}
        onSignOut={signOut}
      />
    );
  }

  return (
    <ShopkeeperContext.Provider value={{ ...shopkeeper, signOut, email: session.user?.email }}>
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

// ---------- Sign up / log in ----------

function AuthGate() {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setSubmitting(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "signup") {
        const { error: signUpError, data } = await supabase.auth.signUp({
          email: email.trim(),
          password,
        });
        if (signUpError) throw signUpError;
        // If email confirmation is enabled on this Supabase project,
        // there's no session yet — tell the shopkeeper to check email
        // instead of leaving them looking at nothing.
        if (!data.session) {
          setInfo("Account created — check your email to confirm, then log in.");
          setMode("login");
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (signInError) throw signInError;
      }
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 360, margin: "10vh auto" }}>
      <div className="page-header">
        <h2>Welcome to VoiceLedger</h2>
        <p className="page-subtitle">
          {mode === "signup" ? "Create an account to start your khata." : "Log in to your khata."}
        </p>
      </div>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input
          className="search-input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          aria-label="Email"
        />
        <input
          className="search-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          aria-label="Password"
        />
        {error && <p className="inline-error">{error}</p>}
        {info && <p className="page-subtitle">{info}</p>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting
            ? mode === "signup"
              ? "Signing up..."
              : "Logging in..."
            : mode === "signup"
            ? "Sign up"
            : "Log in"}
        </button>
      </form>
      <button
        className="btn btn-secondary"
        style={{ marginTop: 12 }}
        type="button"
        onClick={() => {
          setMode(mode === "signup" ? "login" : "signup");
          setError(null);
          setInfo(null);
        }}
      >
        {mode === "signup" ? "Already have an account? Log in" : "New here? Sign up"}
      </button>
    </div>
  );
}

// Shown exactly once per account, right after the first successful
// sign up / login: turns the Supabase Auth user into a VoiceLedger
// shopkeeper (POST /shopkeepers/bootstrap).
function OnboardingGate({ email, onComplete, error, submitting, onSignOut }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    onComplete(name.trim(), phone.trim());
  }

  return (
    <div className="page" style={{ maxWidth: 360, margin: "10vh auto" }}>
      <div className="page-header">
        <h2>Set up your shop</h2>
        <p className="page-subtitle">Signed in as {email}. Tell us who's keeping this khata.</p>
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
          placeholder="Phone number (optional)"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          aria-label="Phone number"
        />
        {error && <p className="inline-error">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Setting up..." : "Continue"}
        </button>
      </form>
      <button className="btn btn-secondary" style={{ marginTop: 12 }} type="button" onClick={onSignOut}>
        Log out
      </button>
    </div>
  );
}