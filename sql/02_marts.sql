-- All monetary totals are aggregated independently BEFORE any one-to-many joins.
-- search_path is set safely by the client to its owned rl_real/rl_synthetic schema.
DROP TABLE IF EXISTS mart_items, mart_orders, mart_cohorts, dim_date, dim_product,
    dim_seller, quality_summary;

CREATE TABLE mart_orders AS
WITH items AS (
    SELECT order_id, count(*)::int AS item_count,
        count(*) FILTER (WHERE price IS NULL)::int AS missing_price_count,
        count(*) FILTER (WHERE freight_value IS NULL)::int AS missing_freight_count,
        sum(price) AS item_value, sum(price + freight_value) AS expected_amount,
        count(DISTINCT seller_id)::int AS seller_count,
        CASE WHEN count(DISTINCT seller_id) = 1 AND count(seller_id) = count(*)
             THEN min(seller_id) END AS single_seller_id
    FROM stg_items GROUP BY order_id
), payments AS (
    SELECT order_id, count(*)::int AS payment_count,
        count(*) FILTER (WHERE payment_value IS NULL)::int AS missing_payment_count,
        sum(payment_value) AS paid_amount
    FROM stg_payments GROUP BY order_id
), latest_time AS (
    SELECT order_id, max(review_answer_timestamp) AS latest
    FROM stg_reviews WHERE review_score BETWEEN 1 AND 5
        AND review_answer_timestamp IS NOT NULL GROUP BY order_id
), latest_reviews AS (
    SELECT r.order_id, count(DISTINCT review_score) > 1 AS review_ambiguous,
        CASE WHEN count(DISTINCT review_score) = 1 THEN min(review_score) END AS review_score
    FROM stg_reviews r JOIN latest_time t ON r.order_id = t.order_id
        AND r.review_answer_timestamp = t.latest
    WHERE review_score BETWEEN 1 AND 5 GROUP BY r.order_id
), review_counts AS (
    SELECT order_id, count(*)::int AS review_count FROM stg_reviews GROUP BY order_id
), rejected AS (
    SELECT order_id,
        count(*) FILTER (WHERE table_name = 'items') AS rejected_items,
        count(*) FILTER (WHERE table_name = 'payments') AS rejected_payments
    FROM import_issues WHERE severity = 'REJECTED' GROUP BY order_id
), joined AS (
    SELECT o.order_id, o.order_status, o.order_purchase_timestamp AS purchase_timestamp,
        o.order_purchase_timestamp::date AS purchase_date, c.customer_unique_id,
        coalesce(c.customer_state, 'Unknown') AS customer_state,
        coalesce(i.item_count, 0) AS item_count,
        coalesce(i.missing_price_count, 0) AS missing_price_count,
        coalesce(i.missing_freight_count, 0) AS missing_freight_count,
        CASE WHEN i.item_count > 0 AND i.missing_price_count = 0
                  AND coalesce(x.rejected_items, 0) = 0 THEN i.item_value END AS item_value,
        CASE WHEN i.item_count > 0 AND i.missing_price_count = 0
                  AND i.missing_freight_count = 0 AND coalesce(x.rejected_items, 0) = 0
             THEN i.expected_amount END AS expected_amount,
        CASE WHEN p.payment_count > 0 AND p.missing_payment_count = 0
                  AND coalesce(x.rejected_payments, 0) = 0 THEN p.paid_amount END AS paid_amount,
        coalesce(p.missing_payment_count, 0) AS missing_payment_count,
        coalesce(i.seller_count, 0) AS seller_count,
        CASE WHEN coalesce(x.rejected_items, 0) = 0 AND EXISTS(
            SELECT 1 FROM stg_sellers s WHERE s.seller_id = i.single_seller_id
        ) THEN i.single_seller_id END AS single_seller_id,
        coalesce(r.review_ambiguous, false) AS review_ambiguous, r.review_score,
        coalesce(rc.review_count, 0) AS review_count,
        (o.order_status = 'delivered' AND o.order_purchase_timestamp IS NOT NULL
            AND i.item_count > 0 AND i.missing_price_count = 0
            AND coalesce(x.rejected_items, 0) = 0) AS gmv_eligible,
        (o.order_status = 'delivered' AND o.order_purchase_timestamp IS NOT NULL
            AND o.order_delivered_customer_date IS NOT NULL
            AND o.order_estimated_delivery_date IS NOT NULL
            AND o.order_delivered_customer_date >= o.order_purchase_timestamp
            AND o.order_estimated_delivery_date::date >= o.order_purchase_timestamp::date
            AND (o.order_approved_at IS NULL OR
                (o.order_approved_at >= o.order_purchase_timestamp
                 AND o.order_approved_at <= o.order_delivered_customer_date))
            AND (o.order_delivered_carrier_date IS NULL OR
                (o.order_delivered_carrier_date >= o.order_purchase_timestamp
                 AND o.order_delivered_carrier_date <= o.order_delivered_customer_date
                 AND (o.order_approved_at IS NULL
                      OR o.order_delivered_carrier_date >= o.order_approved_at)))) AS delivery_eligible,
        (o.order_delivered_customer_date::date <= o.order_estimated_delivery_date::date)
            AS source_on_time,
        (o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date)
            AS source_delay_days
    FROM stg_orders o LEFT JOIN stg_customers c USING (customer_id)
    LEFT JOIN items i USING (order_id) LEFT JOIN payments p USING (order_id)
    LEFT JOIN latest_reviews r USING (order_id) LEFT JOIN review_counts rc USING (order_id)
    LEFT JOIN rejected x USING (order_id)
)
SELECT order_id, order_status, purchase_timestamp, purchase_date, customer_unique_id,
    customer_state, item_count, missing_price_count, missing_freight_count,
    item_value, expected_amount, paid_amount, missing_payment_count, seller_count,
    single_seller_id, review_ambiguous, review_score, review_count,
    coalesce(gmv_eligible, false) AS gmv_eligible,
    coalesce(delivery_eligible, false) AS delivery_eligible,
    CASE WHEN delivery_eligible THEN source_on_time END AS is_on_time,
    CASE WHEN delivery_eligible THEN greatest(source_delay_days, 0) END AS delay_days,
    coalesce(delivery_eligible AND review_score IS NOT NULL AND NOT review_ambiguous, false)
        AS reviewed_eligible,
    paid_amount - expected_amount AS payment_delta,
    CASE WHEN expected_amount IS NULL OR paid_amount IS NULL THEN 'not_comparable'
         WHEN abs(paid_amount - expected_amount) <=
             (SELECT reconciliation_tolerance FROM run_metadata) THEN 'matched'
         ELSE 'mismatch' END AS reconciliation_status
FROM joined;
ALTER TABLE mart_orders ADD PRIMARY KEY (order_id);
CREATE INDEX mart_orders_date_idx ON mart_orders(purchase_date);

CREATE TABLE dim_product AS
SELECT p.product_id, coalesce(t.product_category_name_english, p.product_category_name, 'Unknown')
    AS category FROM stg_products p LEFT JOIN stg_translations t USING (product_category_name)
UNION ALL SELECT '__unknown__', 'Unknown';
ALTER TABLE dim_product ADD PRIMARY KEY (product_id);
CREATE TABLE dim_seller AS
SELECT seller_id, coalesce(seller_state, 'Unknown') AS seller_state FROM stg_sellers
UNION ALL SELECT '__unknown__', 'Unknown';
ALTER TABLE dim_seller ADD PRIMARY KEY (seller_id);
CREATE TABLE mart_items AS
SELECT i.order_id, i.order_item_id, o.purchase_date,
    coalesce(p.product_id, '__unknown__') AS product_id,
    coalesce(s.seller_id, '__unknown__') AS seller_id, i.price, i.freight_value,
    o.gmv_eligible FROM stg_items i JOIN mart_orders o USING (order_id)
LEFT JOIN stg_products p USING (product_id) LEFT JOIN stg_sellers s USING (seller_id);
ALTER TABLE mart_items ADD PRIMARY KEY(order_id, order_item_id);

CREATE TABLE dim_date AS
SELECT d::date AS date, extract(year FROM d)::int AS year,
    extract(month FROM d)::int AS month, to_char(d, 'YYYY-MM') AS year_month,
    (date_trunc('month', d) = date_trunc('month', m.analysis_start::timestamp)
     OR date_trunc('month', d) = date_trunc('month',
         (m.analysis_end_exclusive - 1)::timestamp)) AS is_boundary_month
FROM run_metadata m CROSS JOIN LATERAL generate_series(m.analysis_start::timestamp,
    (m.analysis_end_exclusive - 1)::timestamp, interval '1 day') d;
ALTER TABLE dim_date ADD PRIMARY KEY(date);

-- First observed delivered purchase is computed over ALL source dates before report filtering.
CREATE TABLE mart_cohorts AS
WITH delivered AS (
    SELECT order_id, customer_unique_id, purchase_timestamp FROM mart_orders
    WHERE order_status = 'delivered' AND purchase_timestamp IS NOT NULL
        AND customer_unique_id IS NOT NULL
), firsts AS (
    SELECT customer_unique_id, min(purchase_timestamp) AS first_purchase_timestamp
    FROM delivered GROUP BY customer_unique_id
)
SELECT f.customer_unique_id, f.first_purchase_timestamp,
    f.first_purchase_timestamp::date AS first_purchase_date,
    f.first_purchase_timestamp + interval '90 days' <= m.observation_end::timestamp
        AS eligible_90d,
    bool_or(d.purchase_timestamp > f.first_purchase_timestamp
        AND d.purchase_timestamp <= f.first_purchase_timestamp + interval '90 days') AS repeated_90d,
    count(*) FILTER(WHERE d.purchase_timestamp = f.first_purchase_timestamp)::int - 1
        AS same_timestamp_orders
FROM firsts f JOIN delivered d USING(customer_unique_id) CROSS JOIN run_metadata m
GROUP BY f.customer_unique_id,f.first_purchase_timestamp,m.observation_end;
ALTER TABLE mart_cohorts ADD PRIMARY KEY(customer_unique_id);

CREATE TABLE quality_summary AS
SELECT issue AS check_name, severity, count(*)::int AS affected_rows,
    'See import_issues and raw_records for source provenance'::text AS details
FROM import_issues GROUP BY issue, severity
UNION ALL SELECT 'delivered_gmv_excluded', 'WARNING', count(*)::int,
    'Delivered orders outside the complete item price population'
    FROM mart_orders WHERE order_status = 'delivered' AND NOT gmv_eligible
UNION ALL SELECT 'delivery_excluded', 'WARNING', count(*)::int,
    'Delivered orders with missing dates or inconsistent chronology'
    FROM mart_orders WHERE order_status = 'delivered' AND NOT delivery_eligible
UNION ALL SELECT 'review_ambiguous', 'WARNING', count(*)::int,
    'Conflicting valid scores tied at latest answer timestamp'
    FROM mart_orders WHERE review_ambiguous
UNION ALL SELECT 'multiple_sellers', 'INFO', count(*)::int,
    'Excluded from seller-specific delivery/review metrics'
    FROM mart_orders WHERE seller_count <> 1 OR single_seller_id IS NULL
UNION ALL SELECT 'incomplete_repeat_window', 'WARNING', count(*)::int,
    'First purchase lacks a full assumed 90 day observation window'
    FROM mart_cohorts WHERE NOT eligible_90d
UNION ALL SELECT 'missing_customer_mapping', 'WARNING', count(*)::int,
    'Cannot link to a person; excluded from repeat cohorts'
    FROM mart_orders WHERE customer_unique_id IS NULL
UNION ALL SELECT 'reconciliation_not_comparable', 'WARNING', count(*)::int,
    'At least one side incomplete; no financial inference'
    FROM mart_orders WHERE reconciliation_status = 'not_comparable';

ANALYZE mart_orders;
ANALYZE mart_items;
