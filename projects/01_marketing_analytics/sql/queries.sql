-- Run from this project's directory with DuckDB CLI.
-- The Python pipeline creates outputs/marketing.duckdb and outputs/sessions.

-- Overall conversion rate
SELECT
    COUNT(*) AS sessions,
    COUNT(*) FILTER (WHERE revenue) AS purchases,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions;

-- Conversion by visitor type
SELECT
    visitortype,
    COUNT(*) AS sessions,
    SUM(CAST(revenue AS INTEGER)) AS purchases,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions
GROUP BY visitortype
ORDER BY sessions DESC;

-- Traffic type coverage and conversion
SELECT
    traffictype,
    COUNT(*) AS sessions,
    AVG(CAST(revenue AS INTEGER)) AS conversion_rate
FROM sessions
GROUP BY traffictype
ORDER BY sessions DESC;
