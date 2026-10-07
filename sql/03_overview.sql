SELECT count(*) AS orders,
    count(*) FILTER(WHERE gmv_eligible) AS delivered_orders,
    sum(item_value) FILTER(WHERE gmv_eligible) AS delivered_gmv_brl,
    sum(item_value) FILTER(WHERE gmv_eligible) /
        nullif(count(*) FILTER(WHERE gmv_eligible), 0) AS delivered_aov_brl,
    count(*) FILTER(WHERE delivery_eligible) AS delivery_eligible_orders,
    count(*) FILTER(WHERE delivery_eligible AND is_on_time) AS on_time_orders,
    count(*) FILTER(WHERE delivery_eligible AND is_on_time)::numeric /
        nullif(count(*) FILTER(WHERE delivery_eligible), 0) AS on_time_rate,
    count(*) FILTER(WHERE order_status = 'delivered' AND NOT delivery_eligible)
        AS delivered_delivery_exclusions
FROM mart_orders WHERE purchase_date >= %(start)s AND purchase_date < %(end)s;
