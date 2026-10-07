SELECT d.year_month, d.is_boundary_month,
    count(o.order_id) AS source_orders,
    count(*) FILTER(WHERE o.gmv_eligible) AS delivered_orders,
    sum(o.item_value) FILTER(WHERE o.gmv_eligible) AS delivered_gmv_brl,
    sum(o.item_value) FILTER(WHERE o.gmv_eligible) /
        nullif(count(*) FILTER(WHERE o.gmv_eligible),0) AS delivered_aov_brl
FROM dim_date d LEFT JOIN mart_orders o ON o.purchase_date = d.date
WHERE d.date >= %(start)s AND d.date < %(end)s
GROUP BY d.year_month,d.is_boundary_month ORDER BY d.year_month;
