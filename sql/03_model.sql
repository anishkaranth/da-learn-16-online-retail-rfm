-- 03_model.sql  Star schema: fact_sales (one row per net sales line) + dim_customer, dim_product, dim_country, dim_date.

CREATE OR REPLACE TABLE dim_country AS
SELECT ROW_NUMBER() OVER (ORDER BY country) AS country_key, country,
       CASE WHEN country = 'United Kingdom' THEN 'Domestic (UK)' ELSE 'International' END AS market
FROM (SELECT DISTINCT country FROM cln_sales) c;

-- one description per stock code: the most frequent one (ties -> alphabetical)
CREATE OR REPLACE TABLE dim_product AS
WITH d AS (
  SELECT stock_code, description, COUNT(*) AS n,
         ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC, description) AS rk
  FROM cln_sales WHERE description IS NOT NULL AND description <> '' GROUP BY stock_code, description
)
SELECT s.stock_code, COALESCE(d.description, 'UNKNOWN') AS description, s.avg_unit_price, s.first_sold, s.last_sold
FROM (SELECT stock_code, ROUND(AVG(unit_price), 2) AS avg_unit_price, CAST(MIN(invoice_ts) AS DATE) AS first_sold,
             CAST(MAX(invoice_ts) AS DATE) AS last_sold
      FROM cln_sales GROUP BY stock_code) s
LEFT JOIN d ON d.stock_code = s.stock_code AND d.rk = 1;

-- identified customers: home country = country of the first purchase; cohort = month of the first purchase
CREATE OR REPLACE TABLE dim_customer AS
WITH f AS (
  SELECT customer_id, country, invoice_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY invoice_ts, invoice, stock_code) AS rk
  FROM cln_sales WHERE customer_id IS NOT NULL
), nc AS (SELECT customer_id, COUNT(DISTINCT country) AS countries FROM cln_sales WHERE customer_id IS NOT NULL GROUP BY customer_id)
SELECT f.customer_id, f.country AS home_country, CAST(f.invoice_ts AS DATE) AS first_purchase_date,
       CAST(year(f.invoice_ts) * 100 + month(f.invoice_ts) AS INT) AS cohort_month, nc.countries AS countries_used
FROM f JOIN nc ON nc.customer_id = f.customer_id WHERE f.rk = 1;

CREATE OR REPLACE TABLE dim_date AS
SELECT DISTINCT CAST(year(invoice_ts) * 10000 + month(invoice_ts) * 100 + day(invoice_ts) AS INT) AS date_key,
  CAST(invoice_ts AS DATE) AS invoice_date, year(invoice_ts) AS year, month(invoice_ts) AS month,
  CAST(year(invoice_ts) * 100 + month(invoice_ts) AS INT) AS year_month, dayofweek(invoice_ts) AS day_of_week,
  CASE dayofweek(invoice_ts) WHEN 1 THEN 'Sun' WHEN 2 THEN 'Mon' WHEN 3 THEN 'Tue' WHEN 4 THEN 'Wed' WHEN 5 THEN 'Thu'
                             WHEN 6 THEN 'Fri' ELSE 'Sat' END AS day_name
FROM cln_sales;

CREATE OR REPLACE TABLE fact_sales AS
SELECT s.invoice,
  CAST(year(s.invoice_ts) * 10000 + month(s.invoice_ts) * 100 + day(s.invoice_ts) AS INT) AS date_key,
  s.invoice_ts, hour(s.invoice_ts) AS invoice_hour, s.customer_id, s.stock_code, c.country_key,
  s.quantity, s.unit_price, s.line_revenue,
  CASE WHEN s.customer_id IS NULL THEN 1 ELSE 0 END AS is_guest,
  s.is_qty_outlier, s.is_revenue_outlier, s.is_extreme_line
FROM cln_sales s JOIN dim_country c ON c.country = s.country;
