# Testing Fixtures, Synthetic E-Commerce DB & Benchmarks

To thoroughly test schema introspection, TF-IDF vector pruning, multi-table joins, and query generation without relying on proprietary customer data, TESH-Query includes a realistic, Amazon-scale ecommerce testing database fixture and benchmark harness in `/testing`.

---

## 🏬 The Amazon-Scale E-Commerce Database

The database fixture (`testing/databases/ecommerce.sqlite`) models a complete modern e-commerce enterprise:
- **45 Normalized Relational Tables** across 9 functional domains.
- **38 Explicit Secondary Indexes** optimizing high-cardinality join paths.
- **1,123,500+ Synthetic Rows** generated with deterministic random seeds.

### Schema Domains Matrix

| Domain | Key Tables | Relational Responsibility |
| :--- | :--- | :--- |
| **Identity & Users** | `users`, `addresses`, `user_credentials`, `user_roles` | Customer profiles, authentication states, shipping addresses. |
| **Catalog** | `products`, `categories`, `brands`, `product_variants` | Product taxonomy, SKUs, MSRP, attributes, and tags. |
| **Inventory** | `warehouses`, `inventory_levels`, `inventory_transfers` | Multi-facility stock tracking, replenishment, and reorder levels. |
| **Orders** | `orders`, `order_items`, `order_status_history` | Transaction headers, line items, price snapshots, order tracking. |
| **Payments** | `payment_transactions`, `payment_methods`, `refunds` | Payment processing, gateway reconciliation, refund audits. |
| **Logistics** | `shipments`, `shipment_items`, `carriers` | Fulfillment tracking, waybills, carrier performance. |
| **Marketing** | `coupons`, `promotions`, `campaigns`, `abandoned_carts`| Promotional discounts, campaign attribution, cart recovery. |
| **Customer Feedback**| `product_reviews`, `seller_ratings`, `review_votes` | Verified purchase reviews, star ratings, moderation queues. |
| **Analytics & Clickstream**| `user_sessions`, `page_views`, `search_queries` | High-frequency telemetry, clickstream logs, funnel drops. |

---

## 🏭 Synthetic Data Generator (`testing/create_database.py`)

Generate or rebuild the synthetic database fixture with deterministic seed control:

```bash
# Standard profile (~1.12M rows, 93 MB in ~4s)
python testing/create_database.py --profile standard --seed 42 --force

# Large profile (~10M rows, ~900 MB in ~45s)
python testing/create_database.py --profile large --seed 42 --force
```

### Key Engineering Features
- **Deterministic Reproducibility:** Uses Python's `Faker` and random number generators with a fixed seed (`--seed 42`).
- **Synthetic Domain Purity:** 100% of generated email addresses and domains utilize RFC 2606 reserved domains (`@example.com`, `@synthetic.internal`) to prevent accidental PII leakage.
- **Fast In-Memory Generation:** Leverages SQLite transaction batching and bulk inserts to generate over 250,000 records per second.

---

## 🔍 Invariant Verification Suite (`testing/verify_database.py`)

The verification script validates relational integrity and verifies 7 critical business and financial invariants:

```bash
python testing/verify_database.py
```

### The 7 Financial & Relational Invariants

1. **Foreign Key Integrity:** Zero orphan records across all 45 tables (`PRAGMA foreign_key_check`).
2. **Line Item Reconciliation:** `order_items.line_total == (quantity * unit_price) - discount`.
3. **Order Header Reconciliation:** `orders.total_amount == SUM(order_items.line_total) + tax + shipping - coupon_discount`.
4. **Payment Reconciliation:** Successful payment transactions match the order's `total_amount`.
5. **Refund Ceilings:** Total refunded amounts never exceed the captured payment amount.
6. **Chronological Sequence:** `order_date <= payment_date <= shipped_date <= delivery_date`.
7. **Inventory Floor Integrity:** Available inventory levels satisfy non-negative stock invariants (`stock >= 0`).

---

## ⏱️ Scalability & Latency Benchmarks (`testing/run_benchmarks.py`)

The benchmark harness executes 32 realistic natural-language questions across varying join complexities:

```bash
python testing/run_benchmarks.py
```

### Benchmark Metrics Tracked
- **Schema Reflection Latency:** Time to introspect 45 tables and 38 indexes.
- **TF-IDF Retrieval Efficiency:** Verifies that the TF-IDF pruner correctly selects the 3–5 relevant tables without human intervention.
- **Query Synthesis Time:** Time to plan and synthesize dialect-accurate SQL.
- **Execution Throughput:** Sub-millisecond database execution via SQLite pragmas.

---

## 🧭 Next Steps

- **[Harness Architecture](03_architecture.md)** — Understand how TF-IDF prunes the 45-table schema.
- **[CLI Reference](07_cli_reference.md)** — Run queries against the e-commerce fixture using `teshq query -c ecommerce`.
- **[Production Deployment](13_production_deployment.md)** — Deploy TESH-Query in enterprise production environments.
