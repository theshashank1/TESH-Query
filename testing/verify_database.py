#!/usr/bin/env python3
"""
TESH-Query Database Integrity and Invariant Verification Utility.

Verifies testing/databases/ecommerce.sqlite for structural integrity, foreign key
consistency, index coverage, synthetic data safety, and financial invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
TESTING_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = TESTING_DIR / "databases" / "ecommerce.sqlite"
EXPECTED_RESULTS_PATH = TESTING_DIR / "fixtures" / "expected_results.json"
MANIFEST_PATH = TESTING_DIR / "manifest.json"

REQUIRED_TABLES = [
    "customers", "customer_profiles", "customer_addresses", "customer_segments", "customer_segment_memberships",
    "categories", "brands", "products", "product_variants", "product_attributes",
    "product_attribute_values", "product_reviews",
    "sellers", "seller_profiles", "seller_products", "seller_payouts",
    "carts", "cart_items", "coupons", "coupon_redemptions",
    "orders", "order_items", "order_status_history", "payments", "refunds", "invoices",
    "suppliers", "warehouses", "inventory", "inventory_movements",
    "shipping_carriers", "shipments", "shipment_items", "shipment_tracking_events",
    "returns", "return_items", "support_agents", "support_tickets",
    "campaigns", "ad_impressions", "ad_clicks",
    "subscriptions", "subscription_events", "daily_sales_metrics", "exchange_rates"
]


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 checksum of file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_database(
    db_path: Path,
    profile_name: str = "standard",
    update_manifest: bool = True
) -> bool:
    """Run verification checks on the database file."""
    print("=" * 60)
    print("TESH-Query Database Integrity Verifier")
    print(f"Target Database: {db_path}")
    print(f"Profile:         {profile_name.upper()}")
    print("=" * 60)

    if not db_path.exists():
        print(f"FATAL: Database file does not exist at {db_path}!")
        return False

    file_size_bytes = db_path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f"✓ File exists. Size: {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    failures: List[str] = []

    # 1. SQLite PRAGMA integrity_check
    print("\n[Check 1/7] Running PRAGMA integrity_check...")
    try:
        integrity = cursor.execute("PRAGMA integrity_check;").fetchall()
        if len(integrity) == 1 and integrity[0][0].lower() == "ok":
            print("  ✓ PRAGMA integrity_check: PASSED (ok)")
        else:
            msg = f"PRAGMA integrity_check reported issues: {integrity}"
            failures.append(msg)
            print(f"  ✗ {msg}")
    except Exception as e:
        failures.append(f"integrity_check failed: {e}")
        print(f"  ✗ PRAGMA integrity_check error: {e}")

    # 2. SQLite PRAGMA foreign_key_check
    print("\n[Check 2/7] Running PRAGMA foreign_key_check...")
    try:
        fk_violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
        if not fk_violations:
            print("  ✓ PRAGMA foreign_key_check: PASSED (0 violations)")
        else:
            msg = f"Foreign key violations found: {len(fk_violations)} violations: {fk_violations[:5]}"
            failures.append(msg)
            print(f"  ✗ {msg}")
    except Exception as e:
        failures.append(f"foreign_key_check failed: {e}")
        print(f"  ✗ PRAGMA foreign_key_check error: {e}")

    # 3. Table and Column Existence
    print(f"\n[Check 3/7] Verifying all {len(REQUIRED_TABLES)} required relational tables exist...")
    existing_tables = {
        row[0]
        for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    }
    missing_tables = [tbl for tbl in REQUIRED_TABLES if tbl not in existing_tables]
    if not missing_tables:
        print(f"  ✓ All {len(REQUIRED_TABLES)} required domain tables are present.")
    else:
        msg = f"Missing required tables: {missing_tables}"
        failures.append(msg)
        print(f"  ✗ {msg}")

    # 4. Index Inventory
    print("\n[Check 4/7] Verifying secondary indexes for analytics performance...")
    idx_sql = "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex%';"
    indexes = cursor.execute(idx_sql).fetchall()
    print(f"  ✓ Found {len(indexes)} explicit secondary indexes across key tables.")
    if len(indexes) < 25:
        msg = f"Expected at least 25 secondary indexes, found {len(indexes)}."
        failures.append(msg)
        print(f"  ✗ {msg}")

    # 5. Row Count Thresholds
    print("\n[Check 5/7] Verifying row counts and profile thresholds...")
    table_counts: Dict[str, int] = {}
    total_rows = 0
    for tbl in sorted(existing_tables):
        if tbl == "sqlite_sequence":
            continue
        cnt = cursor.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
        table_counts[tbl] = cnt
        total_rows += cnt

    expected_cfg: Dict[str, Any] = {}
    if EXPECTED_RESULTS_PATH.exists():
        expected_cfg = json.loads(EXPECTED_RESULTS_PATH.read_text(encoding="utf-8"))

    thresholds = expected_cfg.get("profile_thresholds", {}).get(profile_name, {})
    threshold_mapping = {
        "min_customers": "customers",
        "min_products": "products",
        "min_variants": "product_variants",
        "min_sellers": "sellers",
        "min_orders": "orders",
        "min_order_items": "order_items",
        "min_payments": "payments",
        "min_reviews": "product_reviews",
        "min_inventory": "inventory",
        "min_shipments": "shipments",
        "min_tracking_events": "shipment_tracking_events",
        "min_impressions": "ad_impressions",
        "min_clicks": "ad_clicks",
        "min_movements": "inventory_movements",
    }

    for key, tbl in threshold_mapping.items():
        min_required = thresholds.get(key, 0)
        actual = table_counts.get(tbl, 0)
        if actual < min_required:
            msg = f"Table '{tbl}' has {actual:,} rows, expected at least {min_required:,} for {profile_name} profile."
            failures.append(msg)
            print(f"  ✗ {msg}")
        else:
            print(f"  ✓ {tbl:<26} {actual:>10,} rows (>= threshold {min_required:,})")

    # 6. Business Invariants from expected_results.json
    print("\n[Check 6/7] Validating business invariants and financial reconciliation...")
    invariants = expected_cfg.get("business_invariants", [])
    for inv in invariants:
        name = inv["name"]
        query = inv["query"]
        expected_violations = inv.get("expected_violation_count", 0)
        try:
            violation_count = cursor.execute(query).fetchone()[0]
            if violation_count == expected_violations:
                print(f"  ✓ Invariant '{name}': PASSED ({violation_count} violations)")
            else:
                msg = f"Invariant '{name}' failed: expected {expected_violations} violations, found {violation_count}."
                failures.append(msg)
                print(f"  ✗ {msg}")
        except Exception as e:
            msg = f"Invariant query '{name}' crashed: {e}"
            failures.append(msg)
            print(f"  ✗ {msg}")

    # 7. Synthetic Data Audit (ensure no real PII / domains)
    print("\n[Check 7/7] Synthetic data purity check...")
    non_synthetic_emails = cursor.execute(
        "SELECT COUNT(*) FROM customers WHERE email NOT LIKE '%@synthetic-mail.test';"
    ).fetchone()[0]
    if non_synthetic_emails == 0:
        print("  ✓ All customer emails strictly use safe synthetic domain (@synthetic-mail.test).")
    else:
        msg = f"Found {non_synthetic_emails} non-synthetic emails in customers table!"
        failures.append(msg)
        print(f"  ✗ {msg}")

    conn.close()

    # Largest tables
    sorted_tables = sorted(table_counts.items(), key=lambda x: x[1], reverse=True)
    top_5 = sorted_tables[:5]

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Database File:        {db_path.name}")
    print(f"Database Size:        {file_size_mb:.2f} MB")
    print(f"Total Domain Tables:  {len(table_counts)}")
    print(f"Total Record Count:   {total_rows:,} rows")
    print(f"Index Count:          {len(indexes)}")
    print(f"Foreign Key Status:   {'0 Violations' if not fk_violations else 'VIOLATIONS DETECTED'}")
    print(f"Integrity Status:     {'PASSED' if not failures else 'FAILED'}")
    print("\nTop 5 Largest Tables:")
    for t_name, c_cnt in top_5:
        print(f"  • {t_name:<26} {c_cnt:>10,} rows")

    sha256_hash = compute_sha256(db_path)
    print(f"\nSHA-256 Checksum:     {sha256_hash}")

    if update_manifest and not failures:
        manifest_data = {
            "database_name": db_path.name,
            "profile": profile_name,
            "total_tables": len(table_counts),
            "total_rows": total_rows,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_mb, 2),
            "sha256": sha256_hash,
            "table_inventory": table_counts,
            "largest_tables": top_5,
            "verified_invariants": len(invariants),
            "indexes_count": len(indexes),
        }
        MANIFEST_PATH.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        print(f"✓ Manifest updated at {MANIFEST_PATH}")

    if failures:
        print(f"\nFAILED with {len(failures)} error(s):")
        for f in failures:
            print(f"  - {f}")
        return False

    print("\nALL INTEGRITY AND INVARIANT CHECKS PASSED SUCCESSFULLY!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Verify SQLite ecommerce database integrity and invariants."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database to verify (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--profile",
        choices=["standard", "large"],
        default="standard",
        help="Profile thresholds to check against (default: standard).",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip updating manifest.json.",
    )

    args = parser.parse_args()
    success = verify_database(
        db_path=args.database,
        profile_name=args.profile,
        update_manifest=not args.no_manifest,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
