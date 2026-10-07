SELECT p.category,s.seller_id,s.seller_state,
    count(DISTINCT i.order_id) AS segment_orders,
    sum(i.price) AS delivered_segment_item_value_brl,
    sum(i.price) / nullif(count(DISTINCT i.order_id),0) AS segment_item_value_per_order_brl,
    sum(i.price) / nullif(sum(sum(i.price)) OVER(),0) AS item_value_share
FROM mart_items i JOIN dim_product p USING(product_id) JOIN dim_seller s USING(seller_id)
WHERE i.gmv_eligible AND i.purchase_date >= %(start)s AND i.purchase_date < %(end)s
GROUP BY p.category,s.seller_id,s.seller_state ORDER BY delivered_segment_item_value_brl DESC;
