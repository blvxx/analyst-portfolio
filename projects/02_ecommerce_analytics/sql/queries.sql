-- Run against outputs/ecommerce.duckdb.
-- Source: UCI Online Retail II; gross sales exclude cancellation/return rows.

-- 1. Monthly gross sales, order count, average order value and month-over-month change.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date) AS order_month,
        SUM(line_revenue_gbp) AS gross_sales_gbp,
        COUNT(DISTINCT invoice) AS orders
    FROM clean_sales
    GROUP BY 1
),
lagged AS (
    SELECT
        *,
        LAG(gross_sales_gbp) OVER (ORDER BY order_month) AS previous_month_sales
    FROM monthly
)
SELECT
    order_month,
    gross_sales_gbp,
    orders,
    gross_sales_gbp / NULLIF(orders, 0) AS average_order_value_gbp,
    gross_sales_gbp - previous_month_sales AS absolute_mom_change_gbp,
    (gross_sales_gbp / NULLIF(previous_month_sales, 0)) - 1 AS relative_mom_change
FROM lagged
ORDER BY order_month;

-- 2. RFM score distribution and average customer value.
SELECT
    rfm_segment,
    COUNT(*) AS customers,
    AVG(recency_days) AS average_recency_days,
    AVG(frequency) AS average_orders,
    AVG(monetary_gbp) AS average_customer_revenue_gbp
FROM customer_rfm
GROUP BY rfm_segment
ORDER BY customers DESC;

-- 3. Rank countries by gross sales and calculate cumulative revenue contribution.
WITH country_revenue AS (
    SELECT
        country,
        SUM(line_revenue_gbp) AS gross_sales_gbp
    FROM clean_sales
    GROUP BY country
),
ranked AS (
    SELECT
        country,
        gross_sales_gbp,
        DENSE_RANK() OVER (ORDER BY gross_sales_gbp DESC) AS revenue_rank,
        SUM(gross_sales_gbp) OVER (
            ORDER BY gross_sales_gbp DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_sales_gbp,
        SUM(gross_sales_gbp) OVER () AS total_sales_gbp
    FROM country_revenue
)
SELECT
    country,
    gross_sales_gbp,
    revenue_rank,
    cumulative_sales_gbp / NULLIF(total_sales_gbp, 0) AS cumulative_revenue_share
FROM ranked
ORDER BY revenue_rank;

-- 4. Cohort retention curve calculated in the Python pipeline.
SELECT
    cohort_month,
    month_index,
    active_customers,
    cohort_size,
    retention_rate
FROM cohort_retention
ORDER BY cohort_month, month_index;
