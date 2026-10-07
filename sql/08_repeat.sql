SELECT count(*) AS first_observed_people,
    count(*) FILTER(WHERE eligible_90d) AS eligible_people,
    count(*) FILTER(WHERE eligible_90d AND repeated_90d) AS repeat_people,
    count(*) FILTER(WHERE NOT eligible_90d) AS incomplete_window_people,
    count(*) FILTER(WHERE eligible_90d AND repeated_90d)::numeric /
        nullif(count(*) FILTER(WHERE eligible_90d),0) AS observed_repeat_90d_rate,
    sum(same_timestamp_orders) AS simultaneous_orders_excluded_as_repeat
FROM mart_cohorts WHERE first_purchase_date >= %(start)s AND first_purchase_date < %(end)s;
