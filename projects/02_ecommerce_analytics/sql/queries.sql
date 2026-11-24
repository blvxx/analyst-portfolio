-- Run against outputs/ecommerce.duckdb.

-- Monthly gross sales, order count and AOV
SELECT
    order_month,
    SUM(revenue_gbp) AS gross_sales_gbp,
    COUNT(DISTINCT invoice) AS orders,
    SUM(revenue_gbp) / NULLIF(COUNT(DISTINCT invoice), 0) AS aov_gbp
FROM (
    SELECT invoice, MIN(invoice_date) AS order_month, SUM(line_revenue_gbp) AS revenue_gbp
    FROM clean_sales
    GROUP BY invoice
)
GROUP BY order_month
ORDER BY order_month;

-- RFM distribution
SELECT
    rfm_segment,
    COUNT(*) AS customers,
    AVG(recency_days) AS average_recency_days,
    AVG(frequency) AS average_orders,
    AVG(monetary_gbp) AS average_customer_revenue_gbp
FROM customer_rfm
GROUP BY rfm_segment
ORDER BY customers DESC;

-- Cohort retention curve
SELECT
    cohort_month,
    month_index,
    active_customers,
    cohort_size,
    retention_rate
FROM cohort_retention
ORDER BY cohort_month, month_index;
