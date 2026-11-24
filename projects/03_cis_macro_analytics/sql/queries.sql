-- Run against outputs/cis_macro.duckdb.

-- Internet penetration trend by country.
SELECT country_name, year, internet_users_pct
FROM macro_panel
WHERE internet_users_pct IS NOT NULL
ORDER BY country_name, year;

-- Most recent non-null observation by country for GDP per capita.
WITH ranked AS (
    SELECT
        country_code,
        country_name,
        year,
        gdp_per_capita_current_usd,
        ROW_NUMBER() OVER (
            PARTITION BY country_code
            ORDER BY year DESC
        ) AS row_num
    FROM macro_panel
    WHERE gdp_per_capita_current_usd IS NOT NULL
)
SELECT country_code, country_name, year, gdp_per_capita_current_usd
FROM ranked
WHERE row_num = 1
ORDER BY gdp_per_capita_current_usd DESC;

-- Data completeness by country.
SELECT
    country_code,
    country_name,
    COUNT(*) AS calendar_years,
    COUNT(internet_users_pct) AS observed_internet_years,
    COUNT(gdp_per_capita_current_usd) AS observed_gdp_years
FROM macro_panel
GROUP BY country_code, country_name
ORDER BY country_code;
