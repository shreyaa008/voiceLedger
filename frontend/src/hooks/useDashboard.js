import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../services/api";
import { useShopkeeper } from "../context/ShopkeeperContext.jsx";

// Loads every customer + balance + risk in one go, scoped to the
// signed-in shopkeeper. Used by both the Ledger page and the Risk page.
export default function useDashboard() {
  const shopkeeper = useShopkeeper();
  const [state, setState] = useState({ loading: true, error: null, data: null });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await getDashboardSummary(shopkeeper.id);
      setState({ loading: false, error: null, data });
    } catch (err) {
      setState({ loading: false, error: err.message || "Something went wrong", data: null });
    }
  }, [shopkeeper.id]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}