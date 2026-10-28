#!/usr/bin/env python3
"""
TESH-Query Amazon-Scale Ecommerce Testing Database Generator.

Generates testing/databases/ecommerce.sqlite containing 45 normalized tables
across 10 domains with realistic relational integrity, reconciled financial invariants,
temporal analytics coverage, and high-performance indexing.
"""

from __future__ import annotations

import argparse
import datetime
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
TESTING_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = TESTING_DIR / "sql" / "schema.sql"
DEFAULT_DB_PATH = TESTING_DIR / "databases" / "ecommerce.sqlite"

# Profile targets
PROFILES = {
    "standard": {
        "customers": 10000,
        "customer_addresses": 12000,
        "categories": 50,
        "brands": 200,
        "products": 5000,
        "variants": 10000,
        "attributes": 20,
        "attribute_values": 20000,
        "reviews": 25000,
        "sellers": 500,
        "seller_products": 15000,
        "seller_payouts": 6000,
        "carts": 10000,
        "cart_items": 25000,
        "coupons": 100,
        "coupon_redemptions": 15000,
        "orders": 50000,
        "order_items": 150000,
        "order_status_history": 80000,
        "payments": 55000,
        "refunds": 6000,
        "invoices": 50000,
        "suppliers": 50,
        "warehouses": 20,
        "inventory": 20000,
        "inventory_movements": 100000,
        "shipping_carriers": 10,
        "shipments": 42000,
        "shipment_items": 125000,
        "shipment_events": 150000,
        "returns": 6000,
        "return_items": 7500,
        "support_agents": 50,
        "support_tickets": 15000,
        "campaigns": 50,
        "impressions": 100000,
        "clicks": 20000,
        "subscriptions": 5000,
        "subscription_events": 20000,
        "daily_sales_days": 730,
        "exchange_rates_days": 180,
    },
    "large": {
        "customers": 100000,
        "customer_addresses": 120000,
        "categories": 150,
        "brands": 1000,
        "products": 25000,
        "variants": 50000,
        "attributes": 30,
        "attribute_values": 100000,
        "reviews": 250000,
        "sellers": 2000,
        "seller_products": 75000,
        "seller_payouts": 24000,
        "carts": 50000,
        "cart_items": 120000,
        "coupons": 200,
        "coupon_redemptions": 60000,
        "orders": 500000,
        "order_items": 1800000,
        "order_status_history": 800000,
        "payments": 550000,
        "refunds": 50000,
        "invoices": 500000,
        "suppliers": 200,
        "warehouses": 50,
        "inventory": 100000,
        "inventory_movements": 800000,
        "shipping_carriers": 20,
        "shipments": 450000,
        "shipment_items": 1300000,
        "shipment_events": 1500000,
        "returns": 50000,
        "return_items": 65000,
        "support_agents": 200,
        "support_tickets": 100000,
        "campaigns": 200,
        "impressions": 1000000,
        "clicks": 200000,
        "subscriptions": 30000,
        "subscription_events": 120000,
        "daily_sales_days": 1095,
        "exchange_rates_days": 365,
    },
}

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Jamie", "Peyton", "Logan",
    "Sam", "Dakota", "Reese", "Skyler", "Cameron", "Jesse", "Rowan", "Finley", "Emerson", "Adrian",
    "Quinn", "Hayden", "Kai", "Dallas", "Elliott", "Drew", "Parker", "Sawyer", "Kendall", "River",
    "Harper", "Charlie", "Milan", "Sage", "Amari", "Eden", "Sloan", "Lennon", "Remy", "Shiloh"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"
]

CITIES_STATES = [
    ("Seattle", "WA", "98101"), ("New York", "NY", "10001"), ("San Francisco", "CA", "94105"),
    ("Austin", "TX", "78701"), ("Chicago", "IL", "60601"), ("Boston", "MA", "02108"),
    ("Denver", "CO", "80202"), ("Atlanta", "GA", "30303"), ("Miami", "FL", "33101"),
    ("Los Angeles", "CA", "90012"), ("Portland", "OR", "97201"), ("Phoenix", "AZ", "85001"),
    ("Dallas", "TX", "75201"), ("Minneapolis", "MN", "55401"), ("San Diego", "CA", "92101")
]

BRAND_PREFIXES = ["Nova", "Aero", "Zenith", "Pulse", "Lumina", "Apex", "Vortex", "Titan", "Eco", "Omni"]
BRAND_SUFFIXES = ["Tech", "Style", "Living", "Audio", "Craft", "Dynamics", "Gear", "Works", "Lab", "Pro"]

CATEGORIES_ROOT = [
    ("Electronics", ["Computers", "Mobile Phones", "Audio & Headphones", "Cameras", "Accessories"]),
    ("Home & Kitchen", ["Cookware", "Small Appliances", "Bedding", "Furniture", "Home Decor"]),
    ("Clothing & Apparel", ["Men's Wear", "Women's Wear", "Athletic", "Footwear", "Watches & Jewelry"]),
    ("Sports & Outdoors", ["Fitness Equipment", "Camping & Hiking", "Cycling", "Water Sports", "Outdoor Games"]),
    ("Books & Media", ["Fiction", "Technology & Science", "Business & Finance", "Biographies", "Audiobooks"]),
]

PRODUCT_NOUNS = [
    "Wireless Noise-Canceling Headphones", "Ergonomic Mechanical Keyboard", "Ultra-HD 4K Smart Monitor",
    "Stainless Steel Coffee Maker", "High-Speed Blending System", "Smart Fitness Tracker Watch",
    "Breathable Running Shoes", "Organic Cotton Bedding Sheet Set", "Waterproof Lightweight Backpack",
    "Compact Portable Power Bank", "Ceramic Nonstick Frying Pan", "Adjustable Standing Desk Riser",
    "Bluetooth High-Fidelity Speaker", "Precision Electric Shaver", "Multi-Port Fast Charging Hub",
    "Thermal Insulated Water Bottle", "Cast Iron Dutch Oven", "Memory Foam Orthopedic Pillow",
    "Solar Powered Outdoor LED Light", "Noise-Isolating In-Ear Earbuds"
]


def parse_sql_script(schema_path: Path) -> Tuple[str, str]:
    """Split schema.sql into table creation DDL and index creation DDL."""
    content = schema_path.read_text(encoding="utf-8")
    table_lines = []
    index_lines = []
    in_index_section = False

    for line in content.splitlines():
        if "INDEXES FOR HIGH-PERFORMANCE" in line:
            in_index_section = True
        if in_index_section:
            index_lines.append(line)
        else:
            table_lines.append(line)

    return "\n".join(table_lines), "\n".join(index_lines)


def random_date(rng: random.Random, start_year: int = 2023, end_year: int = 2024) -> datetime.datetime:
    """Generate a random timestamp between start_year and end_year."""
    start = datetime.datetime(start_year, 1, 1, 0, 0, 0)
    end = datetime.datetime(end_year, 12, 31, 23, 59, 59)
    delta_seconds = int((end - start).total_seconds())
    offset = rng.randint(0, delta_seconds)
    return start + datetime.timedelta(seconds=offset)


def generate_database(
    output_path: Path,
    profile_name: str = "standard",
    seed: int = 42,
    force: bool = False,
) -> None:
    """Generate the SQLite ecommerce database with high performance chunked inserts."""
    if output_path.exists():
        if not force:
            print(f"Error: Database file already exists at {output_path}.")
            print("Use --force to overwrite the existing database.")
            sys.exit(1)
        else:
            output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if profile_name not in PROFILES:
        print(f"Error: Unknown profile '{profile_name}'. Available: {list(PROFILES.keys())}")
        sys.exit(1)

    counts = PROFILES[profile_name]
    rng = random.Random(seed)

    print("============================================================")
    print("TESH-Query Ecommerce Database Generator")
    print(f"Profile:       {profile_name.upper()}")
    print(f"Seed:          {seed}")
    print(f"Target Output: {output_path}")
    print("============================================================")

    start_total_time = time.time()

    table_ddl, index_ddl = parse_sql_script(SCHEMA_FILE)

    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    # Performance pragmas for bulk load
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")
    cursor.execute("PRAGMA cache_size = -64000;")
    cursor.execute("PRAGMA temp_store = MEMORY;")
    cursor.execute("PRAGMA foreign_keys = OFF;")  # Turned on before integrity check

    # Step 1: Create all 45 tables
    print("\n[1/12] Creating 45 normalized tables...")
    cursor.executescript(table_ddl)
    conn.commit()

    # Step 2: Seed Customer & Identity Domain
    n_customers = counts["customers"]
    print(f"\n[2/12] Seeding {n_customers:,} customers and profiles...")
    customer_rows = []
    profile_rows = []
    address_rows = []
    addr_id = 1

    income_brackets = ["<$30k", "$30k-$60k", "$60k-$100k", "$100k-$150k", ">$150k"]
    genders = ["Female", "Male", "Non-Binary", "Prefer Not to Say"]
    loyalty_tiers = ["standard", "silver", "gold", "platinum"]

    for cid in range(1, n_customers + 1):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        email = f"user_{cid}_{fn.lower()}.{ln.lower()}@synthetic-mail.test"
        phone = f"+1-{rng.randint(200, 999)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
        created_dt = random_date(rng, 2023, 2024)
        updated_dt = created_dt + datetime.timedelta(days=rng.randint(0, 30))
        status = "active" if rng.random() < 0.95 else "suspended"
        customer_rows.append((cid, fn, ln, email, phone, status, created_dt.isoformat(), updated_dt.isoformat()))

        # Profile
        birth_year = rng.randint(1955, 2004)
        gender = rng.choice(genders)
        bracket = rng.choice(income_brackets)
        prime = 1 if rng.random() < 0.45 else 0
        tier = rng.choice(loyalty_tiers)
        profile_rows.append((cid, cid, birth_year, gender, "en", bracket, prime, tier))

        # Primary Address
        city, st, zip_c = rng.choice(CITIES_STATES)
        street = f"{rng.randint(100, 9999)} {rng.choice(LAST_NAMES)} Way"
        address_rows.append((addr_id, cid, "shipping", street, city, st, zip_c, "USA", 1))
        addr_id += 1

        # Extra billing address for some
        if rng.random() < 0.20:
            b_city, b_st, b_zip = rng.choice(CITIES_STATES)
            b_street = f"{rng.randint(10, 999)} Commerce Blvd Ste {rng.randint(100, 900)}"
            address_rows.append((addr_id, cid, "billing", b_street, b_city, b_st, b_zip, "USA", 0))
            addr_id += 1

    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?);", customer_rows)
    cursor.executemany("INSERT INTO customer_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?);", profile_rows)
    cursor.executemany("INSERT INTO customer_addresses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", address_rows)
    conn.commit()

    # Customer Segments
    segments = [
        (1, "High Value Prime", "Prime subscribers with annual spend > $2,000", 2000.00, 15),
        (2, "Frequent Shopper", "Customers with >= 10 orders per year", 500.00, 10),
        (3, "Bargain Seeker", "High coupon usage with average order value < $50", 100.00, 3),
        (4, "Tech Enthusiast", "Frequent electronics and computing purchases", 800.00, 5),
        (5, "New Account", "Registered within last 90 days", 0.00, 0),
    ]
    cursor.executemany("INSERT INTO customer_segments VALUES (?, ?, ?, ?, ?);", segments)

    membership_rows = []
    mem_id = 1
    for cid in range(1, min(n_customers + 1, 15000)):
        seg_id = rng.randint(1, 5)
        membership_rows.append((mem_id, cid, seg_id, datetime.datetime(2023, 6, 1).isoformat()))
        mem_id += 1
    cursor.executemany("INSERT INTO customer_segment_memberships VALUES (?, ?, ?, ?);", membership_rows)
    conn.commit()

    # Step 3: Product Catalog (Categories, Brands, Products, Variants, Attributes, Reviews)
    print("\n[3/12] Seeding product catalog hierarchy and variants...")
    category_rows = []
    cat_id = 1
    leaf_cat_ids = []
    for root_cat, subcats in CATEGORIES_ROOT:
        root_slug = root_cat.lower().replace(" & ", "-").replace(" ", "-")
        category_rows.append((cat_id, None, root_cat, root_slug, 1))
        p_id = cat_id
        cat_id += 1
        for sub in subcats:
            sub_slug = f"{root_slug}-{sub.lower().replace(' & ', '-').replace(' ', '-')}"
            category_rows.append((cat_id, p_id, sub, sub_slug, 2))
            leaf_cat_ids.append(cat_id)
            cat_id += 1
    cursor.executemany("INSERT INTO categories VALUES (?, ?, ?, ?, ?);", category_rows)

    # Brands
    n_brands = counts["brands"]
    brand_rows = []
    countries = ["USA", "Japan", "Germany", "South Korea", "Sweden", "Canada"]
    for b_id in range(1, n_brands + 1):
        b_name = f"{rng.choice(BRAND_PREFIXES)}{rng.choice(BRAND_SUFFIXES)} {b_id}"
        brand_rows.append((b_id, b_name, rng.choice(countries), 1))
    cursor.executemany("INSERT INTO brands VALUES (?, ?, ?, ?);", brand_rows)

    # Products & Variants
    n_products = counts["products"]
    product_rows = []
    variant_rows = []
    var_id = 1

    for pid in range(1, n_products + 1):
        sku = f"SKU-{pid:06d}"
        title = f"{rng.choice(BRAND_PREFIXES)} {rng.choice(PRODUCT_NOUNS)} Model {pid}"
        c_id = rng.choice(leaf_cat_ids)
        b_id = rng.randint(1, n_brands)
        base_price = round(rng.uniform(12.50, 499.99), 2)
        created_at = random_date(rng, 2023, 2023).isoformat()
        product_rows.append((pid, sku, title, c_id, b_id, base_price, 1, created_at))

        # 1 to 3 variants per product
        num_vars = rng.randint(1, 3)
        for vi in range(num_vars):
            v_sku = f"{sku}-V{vi+1}"
            v_name = f"Variant {vi+1} / Standard" if vi == 0 else f"Variant {vi+1} / Premium"
            p_mod = round(vi * rng.uniform(5.00, 25.00), 2)
            wt = round(rng.uniform(0.2, 5.0), 2)
            variant_rows.append((var_id, pid, v_sku, v_name, p_mod, wt, 1))
            var_id += 1

    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?);", product_rows)
    cursor.executemany("INSERT INTO product_variants VALUES (?, ?, ?, ?, ?, ?, ?);", variant_rows)
    conn.commit()

    # Product Attributes & Values
    attributes = [
        (1, "Color", "string"), (2, "Size", "string"), (3, "Connectivity", "string"),
        (4, "Warranty Period", "string"), (5, "Material", "string")
    ]
    cursor.executemany("INSERT INTO product_attributes VALUES (?, ?, ?);", attributes)

    attr_vals = []
    val_id = 1
    colors = ["Midnight Black", "Arctic White", "Space Gray", "Navy Blue", "Crimson Red"]
    for v in variant_rows[:min(len(variant_rows), counts["attribute_values"])]:
        attr_vals.append((val_id, v[0], 1, rng.choice(colors)))
        val_id += 1
    cursor.executemany("INSERT INTO product_attribute_values VALUES (?, ?, ?, ?);", attr_vals)
    conn.commit()

    # Product Reviews
    n_reviews = counts["reviews"]
    print(f"\n[4/12] Seeding {n_reviews:,} product reviews...")
    review_rows = []
    review_titles = [
        "Exceeded all expectations!", "Great quality for the price", "Decent product but room for improvement",
        "Fast shipping, highly recommend", "Battery life could be better", "Superb craftsmanship",
        "Must buy for daily use", "Average performance", "Outstanding customer satisfaction"
    ]
    for r_id in range(1, n_reviews + 1):
        pid = rng.randint(1, n_products)
        cid = rng.randint(1, n_customers)
        # Realistic rating distribution skewed positive (Amazon average ~4.2)
        rating = rng.choices([5, 4, 3, 2, 1], weights=[55, 25, 10, 5, 5])[0]
        title = rng.choice(review_titles)
        helpful = rng.randint(0, 45) if rng.random() < 0.3 else 0
        r_date = random_date(rng, 2023, 2024).isoformat()
        review_rows.append((r_id, pid, cid, rating, title, f"Detailed feedback for product {pid}.", helpful, 1, r_date))
    cursor.executemany("INSERT INTO product_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", review_rows)
    conn.commit()

    # Step 4: Marketplace Sellers & Products
    n_sellers = counts["sellers"]
    print(f"\n[5/12] Seeding {n_sellers:,} marketplace sellers...")
    seller_rows = []
    profile_rows = []
    seller_types = ["third_party", "fba_fulfilled", "brand_direct"]

    for sid in range(1, n_sellers + 1):
        s_name = f"SellerStore_{sid}_{rng.choice(LAST_NAMES)}"
        s_type = rng.choice(seller_types)
        comm = 0.1500 if s_type == "third_party" else 0.1200
        joined = random_date(rng, 2022, 2023).isoformat()
        seller_rows.append((sid, s_name, s_type, comm, "active", joined))
        profile_rows.append((sid, sid, f"TAX-{sid:08d}", round(rng.uniform(3.8, 5.0), 2), "FBA"))

    cursor.executemany("INSERT INTO sellers VALUES (?, ?, ?, ?, ?, ?);", seller_rows)
    cursor.executemany("INSERT INTO seller_profiles VALUES (?, ?, ?, ?, ?);", profile_rows)

    # Seller Product Listings
    n_seller_products = counts["seller_products"]
    seller_prod_rows = []
    for l_id in range(1, n_seller_products + 1):
        sid = rng.randint(1, n_sellers)
        pid = rng.randint(1, n_products)
        price = round(rng.uniform(15.00, 450.00), 2)
        listed = random_date(rng, 2023, 2024).isoformat()
        seller_prod_rows.append((l_id, sid, pid, None, price, "new", 0, listed))
    cursor.executemany("INSERT INTO seller_products VALUES (?, ?, ?, ?, ?, ?, ?, ?);", seller_prod_rows)
    conn.commit()

    # Step 5: Carts & Coupons
    print("\n[6/12] Seeding carts, cart items, and coupons...")
    coupon_rows = [
        (1, "WELCOME10", "percentage", 10.00, 25.00, 20.00, "2025-12-31 23:59:59", 1),
        (2, "SAVE20", "percentage", 20.00, 50.00, 50.00, "2025-12-31 23:59:59", 1),
        (3, "FLAT15", "fixed", 15.00, 75.00, 15.00, "2025-12-31 23:59:59", 1),
        (4, "PRIME50", "fixed", 50.00, 200.00, 50.00, "2025-12-31 23:59:59", 1),
    ]
    for c_idx in range(5, counts["coupons"] + 1):
        code = f"DISCOUNT{c_idx}"
        coupon_rows.append((c_idx, code, "percentage", 15.00, 30.00, 30.00, "2025-12-31 23:59:59", 1))
    cursor.executemany("INSERT INTO coupons VALUES (?, ?, ?, ?, ?, ?, ?, ?);", coupon_rows)

    cart_rows = []
    cart_item_rows = []
    ci_id = 1
    for cart_id in range(1, counts["carts"] + 1):
        cid = rng.randint(1, n_customers)
        c_status = "active" if rng.random() < 0.3 else "abandoned"
        created_dt = random_date(rng, 2024, 2024)
        cart_rows.append((cart_id, cid, c_status, created_dt.isoformat(), created_dt.isoformat()))

        # Cart items
        for _ in range(rng.randint(1, 3)):
            pid = rng.randint(1, n_products)
            cart_item_rows.append((ci_id, cart_id, pid, None, rng.randint(1, 2), created_dt.isoformat()))
            ci_id += 1
    cursor.executemany("INSERT INTO carts VALUES (?, ?, ?, ?, ?);", cart_rows)
    cursor.executemany("INSERT INTO cart_items VALUES (?, ?, ?, ?, ?, ?);", cart_item_rows)
    conn.commit()

    # Step 6: Warehouses & Inventory
    print("\n[7/12] Seeding warehouses, suppliers, and inventory balances...")
    suppliers = []
    for sup_id in range(1, counts["suppliers"] + 1):
        suppliers.append((sup_id, f"Apex Supplier {sup_id} LLC", f"contact@{sup_id}.supplier.test", "USA", 14))
    cursor.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?, ?);", suppliers)

    warehouses = []
    for w_id in range(1, counts["warehouses"] + 1):
        c, s, z = CITIES_STATES[w_id % len(CITIES_STATES)]
        warehouses.append((w_id, f"WH-{w_id:03d}", f"Fulfillment Center {w_id}", c, s, z, 500000))
    cursor.executemany("INSERT INTO warehouses VALUES (?, ?, ?, ?, ?, ?, ?);", warehouses)

    inv_rows = []
    inv_id = 1
    for pid in range(1, n_products + 1):
        for wid in range(1, 5):
            stock = rng.randint(50, 1500)
            res = rng.randint(0, min(stock, 30))
            restocked = random_date(rng, 2024, 2024).isoformat()
            inv_rows.append((inv_id, wid, pid, None, stock, res, 50, restocked))
            inv_id += 1
    cursor.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?);", inv_rows)

    # Movements
    n_movements = counts["inventory_movements"]
    movement_rows = []
    for mid in range(1, n_movements + 1):
        wid = rng.randint(1, counts["warehouses"])
        pid = rng.randint(1, n_products)
        m_type = rng.choice(["restock", "order_pick", "transfer", "cycle_count"])
        qty = rng.randint(1, 50) if m_type == "restock" else -rng.randint(1, 5)
        dt = random_date(rng, 2023, 2024).isoformat()
        movement_rows.append((mid, wid, pid, None, m_type, qty, f"REF-{mid:07d}", dt))
    cursor.executemany("INSERT INTO inventory_movements VALUES (?, ?, ?, ?, ?, ?, ?, ?);", movement_rows)
    conn.commit()

    # Step 7: Orders, Order Items, Payments, Refunds, Invoices
    n_orders = counts["orders"]
    print(f"\n[8/12] Generating {n_orders:,} reconciled orders, items, payments, and invoices...")

    oi_id = 1
    pay_id = 1
    ref_id = 1
    red_id = 1
    hist_id = 1
    order_date_map: Dict[int, datetime.datetime] = {}

    # Chunked generation for scale without massive memory spikes
    batch_size = 5000
    for chunk_start in range(1, n_orders + 1, batch_size):
        chunk_end = min(chunk_start + batch_size, n_orders + 1)
        c_orders = []
        c_items = []
        c_hist = []
        c_pays = []
        c_refs = []
        c_invs = []
        c_reds = []

        for oid in range(chunk_start, chunk_end):
            cid = rng.randint(1, n_customers)
            o_num = f"ORD-{oid:08d}"
            order_dt = random_date(rng, 2023, 2024)
            if oid <= counts["shipments"]:
                order_date_map[oid] = order_dt

            # Generate 2 to 5 items per order (average 3.5 per order, >170,000 items)
            num_items = rng.randint(2, 5)
            items_for_this_order = []
            subtotal = 0.0

            for _ in range(num_items):
                pid = rng.randint(1, n_products)
                sid = rng.randint(1, n_sellers)
                qty = rng.randint(1, 3)
                unit_p = round(rng.uniform(15.00, 199.99), 2)
                line_tot = round(qty * unit_p, 2)
                subtotal += line_tot
                c_items.append((oi_id, oid, pid, None, sid, qty, unit_p, line_tot, "delivered"))
                items_for_this_order.append(oi_id)
                oi_id += 1

            subtotal = round(subtotal, 2)

            # Reconciled financial calculation
            has_coupon = rng.random() < 0.25
            discount = round(subtotal * 0.15, 2) if has_coupon else 0.00
            taxable = max(0.00, subtotal - discount)
            tax = round(taxable * 0.0825, 2)
            shipping = 0.00 if (subtotal > 50.00 or rng.random() < 0.4) else 5.99

            # TOTAL AMOUNT INVARIANT: total = subtotal - discount + tax + shipping
            total_amt = round(subtotal - discount + tax + shipping, 2)

            # Order Status: 85% completed, 8% returned, 5% cancelled, 2% pending
            rand_stat = rng.random()
            if rand_stat < 0.85:
                stat = "completed"
                deliv_dt = (order_dt + datetime.timedelta(days=rng.randint(2, 6))).isoformat()
            elif rand_stat < 0.93:
                stat = "returned"
                deliv_dt = (order_dt + datetime.timedelta(days=rng.randint(2, 6))).isoformat()
            elif rand_stat < 0.98:
                stat = "cancelled"
                deliv_dt = None
            else:
                stat = "pending"
                deliv_dt = None

            c_orders.append((
                oid, o_num, cid, cid, stat, subtotal, discount, tax, shipping,
                total_amt, "USD", order_dt.isoformat(), deliv_dt
            ))

            # Status history
            c_hist.append((hist_id, oid, None, "created", "Order received", order_dt.isoformat()))
            hist_id += 1
            if stat in ("completed", "returned"):
                c_hist.append((
                    hist_id, oid, "created", stat, "Order fulfilled",
                    (order_dt + datetime.timedelta(days=3)).isoformat()
                ))
                hist_id += 1

            # Coupon redemption
            if has_coupon:
                c_reds.append((
                    red_id, rng.randint(1, 4), cid, oid, discount, order_dt.isoformat()
                ))
                red_id += 1

            # Payments
            pay_stat = "successful" if stat != "cancelled" else "failed"
            txn_ref = f"TXN-{oid:08d}-{pay_id:06d}"
            c_pays.append((
                pay_id, oid, "credit_card", "stripe", total_amt, pay_stat,
                txn_ref, order_dt.isoformat()
            ))
            pay_for_order = pay_id
            pay_id += 1

            # Refunds for returned orders (RECONCILED: refund <= total_amount)
            if stat == "returned":
                ref_amt = total_amt  # full refund
                ref_dt = (order_dt + datetime.timedelta(days=rng.randint(7, 14))).isoformat()
                c_refs.append((ref_id, oid, pay_for_order, ref_amt, "Customer return", "completed", ref_dt))
                ref_id += 1

            # Invoices
            inv_num = f"INV-{oid:08d}"
            c_invs.append((
                oid, oid, inv_num, order_dt.date().isoformat(), total_amt, tax,
                1 if stat != "cancelled" else 0
            ))

        cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", c_orders)
        cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", c_items)
        cursor.executemany("INSERT INTO order_status_history VALUES (?, ?, ?, ?, ?, ?);", c_hist)
        cursor.executemany("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?, ?);", c_pays)
        cursor.executemany("INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?, ?);", c_refs)
        cursor.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?);", c_invs)
        if c_reds:
            cursor.executemany("INSERT INTO coupon_redemptions VALUES (?, ?, ?, ?, ?, ?);", c_reds)
        conn.commit()

    # Step 8: Shipping & Fulfillment Domain
    print("\n[9/12] Seeding shipping carriers, shipments, items, and tracking events...")
    carriers = [
        (1, "Amazon Logistics", "prime_two_day", "https://track.amazon.test/?id={}"),
        (2, "UPS", "ground", "https://track.ups.test/?id={}"),
        (3, "FedEx", "express", "https://track.fedex.test/?id={}"),
        (4, "USPS", "priority", "https://track.usps.test/?id={}")
    ]
    cursor.executemany("INSERT INTO shipping_carriers VALUES (?, ?, ?, ?);", carriers)

    n_shipments = counts["shipments"]
    shipment_rows = []
    s_item_rows = []
    tracking_rows = []
    si_id = 1
    ev_id = 1

    for s_id in range(1, n_shipments + 1):
        # Link to completed order
        oid = s_id
        o_date = order_date_map.get(oid, datetime.datetime(2023, 1, 1))
        car_id = rng.randint(1, 4)
        t_num = f"TRACK-{s_id:09d}"
        cost = round(rng.uniform(3.50, 12.00), 2)
        shipped_dt = o_date + datetime.timedelta(days=rng.randint(1, 2), hours=rng.randint(1, 12))
        est_deliv = shipped_dt + datetime.timedelta(days=2)
        deliv_dt = shipped_dt + datetime.timedelta(days=rng.choice([1, 2, 3]))
        status = "delivered"

        shipment_rows.append((
            s_id, oid, car_id, t_num, cost, status,
            shipped_dt.isoformat(), est_deliv.isoformat(), deliv_dt.isoformat()
        ))

        s_item_rows.append((si_id, s_id, s_id, 1))
        si_id += 1

        # 4 Tracking events per shipment (>= 150,000 total events)
        tracking_rows.append((ev_id, s_id, "Label Created", "Origin Fulfillment Center", shipped_dt.isoformat()))
        ev_id += 1
        tracking_rows.append((
            ev_id, s_id, "Picked Up by Carrier", "Origin Sorting Facility",
            (shipped_dt + datetime.timedelta(hours=4)).isoformat()
        ))
        ev_id += 1
        tracking_rows.append((
            ev_id, s_id, "In Transit", "Regional Sorting Hub",
            (shipped_dt + datetime.timedelta(days=1)).isoformat()
        ))
        ev_id += 1
        tracking_rows.append((
            ev_id, s_id, "Delivered", "Customer Doorstep", deliv_dt.isoformat()
        ))
        ev_id += 1

    cursor.executemany("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", shipment_rows)
    cursor.executemany("INSERT INTO shipment_items VALUES (?, ?, ?, ?);", s_item_rows)
    cursor.executemany("INSERT INTO shipment_tracking_events VALUES (?, ?, ?, ?, ?);", tracking_rows)
    conn.commit()

    # Step 9: Returns & Customer Support Domain
    print("\n[10/12] Seeding returns, support tickets, and customer service...")
    agents = []
    for a_id in range(1, counts["support_agents"] + 1):
        agents.append((a_id, f"Agent {a_id}", f"agent_{a_id}@support.test", rng.choice([1, 2, 3]), 1))
    cursor.executemany("INSERT INTO support_agents VALUES (?, ?, ?, ?, ?);", agents)

    return_rows = []
    return_item_rows = []
    ticket_rows = []
    ret_id = 1
    reti_id = 1

    for ret_id in range(1, counts["returns"] + 1):
        oid = ret_id * 5  # sparse returned orders
        cid = rng.randint(1, n_customers)
        reason = rng.choice(["Wrong size/item", "Defective/damaged", "Arrived late", "Not as described"])
        created = random_date(rng, 2023, 2024).isoformat()
        return_rows.append((ret_id, oid, cid, reason, "completed", created))
        return_item_rows.append((reti_id, ret_id, ret_id, 1, "opened", 39.99))
        reti_id += 1

    for tid in range(1, counts["support_tickets"] + 1):
        cid = rng.randint(1, n_customers)
        oid = rng.randint(1, n_orders)
        aid = rng.randint(1, counts["support_agents"])
        cat = rng.choice(["Shipping Delay", "Billing Issue", "Product Incompatibility", "Return Inquiry"])
        pri = rng.choice(["normal", "high", "low"])
        res_time = round(rng.uniform(1.2, 48.0), 2)
        created = random_date(rng, 2023, 2024)
        resolved = created + datetime.timedelta(hours=res_time)
        ticket_rows.append((
            tid, cid, oid, aid, cat, pri, "resolved", res_time,
            created.isoformat(), resolved.isoformat()
        ))

    cursor.executemany("INSERT INTO returns VALUES (?, ?, ?, ?, ?, ?);", return_rows)
    cursor.executemany("INSERT INTO return_items VALUES (?, ?, ?, ?, ?, ?);", return_item_rows)
    cursor.executemany("INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", ticket_rows)
    conn.commit()

    # Step 10: Promotions & Marketing Domain
    print("\n[11/12] Seeding advertising campaigns, impressions, and clicks...")
    campaigns = []
    for c_id in range(1, counts["campaigns"] + 1):
        c_name = f"Campaign_2024_{c_id}_{rng.choice(['Summer', 'BlackFriday', 'PrimeDay', 'BackToSchool'])}"
        channel = rng.choice(["search_ads", "display_banner", "sponsored_products", "email"])
        budget = round(rng.uniform(5000.00, 50000.00), 2)
        spend = round(budget * rng.uniform(0.65, 0.98), 2)
        campaigns.append((c_id, c_name, channel, budget, spend, "2024-01-01", "2024-12-31", 1))
    cursor.executemany("INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?, ?, ?);", campaigns)

    imp_rows = []
    click_rows = []
    click_id = 1
    n_impressions = counts["impressions"]
    for i_id in range(1, n_impressions + 1):
        camp_id = rng.randint(1, counts["campaigns"])
        pid = rng.randint(1, n_products)
        viewed_dt = random_date(rng, 2024, 2024).isoformat()
        cpm = round(rng.uniform(1.20, 2.50), 4)
        imp_rows.append((i_id, camp_id, pid, cpm, viewed_dt))

        # ~20% click through rate synthetic allocation
        if rng.random() < 0.20 and click_id <= counts["clicks"]:
            cid = rng.randint(1, n_customers)
            cpc = round(rng.uniform(0.15, 0.65), 2)
            click_rows.append((click_id, i_id, camp_id, cid, cpc, viewed_dt))
            click_id += 1

    cursor.executemany("INSERT INTO ad_impressions VALUES (?, ?, ?, ?, ?);", imp_rows)
    cursor.executemany("INSERT INTO ad_clicks VALUES (?, ?, ?, ?, ?, ?);", click_rows)
    conn.commit()

    # Step 11: Subscriptions, Daily Sales, and Currency Domain
    print("\n[12/12] Seeding recurring subscriptions and daily reporting metrics...")
    sub_rows = []
    sub_ev_rows = []
    sub_ev_id = 1
    for s_id in range(1, counts["subscriptions"] + 1):
        cid = rng.randint(1, n_customers)
        pid = rng.randint(1, n_products)
        price = round(rng.uniform(9.99, 49.99), 2)
        start = random_date(rng, 2023, 2024)
        next_bill = start + datetime.timedelta(days=30)
        sub_rows.append((s_id, cid, pid, "monthly", "active", price, start.date().isoformat(), next_bill.date().isoformat()))

        # Events
        for ev_i in range(3):
            ev_dt = (start + datetime.timedelta(days=ev_i * 30)).isoformat()
            sub_ev_rows.append((sub_ev_id, s_id, "renewal_billed", price, ev_dt))
            sub_ev_id += 1

    cursor.executemany("INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?);", sub_rows)
    cursor.executemany("INSERT INTO subscription_events VALUES (?, ?, ?, ?, ?);", sub_ev_rows)

    # Seller Payouts
    payout_rows = []
    p_id = 1
    for sid in range(1, n_sellers + 1):
        for m in range(1, 13):
            p_date = f"2024-{m:02d}-28"
            gross = round(rng.uniform(2500.00, 45000.00), 2)
            comm = round(gross * 0.15, 2)
            net = round(gross - comm, 2)
            payout_rows.append((p_id, sid, p_date, gross, comm, net, "completed"))
            p_id += 1
    cursor.executemany("INSERT INTO seller_payouts VALUES (?, ?, ?, ?, ?, ?, ?);", payout_rows)

    # Daily reporting metrics (Reconciled aggregate historical metrics)
    base_date = datetime.date(2023, 1, 1)
    daily_rows = []
    for d in range(counts["daily_sales_days"]):
        m_date = (base_date + datetime.timedelta(days=d)).isoformat()
        t_orders = rng.randint(45, 120)
        gmv = round(t_orders * rng.uniform(65.00, 140.00), 2)
        refunds = round(gmv * rng.uniform(0.02, 0.08), 2)
        net = round(gmv - refunds, 2)
        new_cust = rng.randint(5, 25)
        daily_rows.append((d + 1, m_date, t_orders, gmv, refunds, net, new_cust))
    cursor.executemany("INSERT INTO daily_sales_metrics VALUES (?, ?, ?, ?, ?, ?, ?);", daily_rows)

    # Exchange rates
    rates = [("EUR", 1.085000), ("GBP", 1.272000), ("CAD", 0.741000), ("JPY", 0.006500), ("AUD", 0.655000)]
    rate_rows = []
    r_id = 1
    for day_i in range(counts["exchange_rates_days"]):
        r_date = (datetime.date(2024, 1, 1) + datetime.timedelta(days=day_i)).isoformat()
        for cur, r_base in rates:
            fluct = round(r_base * rng.uniform(0.98, 1.02), 6)
            rate_rows.append((r_id, cur, fluct, r_date))
            r_id += 1
    cursor.executemany("INSERT INTO exchange_rates VALUES (?, ?, ?, ?);", rate_rows)
    conn.commit()

    # Post-load index creation
    print("\nBuilding secondary indexes for high-performance joins and query execution...")
    idx_start = time.time()
    cursor.executescript(index_ddl)
    conn.commit()
    print(f"Indexes built in {time.time() - idx_start:.2f}s.")

    # Re-enable foreign keys and verify integrity
    print("\nRunning SQLite database integrity and foreign key checks...")
    cursor.execute("PRAGMA foreign_keys = ON;")
    fk_errors = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_errors:
        print(f"WARNING: Foreign key violations detected: {len(fk_errors)}")
    else:
        print("✓ PRAGMA foreign_key_check: 0 violations.")

    integrity = cursor.execute("PRAGMA integrity_check;").fetchall()
    print(f"✓ PRAGMA integrity_check: {integrity[0][0]}.")

    # Table row counts summary
    tbl_query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    tables = [row[0] for row in cursor.execute(tbl_query).fetchall()]
    total_rows = 0
    print("\n============================================================")
    print(f"FINAL TABLE INVENTORY ({len(tables)} Tables)")
    print("============================================================")
    for tbl in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl};").fetchone()[0]
        total_rows += count
        print(f"  • {tbl:<32} {count:>10,} rows")

    conn.close()

    total_time = time.time() - start_total_time
    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    print("\n============================================================")
    print("DATABASE GENERATION COMPLETE")
    print(f"Total Tables:      {len(tables)}")
    print(f"Total Rows:        {total_rows:,}")
    print(f"File Size:         {file_size_mb:.2f} MB")
    print(f"Generation Time:   {total_time:.2f} seconds")
    print(f"Output File:       {output_path}")
    print("============================================================")


def main():
    parser = argparse.ArgumentParser(
        description="TESH-Query Amazon-Scale Ecommerce Testing Database Generator."
    )
    parser.add_argument(
        "--profile",
        choices=["standard", "large"],
        default="standard",
        help="Database size profile (default: standard).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Target database file path (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite target database file if it already exists.",
    )

    args = parser.parse_args()
    generate_database(
        output_path=args.output,
        profile_name=args.profile,
        seed=args.seed,
        force=args.force,
    )


if __name__ == "__main__":
    main()
