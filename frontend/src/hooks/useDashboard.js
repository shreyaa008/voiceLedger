import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../services/api";
import { DEMO_SHOPKEEPER_ID } from "../config";

// Loads every customer + balance + risk in one go.
// Used by both the Ledger page and the Risk page.
export default function useDashboard() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await getDashboardSummary(DEMO_SHOPKEEPER_ID);
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