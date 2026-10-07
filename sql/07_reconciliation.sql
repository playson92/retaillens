SELECT order_status,reconciliation_status,count(*) AS orders,
    sum(expected_amount) AS expected_brl,sum(paid_amount) AS paid_brl,
    sum(payment_delta) AS delta_brl
FROM mart_orders WHERE purchase_date >= %(start)s AND purchase_date < %(end)s
GROUP BY order_status,reconciliation_status ORDER BY order_status,reconciliation_status;
