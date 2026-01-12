-- Marts layer: Business logic and aggregations
--
-- This layer creates analysis-ready tables for reporting and insights.

-- mart_experiment_results.sql
-- Aggregated experiment results by test and template

SELECT
    e.run_id,
    e.template_name,
    e.test_market,
    e.control_market,
    e.mde_applied,
    e.effect_shape,
    e.created_at,
    
    -- Pre-period aggregates
    AVG(CASE WHEN m.period = 'pre_period' THEN m.test_value END) AS pre_period_test_mean,
    AVG(CASE WHEN m.period = 'pre_period' THEN m.control_value END) AS pre_period_control_mean,
    STDDEV(CASE WHEN m.period = 'pre_period' THEN m.test_value END) AS pre_period_test_std,
    STDDEV(CASE WHEN m.period = 'pre_period' THEN m.control_value END) AS pre_period_control_std,
    
    -- Post-period aggregates
    AVG(CASE WHEN m.period = 'post_period' THEN m.test_value END) AS post_period_test_mean,
    AVG(CASE WHEN m.period = 'post_period' THEN m.control_value END) AS post_period_control_mean,
    
    -- Difference metrics
    (AVG(CASE WHEN m.period = 'post_period' THEN m.test_value END) - 
     AVG(CASE WHEN m.period = 'pre_period' THEN m.test_value END)) AS test_lift_absolute,
    
    ((AVG(CASE WHEN m.period = 'post_period' THEN m.test_value END) - 
      AVG(CASE WHEN m.period = 'pre_period' THEN m.test_value END)) /
     AVG(CASE WHEN m.period = 'pre_period' THEN m.test_value END) * 100) AS test_lift_pct,
    
    COUNT(DISTINCT CASE WHEN m.period = 'post_period' THEN m.date END) AS post_period_days,
    COUNT(DISTINCT CASE WHEN m.period = 'pre_period' THEN m.date END) AS pre_period_days
    
FROM experiments e
LEFT JOIN experiment_metrics m ON e.run_id = m.run_id
GROUP BY 
    e.run_id,
    e.template_name,
    e.test_market,
    e.control_market,
    e.mde_applied,
    e.effect_shape,
    e.created_at
ORDER BY e.created_at DESC
