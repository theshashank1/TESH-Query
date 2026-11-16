-- TESH-Query Amazon-Scale Ecommerce Testing Schema
-- 45 Normalized Relational Tables spanning 10 Core Business Domains

PRAGMA foreign_keys = ON;

-- ============================================================================
-- DOMAIN A: Customers & Identity (Tables 1-5)
-- ============================================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(30),
    account_status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customers(customer_id) ON DELETE CASCADE,
    birth_year INTEGER,
    gender VARCHAR(20),
    preferred_language VARCHAR(10) DEFAULT 'en',
    annual_income_bracket VARCHAR(30),
    prime_member BOOLEAN DEFAULT 0,
    loyalty_tier VARCHAR(20) DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    address_type VARCHAR(20) NOT NULL DEFAULT 'shipping',
    street_line1 VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    is_default BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customer_segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    min_annual_spend NUMERIC(10, 2) DEFAULT 0.00,
    min_order_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customer_segment_memberships (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    segment_id INTEGER NOT NULL REFERENCES customer_segments(segment_id) ON DELETE CASCADE,
    assigned_at DATETIME NOT NULL,
    UNIQUE(customer_id, segment_id)
);

-- ============================================================================
-- DOMAIN B: Product Catalog (Tables 6-12)
-- ============================================================================

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES categories(category_id),
    category_name VARCHAR(100) NOT NULL,
    category_slug VARCHAR(100) UNIQUE NOT NULL,
    category_level INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS brands (
    brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name VARCHAR(100) UNIQUE NOT NULL,
    country_of_origin VARCHAR(50),
    is_verified BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    brand_id INTEGER REFERENCES brands(brand_id),
    base_price NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS product_variants (
    variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    variant_sku VARCHAR(60) UNIQUE NOT NULL,
    variant_name VARCHAR(100) NOT NULL,
    price_modifier NUMERIC(10, 2) DEFAULT 0.00,
    weight_kg NUMERIC(8, 2) DEFAULT 0.50,
    is_available BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS product_attributes (
    attribute_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attribute_name VARCHAR(50) UNIQUE NOT NULL,
    data_type VARCHAR(20) DEFAULT 'string'
);

CREATE TABLE IF NOT EXISTS product_attribute_values (
    val_id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES product_variants(variant_id) ON DELETE CASCADE,
    attribute_id INTEGER NOT NULL REFERENCES product_attributes(attribute_id) ON DELETE CASCADE,
    attr_value VARCHAR(100) NOT NULL,
    UNIQUE(variant_id, attribute_id)
);

CREATE TABLE IF NOT EXISTS product_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(200),
    review_text TEXT,
    helpful_votes INTEGER DEFAULT 0,
    verified_purchase BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL
);

-- ============================================================================
-- DOMAIN C: Sellers & Marketplace (Tables 13-16)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sellers (
    seller_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_name VARCHAR(100) UNIQUE NOT NULL,
    seller_type VARCHAR(30) DEFAULT 'third_party',
    commission_rate NUMERIC(5, 4) DEFAULT 0.1500,
    status VARCHAR(20) DEFAULT 'active',
    joined_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS seller_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL UNIQUE REFERENCES sellers(seller_id) ON DELETE CASCADE,
    tax_id VARCHAR(50),
    rating_score NUMERIC(3, 2) DEFAULT 4.50,
    fulfillment_type VARCHAR(20) DEFAULT 'FBA'
);

CREATE TABLE IF NOT EXISTS seller_products (
    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES sellers(seller_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES product_variants(variant_id) ON DELETE CASCADE,
    seller_price NUMERIC(10, 2) NOT NULL,
    condition VARCHAR(20) DEFAULT 'new',
    is_featured BOOLEAN DEFAULT 0,
    listed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS seller_payouts (
    payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL REFERENCES sellers(seller_id) ON DELETE CASCADE,
    payout_date DATE NOT NULL,
    gross_sales NUMERIC(12, 2) NOT NULL,
    commission_deducted NUMERIC(12, 2) NOT NULL,
    net_payout NUMERIC(12, 2) NOT NULL,
    payout_status VARCHAR(20) DEFAULT 'completed'
);

-- ============================================================================
-- DOMAIN D: Shopping Cart & Checkout (Tables 17-20)
-- ============================================================================

CREATE TABLE IF NOT EXISTS carts (
    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME NOT NULL,
    last_activity_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL REFERENCES carts(cart_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    variant_id INTEGER REFERENCES product_variants(variant_id),
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS coupons (
    coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    discount_type VARCHAR(20) NOT NULL,
    discount_val NUMERIC(10, 2) NOT NULL,
    min_order_amount NUMERIC(10, 2) DEFAULT 0.00,
    max_discount_amount NUMERIC(10, 2),
    expires_at DATETIME NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER NOT NULL REFERENCES coupons(coupon_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_id INTEGER REFERENCES orders(order_id),
    discount_applied NUMERIC(10, 2) NOT NULL,
    redeemed_at DATETIME NOT NULL
);

-- ============================================================================
-- DOMAIN E: Orders & Payments (Tables 21-26)
-- ============================================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    shipping_address_id INTEGER REFERENCES customer_addresses(address_id),
    order_status VARCHAR(30) NOT NULL DEFAULT 'completed',
    subtotal_amount NUMERIC(12, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) DEFAULT 0.00,
    tax_amount NUMERIC(10, 2) DEFAULT 0.00,
    shipping_amount NUMERIC(10, 2) DEFAULT 0.00,
    total_amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    order_date DATETIME NOT NULL,
    delivered_date DATETIME
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    variant_id INTEGER REFERENCES product_variants(variant_id),
    seller_id INTEGER REFERENCES sellers(seller_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    line_total NUMERIC(12, 2) NOT NULL,
    item_status VARCHAR(20) DEFAULT 'delivered'
);

CREATE TABLE IF NOT EXISTS order_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    from_status VARCHAR(30),
    to_status VARCHAR(30) NOT NULL,
    notes TEXT,
    changed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'credit_card',
    payment_provider VARCHAR(30) DEFAULT 'stripe',
    amount NUMERIC(12, 2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'successful',
    transaction_reference VARCHAR(100) UNIQUE NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_id INTEGER REFERENCES payments(payment_id),
    refund_amount NUMERIC(10, 2) NOT NULL,
    reason VARCHAR(100),
    refund_status VARCHAR(20) DEFAULT 'completed',
    processed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    invoice_date DATE NOT NULL,
    total_due NUMERIC(12, 2) NOT NULL,
    tax_collected NUMERIC(10, 2) NOT NULL,
    paid_in_full BOOLEAN DEFAULT 1
);

-- ============================================================================
-- DOMAIN F: Inventory & Warehouses (Tables 27-30)
-- ============================================================================

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name VARCHAR(100) UNIQUE NOT NULL,
    contact_email VARCHAR(100),
    country VARCHAR(50) DEFAULT 'USA',
    lead_time_days INTEGER DEFAULT 14
);

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_code VARCHAR(20) UNIQUE NOT NULL,
    warehouse_name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    capacity_units INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    variant_id INTEGER REFERENCES product_variants(variant_id) ON DELETE CASCADE,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    reorder_point INTEGER DEFAULT 50,
    last_restocked_at DATETIME,
    UNIQUE(warehouse_id, product_id, variant_id)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    variant_id INTEGER REFERENCES product_variants(variant_id),
    movement_type VARCHAR(30) NOT NULL,
    quantity INTEGER NOT NULL,
    reference_id VARCHAR(50),
    occurred_at DATETIME NOT NULL
);

-- ============================================================================
-- DOMAIN G: Shipping & Fulfillment (Tables 31-34)
-- ============================================================================

CREATE TABLE IF NOT EXISTS shipping_carriers (
    carrier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier_name VARCHAR(50) UNIQUE NOT NULL,
    service_tier VARCHAR(30) DEFAULT 'standard',
    tracking_url_template VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    carrier_id INTEGER NOT NULL REFERENCES shipping_carriers(carrier_id),
    tracking_number VARCHAR(100) UNIQUE NOT NULL,
    shipping_cost NUMERIC(8, 2) NOT NULL,
    shipment_status VARCHAR(30) DEFAULT 'delivered',
    shipped_at DATETIME NOT NULL,
    estimated_delivery DATETIME,
    delivered_at DATETIME
);

CREATE TABLE IF NOT EXISTS shipment_items (
    shipment_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    order_item_id INTEGER NOT NULL REFERENCES order_items(order_item_id) ON DELETE CASCADE,
    quantity_shipped INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_tracking_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    event_status VARCHAR(50) NOT NULL,
    location VARCHAR(100),
    event_timestamp DATETIME NOT NULL
);

-- ============================================================================
-- DOMAIN H: Returns & Customer Support (Tables 35-38)
-- ============================================================================

CREATE TABLE IF NOT EXISTS returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    return_reason VARCHAR(100) NOT NULL,
    status VARCHAR(30) DEFAULT 'completed',
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS return_items (
    return_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL REFERENCES returns(return_id) ON DELETE CASCADE,
    order_item_id INTEGER NOT NULL REFERENCES order_items(order_item_id),
    quantity_returned INTEGER NOT NULL,
    condition_received VARCHAR(30) DEFAULT 'opened',
    refund_item_amount NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS support_agents (
    agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    tier_level INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_id INTEGER REFERENCES orders(order_id),
    agent_id INTEGER REFERENCES support_agents(agent_id),
    category VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    status VARCHAR(20) DEFAULT 'resolved',
    resolution_time_hours NUMERIC(6, 2),
    created_at DATETIME NOT NULL,
    resolved_at DATETIME
);

-- ============================================================================
-- DOMAIN I: Promotions & Marketing (Tables 39-41)
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_name VARCHAR(100) UNIQUE NOT NULL,
    channel VARCHAR(50) NOT NULL,
    budget NUMERIC(12, 2) NOT NULL,
    spend NUMERIC(12, 2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ad_impressions (
    impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    cost_per_mille NUMERIC(6, 4) DEFAULT 1.5000,
    viewed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_clicks (
    click_id INTEGER PRIMARY KEY AUTOINCREMENT,
    impression_id INTEGER REFERENCES ad_impressions(impression_id) ON DELETE SET NULL,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    customer_id INTEGER REFERENCES customers(customer_id),
    cost_per_click NUMERIC(6, 2) DEFAULT 0.25,
    clicked_at DATETIME NOT NULL
);

-- ============================================================================
-- DOMAIN J: Subscriptions & Analytics (Tables 42-45)
-- ============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    frequency VARCHAR(20) DEFAULT 'monthly',
    status VARCHAR(20) DEFAULT 'active',
    price_per_cycle NUMERIC(10, 2) NOT NULL,
    start_date DATE NOT NULL,
    next_billing_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS subscription_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL,
    amount_billed NUMERIC(10, 2) DEFAULT 0.00,
    event_date DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_sales_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE UNIQUE NOT NULL,
    total_orders INTEGER NOT NULL,
    gross_merchandise_value NUMERIC(14, 2) NOT NULL,
    total_refunds NUMERIC(12, 2) NOT NULL,
    net_sales NUMERIC(14, 2) NOT NULL,
    new_customers_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_code VARCHAR(3) NOT NULL,
    rate_to_usd NUMERIC(10, 6) NOT NULL,
    as_of_date DATE NOT NULL,
    UNIQUE(currency_code, as_of_date)
);

-- ============================================================================
-- INDEXES FOR HIGH-PERFORMANCE ANALYTICS AND JOINS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_created ON customers(created_at);
CREATE INDEX IF NOT EXISTS idx_cust_addr_cust_id ON customer_addresses(customer_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_id);
CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON product_reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_customer ON product_reviews(customer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON product_reviews(rating);
CREATE INDEX IF NOT EXISTS idx_seller_products_seller ON seller_products(seller_id);
CREATE INDEX IF NOT EXISTS idx_seller_products_product ON seller_products(product_id);
CREATE INDEX IF NOT EXISTS idx_seller_payouts_seller ON seller_payouts(seller_id, payout_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller ON order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(payment_status);
CREATE INDEX IF NOT EXISTS idx_refunds_order ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id, warehouse_id);
CREATE INDEX IF NOT EXISTS idx_inv_movements_prod ON inventory_movements(product_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id);
CREATE INDEX IF NOT EXISTS idx_shipment_events_shipment ON shipment_tracking_events(shipment_id);
CREATE INDEX IF NOT EXISTS idx_returns_order ON returns(order_id);
CREATE INDEX IF NOT EXISTS idx_return_items_return ON return_items(return_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_cust ON support_tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_agent ON support_tickets(agent_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_impressions_campaign ON ad_impressions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_impressions_product ON ad_impressions(product_id);
CREATE INDEX IF NOT EXISTS idx_clicks_campaign ON ad_clicks(campaign_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_cust ON subscriptions(customer_id);
CREATE INDEX IF NOT EXISTS idx_sub_events_sub ON subscription_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_daily_sales_date ON daily_sales_metrics(metric_date);
