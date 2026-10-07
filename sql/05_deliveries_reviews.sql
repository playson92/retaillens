SELECT customer_state, is_on_time,
    count(*) AS eligible_orders,
    avg(delay_days) AS mean_delay_days,
    count(review_score) AS reviewed_orders,
    count(review_score)::numeric / nullif(count(*),0) AS review_coverage,
    avg(review_score) AS mean_review_score,
    count(*) FILTER(WHERE review_score=1) AS score_1,
    count(*) FILTER(WHERE review_score=2) AS score_2,
    count(*) FILTER(WHERE review_score=3) AS score_3,
    count(*) FILTER(WHERE review_score=4) AS score_4,
    count(*) FILTER(WHERE review_score=5) AS score_5,
    count(*) FILTER(WHERE review_ambiguous) AS ambiguous_reviews
FROM mart_orders WHERE delivery_eligible AND purchase_date >= %(start)s
    AND purchase_date < %(end)s GROUP BY customer_state,is_on_time
ORDER BY customer_state,is_on_time;
