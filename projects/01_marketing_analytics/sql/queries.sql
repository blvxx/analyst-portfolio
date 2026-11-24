-- Run against outputs/marketing.duckdb.

SELECT
    COUNT(*) AS sessions,
    COUNT(*) FILTER (WHERE revenue) AS purchases,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions;

SELECT
    visitor_type,
    COUNT(*) AS sessions,
    SUM(CAST(revenue AS INTEGER)) AS purchases,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions
GROUP BY visitor_type
ORDER BY sessions DESC;

SELECT
    traffic_type,
    COUNT(*) AS sessions,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions
GROUP BY traffic_type
ORDER BY sessions DESC;
