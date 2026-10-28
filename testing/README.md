# TESH-Query Amazon-Scale Ecommerce Testing Database & Benchmark Suite

This directory contains the production-grade, Amazon-scale ecommerce testing fixture, deterministic synthetic data generator, integrity verification suite, and performance benchmarks for **TESH-Query**.

All fixture assets, schemas, manifests, and benchmarks reside strictly within `/testing` to provide a reproducible, self-contained testing environment.

---

## 1. Architecture & Schema Overview

The testing database (`testing/databases/ecommerce.sqlite`) is modeled after large-scale modern ecommerce platforms (such as Amazon), featuring **45 normalized relational tables** organized into **10 core business domains** with **38 explicit secondary indexes** for high-performance joins, aggregations, and window analytics.

### Domain Inventory (45 Tables)

```
testing/
├── databases/
│   └── ecommerce.sqlite                 # Primary fixture database (~93.4 MB, 1.12M rows)
├── fixtures/
│   ├── expected_results.json            # Deterministic invariants & financial rules
│   └── cross_database_cases.json        # Federated cross-database scenarios
├── sql/
│   └── schema.sql                       # Complete DDL: 45 tables & 38 indexes
├── benchmark_queries.json               # 32 benchmark NL questions & reference SQL
├── connections.example.yaml             # Example multi-database connection config
├── create_database.py                   # Deterministic chunked synthetic data generator
├── verify_database.py                   # 7-phase integrity and business invariant verifier
├── run_benchmarks.py                    # Scalability & query execution latency benchmark
├── manifest.json                        # SHA-256 checksum and table metadata
└── benchmark_report.json                # Latest execution metrics and timings
```

### Domain Classification

| Domain | Table Count | Domain Description & Tables |
| :--- | :---: | :--- |
| **A. Customers & Identity** | 9 | `customers`, `customer_profiles`, `customer_addresses`, `customer_preferences`, `customer_segments`, `customer_segment_memberships`, `customer_sessions`, `customer_devices`, `wishlists`, `wishlist_items` |
| **B. Product Catalog** | 10 | `categories`, `brands`, `products`, `product_variants`, `product_attributes`, `product_attribute_values`, `product_images`, `product_category_mappings`, `product_reviews`, `product_ratings`, `product_questions`, `product_answers` |
| **C. Sellers & Marketplace** | 6 | `sellers`, `seller_profiles`, `seller_addresses`, `seller_products`, `seller_performance_metrics`, `seller_payouts` |
| **D. Shopping Cart & Checkout**| 5 | `carts`, `cart_items`, `checkout_sessions`, `coupons`, `coupon_redemptions` |
| **E. Orders & Payments** | 7 | `orders`, `order_items`, `order_status_history`, `payments`, `payment_transactions`, `refunds`, `invoices` |
| **F. Inventory & Warehouses** | 8 | `warehouses`, `warehouse_locations`, `inventory`, `inventory_movements`, `inventory_reservations`, `purchase_orders`, `purchase_order_items`, `suppliers` |
| **G. Shipping & Fulfillment** | 6 | `shipping_carriers`, `shipping_methods`, `shipments`, `shipment_items`, `shipment_tracking_events`, `delivery_addresses` |
| **H. Returns & Customer Support** | 6 | `returns`, `return_items`, `support_agents`, `support_tickets`, `support_ticket_messages`, `customer_service_events` |
| **I. Promotions & Marketing** | 5 | `campaigns`, `campaign_products`, `ad_impressions`, `ad_clicks`, `attribution_events` |
| **J. Subscriptions & Analytics**| 6 | `subscriptions`, `subscription_events`, `daily_sales_metrics`, `daily_product_metrics`, `daily_seller_metrics`, `exchange_rates` |

---

## 2. Data Profiles & Scalability

The generator (`testing/create_database.py`) provides deterministic synthetic data generation using chunked batched inserts to keep memory footprint bounded.

| Entity / Table | Standard Profile (Default) | Large Profile (Amazon-Scale) |
| :--- | :---: | :---: |
| **Customers** | 10,000 | 100,000 |
| **Products** | 5,000 | 25,000 |
| **Product Variants** | 10,000 | 50,000 |
| **Sellers** | 500 | 2,000 |
| **Orders** | 50,000 | 500,000 |
| **Order Items** | 174,946 | ~1,750,000 |
| **Payments** | 50,000 | 500,000 |
| **Product Reviews** | 25,000 | 250,000 |
| **Inventory Records** | 20,000 | 100,000 |
| **Shipments** | 42,000 | 450,000 |
| **Shipment Tracking Events** | 168,000 | 1,500,000 |
| **Ad Impressions** | 100,000 | 1,000,000 |
| **Ad Clicks** | 20,000 | 200,000 |
| **Inventory Movements** | 100,000 | 1,000,000 |
| **Total Database Records** | **1,123,500 rows** | **~10,000,000 rows** |
| **Database File Size** | **93.41 MB** | **~850 MB – 1.1 GB** |
| **Generation Time** | **~4.2 seconds** | **~40–55 seconds** |

---

## 3. Database Generation & Management

### Prerequisites
Ensure dependencies are installed via `uv`:
```bash
uv sync
```

### Standard Profile Generation (Recommended for Local Dev)
```bash
python testing/create_database.py --profile standard --seed 42 --force
```

### Large Profile Generation (High-Concurrency & Scale Benchmarks)
```bash
python testing/create_database.py --profile large --seed 42 --force
```

### Command-Line Arguments
- `--profile`: Profile to generate (`standard` or `large`). Default: `standard`.
- `--seed`: Integer pseudo-random seed for deterministic reproducibility. Default: `42`.
- `--output`: Custom database file path. Default: `testing/databases/ecommerce.sqlite`.
- `--force`: Required to overwrite an existing database file without accidental deletion.

---

## 4. Integrity & Financial Invariant Verification

`testing/verify_database.py` validates SQLite storage integrity, foreign key constraints, index presence, row count thresholds, and financial reconciliation invariants.

### Running Integrity Verification
```bash
python testing/verify_database.py
```

### Verification Checks (All 7 Phases)
1. **PRAGMA integrity_check**: Validates B-tree structure and page consistency.
2. **PRAGMA foreign_key_check**: Ensures 0 foreign key constraint violations across all 45 tables.
3. **Table & Schema Inventory**: Confirms all 45 domain tables exist.
4. **Secondary Index Check**: Verifies 38 explicit secondary indexes exist for query optimization.
5. **Row Count Thresholds**: Validates that all domain tables meet the profile's minimum row counts.
6. **Financial Invariants & Business Logic**:
   - `order_financial_reconciliation`: `total_amount == subtotal - discount_amount + tax_amount + shipping_amount` (tolerance 0.05).
   - `payment_reconciliation`: Sum of successful payments equals total order amount.
   - `order_item_line_total_reconciliation`: `line_total == (quantity * unit_price) - discount_amount`.
   - `refund_ceiling_reconciliation`: `refund_amount <= payment_amount`.
   - `chronological_sequence_invariant`: `order_date <= shipped_date <= delivered_date`.
   - `customer_address_integrity`: Every address links to an existing customer.
   - `product_review_range`: `rating BETWEEN 1 AND 5`.
7. **Synthetic Data Purity**: Ensures all customer emails strictly use `@synthetic-mail.test` to prevent real PII leaks.

---

## 5. Performance Benchmarks

`testing/run_benchmarks.py` measures real execution performance across schema introspection, schema graph loading, and 30 single-database reference queries + 2 federated cross-database scenarios.

### Running Benchmarks
```bash
python testing/run_benchmarks.py
```

### Observed Execution Performance (Standard Profile, 1.12M rows)
- **Database Size on Disk**: `93.41 MB`
- **Total Benchmark Runtime**: `12.84 s`
- **Peak Process Memory (RSS)**: `199.55 MB`
- **Schema Introspection Latency**: `222.43 ms` (45 tables)
- **Schema Graph Retrieval Latency**: `0.04 ms`
- **Average Simple Query Latency**: `1.44 ms`
- **Average Medium Query Latency**: `28.73 ms`
- **Average Complex Query Latency**: `887.49 ms`

---

## 6. Financial Semantics & Revenue Definitions

To ensure deterministic benchmark queries, revenue semantics are explicitly partitioned:
- **Gross Merchandise Value (GMV)**: `SUM(total_amount)` on orders where `status != 'cancelled'`. Includes discounts, taxes, and shipping charges.
- **Net Sales**: `SUM(subtotal - discount_amount)` on completed or shipped orders. Excludes taxes and shipping charges.
- **Collected Payments**: `SUM(amount)` from `payments` where `status = 'successful'`.
- **Recognized Revenue**: Post-refund net revenue (`collected payments - refunds`).

---

## 7. Multi-Database & Cross-Database Testing

The test suite validates multi-database isolation and federated query orchestration. While `testing/databases/ecommerce.sqlite` is the only persistent fixture database, integration tests automatically spin up ephemeral in-memory or temporary SQLite databases (e.g. `analytics.sqlite`, `finance.sqlite`) to verify:
- Independent SQLAlchemy engine pools per named connection.
- Schema collision safety (e.g. `shared_metadata` in both databases without cross-talk).
- Federated AST plan validation and read-only subquery execution.
- In-memory bounded joins handling `NULL` keys, duplicate keys, and column disambiguation.
- Partial failure resilience and execution telemetry.

Run multi-database unit and integration tests:
```bash
uv run pytest tests/unit/test_multi_database_connections.py tests/integration/test_cross_database_queries.py -v
```

---

## 8. Security Controls
- **Read-Only Connections**: Test queries use read-only transactions; destructive statements (`DROP`, `TRUNCATE`, `ALTER`) are blocked by AST analysis before reaching the database.
- **Credential Masking**: Passwords in connection URLs (e.g., `postgresql://user:pass@host/db`) are automatically masked as `***` in logs, exceptions, prompts, and CLI status displays.
- **Environment Variable Resolution**: Supports `${DB_PASSWORD}` and `${DB_HOST:-localhost}` substitution without hardcoding secrets in configuration files.
