-- Staging layer: Raw simulation data transformations
-- 
-- This layer takes raw simulated data and cleans/transforms it
-- for use in downstream mart tables.

-- stg_daily_metrics.sql
-- Transform raw experiment metrics into standardized format

SELECT
    run_id,
    date,
    CASE 
        WHEN date < DATE('2024-12-31') THEN 'pre_period'
        ELSE 'post_period'
    END AS period,
    test_value AS test_market_metric,
    control_value AS control_market_metric,
    test_value - control_value AS raw_difference,
    CASE 
        WHEN control_value != 0 
        THEN ((test_value - control_value) / control_value) * 100 
        ELSE 0 
    END AS difference_pct,
    day_num,
    EXTRACT(DOW FROM date) AS day_of_week,
    EXTRACT(WEEK FROM date) AS week_number
FROM experiment_metrics
WHERE test_value > 0 AND control_value > 0
ORDER BY run_id, date
