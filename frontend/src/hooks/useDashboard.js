import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../services/api";

// Loads every customer + balance + risk in one go, scoped server-side to
// the signed-in shopkeeper (via the request's auth token — see api.js).
// Used by both the Ledger page and the Risk page.
export default function useDashboard() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await getDashboardSummary();
      setState({ loading: false, error: null, data });
    } catch (err) {
      setState({ loading: false, error: err.message || "Something went wrong", data: null });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}