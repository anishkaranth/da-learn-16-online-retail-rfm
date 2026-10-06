-- 05_quality_checks.sql  Data-quality evidence (Spark SQL dialect): before/after counts, null rates, issue counts, hard assertions.

CREATE OR REPLACE TABLE dq_row_counts AS
SELECT 'raw invoice lines (stg_retail)' AS entity, (SELECT COUNT(*) FROM stg_retail) AS row_count, 'invoice line' AS grain
UNION ALL SELECT 'after removing exact duplicates', (SELECT COUNT(*) FROM cln_lines_flagged WHERE dq_duplicate = 0), 'invoice line'
UNION ALL SELECT 'gross sales lines (before reversals)', (SELECT COUNT(*) FROM cln_sales_gross), 'invoice line'
UNION ALL SELECT 'net sales lines (cln_sales = fact_sales)', (SELECT COUNT(*) FROM cln_sales), 'invoice line'
UNION ALL SELECT 'net sales lines with a CustomerID', (SELECT COUNT(*) FROM cln_sales WHERE customer_id IS NOT NULL), 'invoice line'
UNION ALL SELECT 'returns (credit-note product lines)', (SELECT COUNT(*) FROM cln_returns), 'invoice line'
UNION ALL SELECT 'raw invoices', (SELECT COUNT(DISTINCT InvoiceNo) FROM stg_retail), 'invoice'
UNION ALL SELECT 'clean sales orders', (SELECT COUNT(DISTINCT invoice) FROM fact_sales), 'invoice'
UNION ALL SELECT 'raw distinct CustomerID', (SELECT COUNT(DISTINCT CustomerID) FROM stg_retail), 'customer'
UNION ALL SELECT 'dim_customer (customers with a net sale)', (SELECT COUNT(*) FROM dim_customer), 'customer'
UNION ALL SELECT 'dim_product', (SELECT COUNT(*) FROM dim_product), 'stock code'
UNION ALL SELECT 'dim_country', (SELECT COUNT(*) FROM dim_country), 'country'
UNION ALL SELECT 'dim_date', (SELECT COUNT(*) FROM dim_date), 'trading day';

CREATE OR REPLACE TABLE dq_null_rates AS
SELECT 'CustomerID' AS column_name,
  (SELECT ROUND(100.0 * SUM(CASE WHEN CustomerID IS NULL OR trim(CustomerID) = '' THEN 1 ELSE 0 END) / COUNT(*), 3) FROM stg_retail) AS raw_missing_pct,
  (SELECT ROUND(100.0 * SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) / COUNT(*), 3) FROM cln_sales) AS clean_missing_pct,
  'kept as guest revenue (is_guest = 1); excluded from RFM, cohorts and customer counts' AS treatment
UNION ALL SELECT 'Description',
  (SELECT ROUND(100.0 * SUM(CASE WHEN Description IS NULL OR trim(Description) = '' THEN 1 ELSE 0 END) / COUNT(*), 3) FROM stg_retail),
  (SELECT ROUND(100.0 * SUM(CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END) / COUNT(*), 3) FROM cln_sales),
  'all missing descriptions sit on zero-price lines, which are removed; dim_product uses the most frequent description per code'
UNION ALL SELECT 'any other column',
  (SELECT ROUND(100.0 * SUM(CASE WHEN InvoiceNo IS NULL OR StockCode IS NULL OR Quantity IS NULL OR InvoiceDate IS NULL
                              OR UnitPrice IS NULL OR Country IS NULL THEN 1 ELSE 0 END) / COUNT(*), 3) FROM stg_retail),
  (SELECT ROUND(100.0 * SUM(CASE WHEN invoice IS NULL OR stock_code IS NULL OR quantity IS NULL OR invoice_ts IS NULL
                              OR unit_price IS NULL OR country IS NULL THEN 1 ELSE 0 END) / COUNT(*), 3) FROM cln_sales),
  'no other missing values';

-- flags overlap, so each count is "rows carrying this flag"
CREATE OR REPLACE TABLE dq_issues AS
SELECT 'exact duplicate lines (removed)' AS check_name, (SELECT SUM(dq_duplicate) FROM cln_lines_flagged) AS affected_rows
UNION ALL SELECT 'cancellation lines, invoice C... (moved to returns)', (SELECT SUM(is_cancellation) FROM cln_lines_flagged)
UNION ALL SELECT 'bad-debt adjustments, invoice A... (removed)', (SELECT SUM(is_adjustment) FROM cln_lines_flagged)
UNION ALL SELECT 'non-product codes: postage, fees, manual, discounts, samples, vouchers (removed)', (SELECT SUM(is_non_product) FROM cln_lines_flagged)
UNION ALL SELECT 'unit price <= 0 (removed)', (SELECT SUM(dq_bad_price) FROM cln_lines_flagged)
UNION ALL SELECT 'quantity <= 0 on a non-C invoice: stock write-offs (removed)', (SELECT SUM(dq_bad_quantity) FROM cln_lines_flagged)
UNION ALL SELECT 'sales lines exactly reversed by a credit note (removed from net sales)', (SELECT COUNT(*) FROM cln_reversed)
UNION ALL SELECT 'missing description (all lines)', (SELECT SUM(dq_missing_description) FROM cln_lines_flagged)
UNION ALL SELECT 'missing CustomerID (all lines)', (SELECT SUM(dq_missing_customer) FROM cln_lines_flagged)
UNION ALL SELECT 'net sales lines without CustomerID (kept as guest)', (SELECT COUNT(*) FROM cln_sales WHERE customer_id IS NULL)
UNION ALL SELECT 'country labels standardised (EIRE, RSA, USA, Unspecified)', (SELECT COUNT(*) FROM cln_lines_flagged WHERE country <> country_raw)
UNION ALL SELECT 'quantity above Q3 + 1.5 IQR (flagged, kept)', (SELECT SUM(is_qty_outlier) FROM cln_sales)
UNION ALL SELECT 'line revenue above Q3 + 1.5 IQR (flagged, kept)', (SELECT SUM(is_revenue_outlier) FROM cln_sales)
UNION ALL SELECT 'line revenue above the 99.9th percentile (flagged, kept; see a_extreme_lines)', (SELECT SUM(is_extreme_line) FROM cln_sales)
UNION ALL SELECT 'total raw lines not in net sales', (SELECT COUNT(*) FROM stg_retail) - (SELECT COUNT(*) FROM cln_sales);

CREATE OR REPLACE TABLE dq_assertions AS
WITH c AS (
  SELECT 'raw rows = flagged rows (nothing dropped while typing)' AS check_name,
         (SELECT ABS((SELECT COUNT(*) FROM stg_retail) - (SELECT COUNT(*) FROM cln_lines_flagged))) AS failed_rows
  UNION ALL SELECT 'every InvoiceDate parsed', (SELECT SUM(dq_bad_date) FROM cln_lines_flagged)
  UNION ALL SELECT 'every Quantity and UnitPrice parsed', (SELECT COUNT(*) FROM cln_lines_flagged WHERE quantity IS NULL OR unit_price IS NULL)
  UNION ALL SELECT 'invoice codes are 6 digits, C+6 or A+6',
         (SELECT COUNT(*) FROM cln_lines_flagged WHERE NOT (length(invoice) = 6 OR (length(invoice) = 7 AND (invoice LIKE 'C%' OR invoice LIKE 'A%'))))
  UNION ALL SELECT 'no exact duplicates left in net sales',
         (SELECT COUNT(*) - COUNT(DISTINCT CONCAT_WS('|', invoice, stock_code, COALESCE(description, ''), CAST(quantity AS STRING),
                 CAST(invoice_ts AS STRING), CAST(unit_price AS STRING), COALESCE(CAST(customer_id AS STRING), ''), country)) FROM cln_sales)
  UNION ALL SELECT 'line accounting: gross = net + reversed', (SELECT ABS((SELECT COUNT(*) FROM cln_sales_gross) - (SELECT COUNT(*) FROM cln_sales) - (SELECT COUNT(*) FROM cln_reversed)))
  UNION ALL SELECT 'every clean line is in fact_sales', (SELECT ABS((SELECT COUNT(*) FROM cln_sales) - (SELECT COUNT(*) FROM fact_sales)))
  UNION ALL SELECT 'no cancellations or adjustments in fact', (SELECT COUNT(*) FROM fact_sales WHERE invoice LIKE 'C%' OR invoice LIKE 'A%')
  UNION ALL SELECT 'no non-product codes in fact', (SELECT COUNT(*) FROM fact_sales WHERE stock_code IN ('POST', 'DOT', 'M', 'C2', 'D', 'S', 'B', 'BANK CHARGES', 'AMAZONFEE', 'PADS', 'CRUK'))
  UNION ALL SELECT 'positive quantity and price in fact', (SELECT COUNT(*) FROM fact_sales WHERE quantity <= 0 OR unit_price <= 0)
  UNION ALL SELECT 'line_revenue = round(quantity x price, 2)', (SELECT COUNT(*) FROM fact_sales WHERE ABS(line_revenue - ROUND(quantity * unit_price, 2)) > 0.005)
  UNION ALL SELECT 'dates inside 2010-12-01 .. 2011-12-09', (SELECT COUNT(*) FROM fact_sales WHERE invoice_ts < TIMESTAMP '2010-12-01 00:00:00' OR invoice_ts >= TIMESTAMP '2011-12-10 00:00:00')
  UNION ALL SELECT 'product exists in dim_product', (SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_product p ON p.stock_code = f.stock_code WHERE p.stock_code IS NULL)
  UNION ALL SELECT 'customer exists in dim_customer', (SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_customer c ON c.customer_id = f.customer_id WHERE f.customer_id IS NOT NULL AND c.customer_id IS NULL)
  UNION ALL SELECT 'country exists in dim_country', (SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_country c ON c.country_key = f.country_key WHERE c.country_key IS NULL)
  UNION ALL SELECT 'date exists in dim_date', (SELECT COUNT(*) FROM fact_sales f LEFT JOIN dim_date d ON d.date_key = f.date_key WHERE d.date_key IS NULL)
  UNION ALL SELECT 'dimension keys unique (product, customer, country, date)',
         (SELECT (SELECT COUNT(*) - COUNT(DISTINCT stock_code) FROM dim_product) + (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM dim_customer)
               + (SELECT COUNT(*) - COUNT(DISTINCT country) FROM dim_country) + (SELECT COUNT(*) - COUNT(DISTINCT date_key) FROM dim_date))
  UNION ALL SELECT 'each credit note reverses at most one sales line', (SELECT COUNT(*) - COUNT(DISTINCT CONCAT_WS('|', credit_invoice, stock_code, CAST(quantity AS STRING), CAST(unit_price AS STRING))) FROM cln_reversed)
  UNION ALL SELECT 'reversals happen after the sale', (SELECT COUNT(*) FROM cln_reversed WHERE credit_ts < invoice_ts)
  UNION ALL SELECT 'returns have positive quantity and value', (SELECT COUNT(*) FROM cln_returns WHERE quantity_returned <= 0 OR return_value <= 0)
  UNION ALL SELECT 'RFM covers every identified customer once', (SELECT ABS((SELECT COUNT(DISTINCT customer_id) FROM a_rfm_customers) - (SELECT COUNT(*) FROM dim_customer)) + (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM a_rfm_customers))
  UNION ALL SELECT 'R, F and M scores all within 1..5', (SELECT COUNT(*) FROM a_rfm_customers WHERE r_score NOT BETWEEN 1 AND 5 OR f_score NOT BETWEEN 1 AND 5 OR m_score NOT BETWEEN 1 AND 5)
  UNION ALL SELECT 'tie-aware scores: equal values share a score', (SELECT (SELECT COUNT(*) FROM (SELECT frequency FROM a_rfm_customers GROUP BY frequency HAVING COUNT(DISTINCT f_score) > 1) x)
                                                                         + (SELECT COUNT(*) FROM (SELECT recency_days FROM a_rfm_customers GROUP BY recency_days HAVING COUNT(DISTINCT r_score) > 1) y))
  UNION ALL SELECT 'every customer has a named segment', (SELECT COUNT(*) FROM a_rfm_customers WHERE segment IS NULL)
  UNION ALL SELECT 'segment revenue sums to identified-customer revenue', (SELECT CASE WHEN ABS((SELECT SUM(revenue) FROM a_rfm_segments) - (SELECT SUM(line_revenue) FROM fact_sales WHERE customer_id IS NOT NULL)) < 1 THEN 0 ELSE 1 END)
  UNION ALL SELECT 'segment shares sum to 100% (+/- 0.1)', (SELECT CASE WHEN ABS(SUM(customer_share_pct) - 100) < 0.1 AND ABS(SUM(revenue_share_pct) - 100) < 0.1 THEN 0 ELSE 1 END FROM a_rfm_segments)
  UNION ALL SELECT 'month-0 retention is 100% for every cohort', (SELECT COUNT(*) FROM a_cohort_retention WHERE months_since = 0 AND retention_pct <> 100)
  UNION ALL SELECT 'cohort sizes sum to dim_customer', (SELECT ABS((SELECT SUM(active_customers) FROM a_cohort_retention WHERE months_since = 0) - (SELECT COUNT(*) FROM dim_customer)))
  UNION ALL SELECT 'monthly revenue sums to total revenue', (SELECT CASE WHEN ABS((SELECT SUM(revenue) FROM a_monthly) - (SELECT revenue FROM a_kpi_headline)) < 1 THEN 0 ELSE 1 END)
  UNION ALL SELECT 'country revenue sums to total revenue', (SELECT CASE WHEN ABS((SELECT SUM(revenue) FROM a_country) - (SELECT revenue FROM a_kpi_headline)) < 1 THEN 0 ELSE 1 END)
  UNION ALL SELECT 'product revenue sums to total revenue', (SELECT CASE WHEN ABS((SELECT SUM(revenue) FROM a_products) - (SELECT revenue FROM a_kpi_headline)) < 1 THEN 0 ELSE 1 END)
)
SELECT check_name, failed_rows, CASE WHEN failed_rows = 0 THEN 'PASS' ELSE 'FAIL' END AS status FROM c;
