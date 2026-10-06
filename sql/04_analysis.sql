-- 04_analysis.sql  Revenue KPIs, monthly trend, country mix, product top-N and concentration, cohort retention,
-- RFM segmentation (tie-aware R/F/M quintile scores + named segments) and returns. Valid net sales only (fact_sales).

CREATE OR REPLACE TABLE a_kpi_headline AS
WITH o AS (SELECT customer_id, COUNT(DISTINCT invoice) AS orders FROM fact_sales WHERE customer_id IS NOT NULL GROUP BY customer_id),
     rp AS (SELECT ROUND(100.0 * AVG(CASE WHEN orders >= 2 THEN 1.0 ELSE 0.0 END), 2) AS repeat_customer_pct FROM o),
     inv AS (SELECT invoice, SUM(line_revenue) AS order_value, COUNT(*) AS lines FROM fact_sales GROUP BY invoice),
     iv AS (SELECT ROUND(percentile_approx(order_value, 0.5), 2) AS median_order_value, ROUND(AVG(lines), 2) AS avg_lines_per_order FROM inv),
     r AS (SELECT ROUND(SUM(return_value), 2) AS return_value FROM cln_returns),
     g AS (SELECT ROUND(SUM(line_revenue), 2) AS gross_sales FROM cln_sales_gross),
     rv AS (SELECT ROUND(SUM(line_revenue), 2) AS reversed_value FROM cln_reversed)
SELECT ROUND(SUM(f.line_revenue), 2) AS revenue,
  MAX(g.gross_sales) AS gross_sales_before_reversals,
  MAX(rv.reversed_value) AS reversed_sales_value,
  COUNT(DISTINCT f.invoice) AS orders,
  COUNT(DISTINCT f.customer_id) AS customers,
  COUNT(*) AS order_lines,
  COUNT(DISTINCT f.stock_code) AS products,
  COUNT(DISTINCT f.country_key) AS countries,
  SUM(f.quantity) AS units,
  ROUND(SUM(f.line_revenue) / COUNT(DISTINCT f.invoice), 2) AS avg_order_value,
  MAX(iv.median_order_value) AS median_order_value,
  MAX(iv.avg_lines_per_order) AS avg_lines_per_order,
  ROUND(SUM(CASE WHEN f.customer_id IS NOT NULL THEN f.line_revenue END) / COUNT(DISTINCT f.customer_id), 2) AS revenue_per_customer,
  MAX(rp.repeat_customer_pct) AS repeat_customer_pct,
  ROUND(100.0 * SUM(CASE WHEN f.is_guest = 1 THEN f.line_revenue ELSE 0 END) / SUM(f.line_revenue), 2) AS guest_revenue_pct,
  ROUND(100.0 * SUM(CASE WHEN c.country = 'United Kingdom' THEN f.line_revenue ELSE 0 END) / SUM(f.line_revenue), 2) AS uk_revenue_pct,
  MAX(r.return_value) AS returns_value,
  ROUND(100.0 * MAX(r.return_value) / MAX(g.gross_sales), 2) AS return_rate_pct,
  CAST(MIN(f.invoice_ts) AS DATE) AS first_date, CAST(MAX(f.invoice_ts) AS DATE) AS last_date
FROM fact_sales f JOIN dim_country c ON c.country_key = f.country_key
CROSS JOIN r CROSS JOIN rp CROSS JOIN g CROSS JOIN iv CROSS JOIN rv;

-- monthly trend with new vs returning identified customers and month-over-month growth
CREATE OR REPLACE TABLE a_monthly AS
WITH m AS (
  SELECT d.year_month, ROUND(SUM(f.line_revenue), 2) AS revenue, COUNT(DISTINCT f.invoice) AS orders,
         COUNT(DISTINCT f.customer_id) AS active_customers, COUNT(DISTINCT d.date_key) AS trading_days,
         ROUND(SUM(f.line_revenue) / COUNT(DISTINCT f.invoice), 2) AS avg_order_value,
         ROUND(100.0 * SUM(CASE WHEN f.is_guest = 1 THEN f.line_revenue ELSE 0 END) / SUM(f.line_revenue), 2) AS guest_revenue_pct
  FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key GROUP BY d.year_month
), n AS (SELECT cohort_month AS year_month, COUNT(*) AS new_customers FROM dim_customer GROUP BY cohort_month)
SELECT m.*, COALESCE(n.new_customers, 0) AS new_customers, m.active_customers - COALESCE(n.new_customers, 0) AS returning_customers,
  ROUND(100.0 * (m.revenue - LAG(m.revenue) OVER (ORDER BY m.year_month)) / LAG(m.revenue) OVER (ORDER BY m.year_month), 2) AS revenue_mom_pct
FROM m LEFT JOIN n ON n.year_month = m.year_month;

-- when do orders arrive (weekday x hour)
CREATE OR REPLACE TABLE a_weekday_hour AS
SELECT d.day_of_week, d.day_name, f.invoice_hour, COUNT(DISTINCT f.invoice) AS orders, ROUND(SUM(f.line_revenue), 2) AS revenue
FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.day_of_week, d.day_name, f.invoice_hour;

-- country mix
CREATE OR REPLACE TABLE a_country AS
SELECT c.country, c.market, ROUND(SUM(f.line_revenue), 2) AS revenue,
  ROUND(100.0 * SUM(f.line_revenue) / SUM(SUM(f.line_revenue)) OVER (), 2) AS revenue_share_pct,
  COUNT(DISTINCT f.invoice) AS orders, COUNT(DISTINCT f.customer_id) AS customers,
  ROUND(SUM(f.line_revenue) / COUNT(DISTINCT f.invoice), 2) AS avg_order_value,
  ROUND(SUM(f.line_revenue) / NULLIF(COUNT(DISTINCT f.customer_id), 0), 2) AS revenue_per_customer
FROM fact_sales f JOIN dim_country c ON c.country_key = f.country_key
GROUP BY c.country, c.market;

-- product revenue (all products) and concentration
CREATE OR REPLACE TABLE a_products AS
SELECT p.stock_code, p.description, ROUND(SUM(f.line_revenue), 2) AS revenue,
  ROUND(100.0 * SUM(f.line_revenue) / SUM(SUM(f.line_revenue)) OVER (), 3) AS revenue_share_pct,
  SUM(f.quantity) AS units, COUNT(DISTINCT f.invoice) AS orders, COUNT(DISTINCT f.customer_id) AS customers,
  RANK() OVER (ORDER BY SUM(f.line_revenue) DESC) AS revenue_rank,
  RANK() OVER (ORDER BY SUM(f.quantity) DESC) AS units_rank
FROM fact_sales f JOIN dim_product p ON p.stock_code = f.stock_code
GROUP BY p.stock_code, p.description;

CREATE OR REPLACE TABLE a_products_top20 AS
SELECT * FROM a_products WHERE revenue_rank <= 20;

CREATE OR REPLACE TABLE a_product_concentration AS
WITH r AS (SELECT stock_code, revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC, stock_code) AS rk,
                  COUNT(*) OVER () AS n_products, SUM(revenue) OVER () AS total FROM a_products)
SELECT MAX(n_products) AS products,
  ROUND(100.0 * SUM(CASE WHEN rk <= 10 THEN revenue ELSE 0 END) / MAX(total), 2) AS top10_share_pct,
  ROUND(100.0 * SUM(CASE WHEN rk <= 100 THEN revenue ELSE 0 END) / MAX(total), 2) AS top100_share_pct,
  ROUND(100.0 * SUM(CASE WHEN rk <= 0.2 * n_products THEN revenue ELSE 0 END) / MAX(total), 2) AS top20pct_products_share_pct,
  SUM(CASE WHEN rk <= 0.5 * n_products THEN 0 ELSE 1 END) AS bottom_half_products,
  ROUND(100.0 * SUM(CASE WHEN rk > 0.5 * n_products THEN revenue ELSE 0 END) / MAX(total), 2) AS bottom50pct_products_share_pct
FROM r;

-- Pareto curve: cumulative revenue share after the top p% of products (p = 5, 10, ..., 100)
CREATE OR REPLACE TABLE a_product_pareto AS
WITH r AS (SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC, stock_code) AS rk,
                  COUNT(*) OVER () AS n, SUM(revenue) OVER () AS total FROM a_products),
p AS (SELECT DISTINCT CAST(5 * CEIL(20.0 * rk / n) AS INT) AS pct_products FROM r)
SELECT p.pct_products, ROUND(100.0 * SUM(r.revenue) / MAX(r.total), 2) AS cum_revenue_share_pct
FROM p JOIN r ON r.rk <= p.pct_products * r.n / 100.0
GROUP BY p.pct_products;

-- RFM (identified customers; snapshot = day after the last invoice). Scores are tie-aware quintiles:
-- score = 1 + floor(5 * (rank - 1) / n) with RANK(), so equal values always share a score
-- (all one-order customers get F = 1 instead of being split arbitrarily, as NTILE would do).
CREATE OR REPLACE TABLE a_rfm_customers AS
WITH snap AS (SELECT unix_date(CAST(MAX(invoice_ts) AS DATE)) + 1 AS snap_day FROM fact_sales),
base AS (
  SELECT f.customer_id, MAX(s.snap_day) - unix_date(CAST(MAX(f.invoice_ts) AS DATE)) AS recency_days,
         COUNT(DISTINCT f.invoice) AS frequency, ROUND(SUM(f.line_revenue), 2) AS monetary,
         CAST(MIN(f.invoice_ts) AS DATE) AS first_purchase, CAST(MAX(f.invoice_ts) AS DATE) AS last_purchase
  FROM fact_sales f CROSS JOIN snap s WHERE f.customer_id IS NOT NULL GROUP BY f.customer_id
), sc AS (
  SELECT *,
    CAST(1 + FLOOR(5.0 * (RANK() OVER (ORDER BY recency_days DESC) - 1) / COUNT(*) OVER ()) AS INT) AS r_score,
    CAST(1 + FLOOR(5.0 * (RANK() OVER (ORDER BY frequency) - 1) / COUNT(*) OVER ()) AS INT) AS f_score,
    CAST(1 + FLOOR(5.0 * (RANK() OVER (ORDER BY monetary) - 1) / COUNT(*) OVER ()) AS INT) AS m_score
  FROM base
)
SELECT *, CONCAT(CAST(r_score AS STRING), CAST(f_score AS STRING), CAST(m_score AS STRING)) AS rfm_code,
  r_score + f_score + m_score AS rfm_total,
  CASE WHEN r_score >= 4 AND f_score >= 4                    THEN '01 Champions'
       WHEN r_score >= 3 AND f_score >= 3                    THEN '02 Loyal'
       WHEN r_score >= 4 AND f_score = 2                     THEN '03 Potential loyalist'
       WHEN r_score >= 4 AND f_score = 1                     THEN '04 New customers'
       WHEN r_score = 3                                      THEN '05 Needs attention'
       WHEN f_score >= 4 AND m_score >= 4                    THEN '06 Cannot lose them'
       WHEN f_score >= 3                                     THEN '07 At risk'
       WHEN r_score = 2                                      THEN '08 Hibernating'
       ELSE '09 Lost' END AS segment
FROM sc;

CREATE OR REPLACE TABLE a_rfm_segments AS
SELECT segment, COUNT(*) AS customers, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS customer_share_pct,
  ROUND(SUM(monetary), 2) AS revenue, ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS revenue_share_pct,
  ROUND(AVG(recency_days), 1) AS avg_recency_days, ROUND(AVG(frequency), 2) AS avg_frequency, ROUND(AVG(monetary), 2) AS avg_monetary,
  ROUND(percentile_approx(monetary, 0.5), 2) AS median_monetary
FROM a_rfm_customers GROUP BY segment;

-- R x F grid (5 x 5): customers and average spend per cell
CREATE OR REPLACE TABLE a_rfm_grid AS
SELECT r_score, f_score, COUNT(*) AS customers, ROUND(AVG(monetary), 2) AS avg_monetary, ROUND(SUM(monetary), 2) AS revenue
FROM a_rfm_customers GROUP BY r_score, f_score;

-- the value range behind every score (what a "5" actually means)
CREATE OR REPLACE TABLE a_rfm_score_ranges AS
SELECT 'R recency_days' AS metric, r_score AS score, COUNT(*) AS customers, MIN(recency_days) AS min_value, MAX(recency_days) AS max_value FROM a_rfm_customers GROUP BY r_score
UNION ALL SELECT 'F frequency (orders)', f_score, COUNT(*), MIN(frequency), MAX(frequency) FROM a_rfm_customers GROUP BY f_score
UNION ALL SELECT 'M monetary (GBP)', m_score, COUNT(*), MIN(monetary), MAX(monetary) FROM a_rfm_customers GROUP BY m_score;

-- cohort retention: share of each first-purchase cohort active N months later
CREATE OR REPLACE TABLE a_cohort_retention AS
WITH act AS (
  SELECT DISTINCT f.customer_id, year(f.invoice_ts) * 12 + month(f.invoice_ts) AS m_idx FROM fact_sales f WHERE f.customer_id IS NOT NULL
), c AS (
  SELECT customer_id, cohort_month, CAST(cohort_month / 100 AS INT) * 12 + cohort_month % 100 AS c_idx FROM dim_customer
), sz AS (SELECT cohort_month, COUNT(*) AS cohort_size FROM dim_customer GROUP BY cohort_month)
SELECT c.cohort_month, a.m_idx - c.c_idx AS months_since, COUNT(*) AS active_customers, MAX(sz.cohort_size) AS cohort_size,
  ROUND(100.0 * COUNT(*) / MAX(sz.cohort_size), 2) AS retention_pct
FROM act a JOIN c ON c.customer_id = a.customer_id JOIN sz ON sz.cohort_month = c.cohort_month
GROUP BY c.cohort_month, a.m_idx - c.c_idx;

-- size-weighted average retention curve over the cohorts that can be observed at each offset
CREATE OR REPLACE TABLE a_retention_curve AS
WITH mx AS (SELECT MAX(year(invoice_ts) * 12 + month(invoice_ts)) AS max_idx FROM fact_sales),
sz AS (SELECT cohort_month, CAST(cohort_month / 100 AS INT) * 12 + cohort_month % 100 AS c_idx, COUNT(*) AS cohort_size
       FROM dim_customer GROUP BY cohort_month),
offs AS (SELECT DISTINCT months_since FROM a_cohort_retention),
elig AS (SELECT o.months_since, SUM(s.cohort_size) AS eligible_customers, COUNT(*) AS cohorts
         FROM offs o CROSS JOIN sz s CROSS JOIN mx WHERE s.c_idx + o.months_since <= mx.max_idx GROUP BY o.months_since),
act AS (SELECT months_since, SUM(active_customers) AS active_customers FROM a_cohort_retention GROUP BY months_since),
exd AS (SELECT o.months_since, SUM(r.active_customers) AS active_ex_first, SUM(s.cohort_size) AS eligible_ex_first
        FROM offs o JOIN a_cohort_retention r ON r.months_since = o.months_since JOIN sz s ON s.cohort_month = r.cohort_month
        WHERE r.cohort_month <> (SELECT MIN(cohort_month) FROM dim_customer) GROUP BY o.months_since),
eex AS (SELECT o.months_since, SUM(s.cohort_size) AS eligible_ex_first
        FROM offs o CROSS JOIN sz s CROSS JOIN mx WHERE s.c_idx + o.months_since <= mx.max_idx
          AND s.cohort_month <> (SELECT MIN(cohort_month) FROM dim_customer) GROUP BY o.months_since)
SELECT e.months_since, e.cohorts, e.eligible_customers, a.active_customers,
  ROUND(100.0 * a.active_customers / e.eligible_customers, 2) AS retention_pct,
  ROUND(100.0 * x.active_ex_first / NULLIF(ee.eligible_ex_first, 0), 2) AS retention_ex_first_cohort_pct
FROM elig e JOIN act a ON a.months_since = e.months_since
LEFT JOIN exd x ON x.months_since = e.months_since LEFT JOIN eex ee ON ee.months_since = e.months_since;

-- returns (credit notes) by product
CREATE OR REPLACE TABLE a_returns_products AS
SELECT r.stock_code, COALESCE(p.description, MAX(r.description)) AS description, ROUND(SUM(r.return_value), 2) AS return_value,
  SUM(r.quantity_returned) AS units_returned, COUNT(DISTINCT r.invoice) AS credit_notes
FROM cln_returns r LEFT JOIN dim_product p ON p.stock_code = r.stock_code
GROUP BY r.stock_code, p.description;

-- the largest single lines kept after reversal netting (outlier review list)
CREATE OR REPLACE TABLE a_extreme_lines AS
SELECT f.invoice, CAST(f.invoice_ts AS DATE) AS invoice_date, f.customer_id, f.stock_code, p.description, c.country,
       f.quantity, f.unit_price, f.line_revenue
FROM fact_sales f JOIN dim_product p ON p.stock_code = f.stock_code JOIN dim_country c ON c.country_key = f.country_key
WHERE f.is_extreme_line = 1 ORDER BY f.line_revenue DESC LIMIT 25;
