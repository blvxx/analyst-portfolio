-- Run against outputs/cis_macro.duckdb.

-- Country-year internet penetration and lagged annual change (percentage points).
SELECT
    country_code,
    country_name,
    year,
    internet_users_pct,
    internet_users_pct - LAG(internet_users_pct) OVER (
        PARTITION BY country_code ORDER BY year
    ) AS internet_penetration_yoy_pp
FROM macro_panel
WHERE internet_users_pct IS NOT NULL
ORDER BY country_code, year;

-- Latest available GDP per capita for each country.
WITH ranked AS (
    SELECT
        country_code, country_name, year, gdp_per_capita_current_usd,
        ROW_NUMBER() OVER (PARTITION BY country_code ORDER BY year DESC) AS row_num
    FROM macro_panel
    WHERE gdp_per_capita_current_usd IS NOT NULL
)
SELECT country_code, country_name, year, gdp_per_capita_current_usd
FROM ranked
WHERE row_num = 1
ORDER BY gdp_per_capita_current_usd DESC;

-- Completeness by country: never hide gaps behind interpolation.
SELECT
    country_code,
    country_name,
    COUNT(*) AS calendar_years,
    COUNT(internet_users_pct) AS observed_internet_years,
    COUNT(gdp_per_capita_current_usd) AS observed_gdp_years,
    COUNT(inflation_cpi_annual_pct) AS observed_inflation_years,
    COUNT(unemployment_ilo_pct) AS observed_unemployment_years
FROM macro_panel
GROUP BY country_code, country_name
ORDER BY country_code;

-- Rolling three-year average of internet penetration, using observed values only.
SELECT
    country_code,
    country_name,
    year,
    internet_users_pct,
    AVG(internet_users_pct) OVER (
        PARTITION BY country_code
        ORDER BY year
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_3_observation_avg
FROM macro_panel
WHERE internet_users_pct IS NOT NULL
ORDER BY country_code, year;
