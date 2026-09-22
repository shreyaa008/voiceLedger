"""
Find and merge duplicate customers (same person, different spelling —
"Shreya" / "SHREYA" / "श्रेया" — created before the canonical-matching fix
in backend/app/routers/transactions.py).

SAFE BY DESIGN:
  - Dry-run by default. Nothing is changed unless you pass --apply.
  - No transaction is ever deleted. Merging a duplicate customer means
    reassigning its transactions.customer_id to the surviving customer,
    THEN deleting the now-empty duplicate customer row. If reassignment
    fails partway, nothing has been deleted yet.
  - The "surviving" customer is the one with the most transactions
    (ties broken by whichever name is already in clean display form),
    so the customer with the richest history keeps its name.

Usage:
    cd backend
    python scripts/merge_duplicate_customers.py                 # dry run, all shopkeepers
    python scripts/merge_duplicate_customers.py --apply          # actually merge
    python scripts/merge_duplicate_customers.py --shopkeeper-id <uuid> --apply
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.customer_identity import canonical_key, display_name
from app.services.supabase_client import supabase


def fetch_customers(shopkeeper_id: str | None):
    query = supabase.table("customers").select("id, name, shopkeeper_id, created_at")
    if shopkeeper_id:
        query = query.eq("shopkeeper_id", shopkeeper_id)
    return query.execute().data or []


def fetch_transaction_counts(customer_ids: list[str]) -> dict[str, int]:
    counts = {cid: 0 for cid in customer_ids}
    # Supabase/PostgREST .in_() has a practical size limit — chunk it.
    for i in range(0, len(customer_ids), 200):
        chunk = customer_ids[i : i + 200]
        rows = (
            supabase.table("transactions")
            .select("customer_id")
            .in_("customer_id", chunk)
            .execute()
            .data
            or []
        )
        for row in rows:
            counts[row["customer_id"]] = counts.get(row["customer_id"], 0) + 1
    return counts


def group_duplicates(customers: list[dict]) -> list[list[dict]]:
    by_shopkeeper_and_key = defaultdict(list)
    for c in customers:
        key = canonical_key(c["name"])
        if not key:
            continue
        by_shopkeeper_and_key[(c["shopkeeper_id"], key)].append(c)
    return [group for group in by_shopkeeper_and_key.values() if len(group) > 1]


def choose_primary(group: list[dict], tx_counts: dict[str, int]) -> dict:
    def score(c):
        clean_name = display_name(c["name"]) == c["name"]
        return (tx_counts.get(c["id"], 0), 1 if clean_name else 0, c.get("created_at") or "")

    return max(group, key=score)


def merge_group(group: list[dict], tx_counts: dict[str, int], apply: bool) -> None:
    primary = choose_primary(group, tx_counts)
    duplicates = [c for c in group if c["id"] != primary["id"]]

    names = ", ".join(f'"{c["name"]}"' for c in group)
    print(f'\n  Group: {names}')
    print(
        f'    -> keeping "{primary["name"]}" (id={primary["id"]}, '
        f'{tx_counts.get(primary["id"], 0)} transactions)'
    )

    for dup in duplicates:
        dup_count = tx_counts.get(dup["id"], 0)
        print(f'    -> merging "{dup["name"]}" (id={dup["id"]}, {dup_count} transactions) into it')

        if not apply:
            continue

        if dup_count > 0:
            reassign = (
                supabase.table("transactions")
                .update({"customer_id": primary["id"]})
                .eq("customer_id", dup["id"])
                .execute()
            )
            if reassign.data is None:
                print(f'       ! FAILED to reassign transactions for "{dup["name"]}" — skipping delete, data untouched')
                continue

        supabase.table("customers").delete().eq("id", dup["id"]).execute()
        print(f'       merged and removed duplicate row for "{dup["name"]}"')

    # Tidy the surviving row's display name (e.g. "SHREYA" -> "Shreya") and
    # backfill canonical_key (no-op if that column doesn't exist yet — see
    # migrations/002_customer_canonical_key.sql).
    if apply:
        cleaned_name = display_name(primary["name"])
        update_payload = {"name": cleaned_name}
        try:
            supabase.table("customers").update(
                {**update_payload, "canonical_key": canonical_key(primary["name"])}
            ).eq("id", primary["id"]).execute()
        except Exception:
            supabase.table("customers").update(update_payload).eq("id", primary["id"]).execute()
        if cleaned_name != primary["name"]:
            print(f'       tidied display name to "{cleaned_name}"')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually merge (default: dry run only)")
    parser.add_argument("--shopkeeper-id", default=None, help="Limit to one shopkeeper")
    args = parser.parse_args()

    customers = fetch_customers(args.shopkeeper_id)
    if not customers:
        print("No customers found.")
        return

    groups = group_duplicates(customers)
    if not groups:
        print(f"Checked {len(customers)} customers — no duplicates found.")
        return

    tx_counts = fetch_transaction_counts([c["id"] for c in customers])

    print(f"Checked {len(customers)} customers, found {len(groups)} duplicate group(s).")
    if not args.apply:
        print("DRY RUN — nothing will be changed. Re-run with --apply to actually merge.\n")
    else:
        print("APPLYING — merging duplicates now.\n")

    for group in groups:
        merge_group(group, tx_counts, args.apply)

    if not args.apply:
        print("\nDry run complete. Review the groups above, then re-run with --apply.")
    else:
        print("\nDone. Every duplicate's transactions were reassigned before its row was removed —")
        print("no transaction data was deleted.")


if __name__ == "__main__":
    main()