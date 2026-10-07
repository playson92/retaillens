-- Order-level outcomes only for the single-seller population; no causal attribution.
SELECT single_seller_id AS seller_id,count(*) AS eligible_orders,
    count(*) FILTER(WHERE is_on_time)::numeric/nullif(count(*),0) AS on_time_rate,
    count(review_score) AS reviewed_orders,avg(review_score) AS mean_review_score
FROM mart_orders WHERE delivery_eligible AND single_seller_id IS NOT NULL AND seller_count=1
    AND purchase_date >= %(start)s AND purchase_date < %(end)s
GROUP BY single_seller_id ORDER BY eligible_orders DESC;
