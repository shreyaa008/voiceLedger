"""
Shared, shopkeeper-scoped data access.

Anything that needs "this shopkeeper's customers and transactions" — the
Ledger/Risk screens (routers/dashboard.py) and the read-only ASK tools
(agent/tools/*.py) — goes through the exact same functions here. That is
what guarantees ASK and the Ledger page can never disagree with each
other, and that ASK can never see another shopkeeper's data: there is
only one place that queries these tables, and every query is scoped by
shopkeeper_id.

fetch_transactions() also pages past Supabase's 1000-row-per-request
limit, so totals for a shop with a long history are never silently
truncated (this was the root cause of incorrect totals like "₹86,400"
coming out of the old search_transactions tool, which fetched all
transactions for ALL shopkeepers in one un-paginated request).
"""
from app.services.customer_identity import canonical_key
from app.services.supabase_client import supabase

PAGE_SIZE = 1000  # Supabase returns at most 1000 rows per request


def fetch_customers(shopkeeper_id: str) -> list[dict]:
    """Every customer belonging to this shopkeeper — nothing else.
    Requires a real shopkeeper_id; returns [] rather than guessing."""
    if not shopkeeper_id:
        return []
    return (
        supabase
        .table("customers")
        .select("id, name, phone")
        .eq("shopkeeper_id", shopkeeper_id)
        .execute()
        .data
        or []
    )


def fetch_transactions(customer_ids: list[str]) -> list[dict]:
    """All transactions for these customer ids, paging past Supabase's
    1000-row limit so sums/counts are never silently incomplete."""
    if not customer_ids:
        return []

    rows: list[dict] = []
    start = 0
    while True:
        page = (
            supabase
            .table("transactions")
            .select("id, customer_id, amount, type, date, due_date, raw_text")
            .in_("customer_id", customer_ids)
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def find_customer(shopkeeper_id: str, name: str) -> dict | None:
    """Match a customer belonging to THIS shopkeeper by canonical identity
    (case/script-insensitive — 'Shreya'/'SHREYA'/'श्रेया' all match the
    same row; see customer_identity.py). Never another shopkeeper's
    customer, and this never creates one — callers get None and must
    report "not found", not invent a record."""
    if not shopkeeper_id or not name:
        return None
    target_key = canonical_key(name)
    for c in fetch_customers(shopkeeper_id):
        if canonical_key(c["name"]) == target_key:
            return c
    return None