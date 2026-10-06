-- 02_cleaning.sql  (Spark SQL dialect; DuckDB via the 00 shims)
-- typed + standardised lines -> exact-duplicate detection -> quality flags -> cln_sales_gross -> reversal netting -> cln_sales,
-- plus cln_returns (credit notes) and line-level outlier flags (flagged, kept).
-- Invoice codes: 6 digits = sale, 'C' prefix = cancellation / credit note, 'A' prefix = bad-debt adjustment.

CREATE OR REPLACE TABLE cln_lines_flagged AS
WITH t AS (
  SELECT
    upper(trim(InvoiceNo))                            AS invoice,
    upper(trim(StockCode))                            AS stock_code,
    upper(trim(Description)) AS description,
    TRY_CAST(Quantity AS INT)                         AS quantity,
    TRY_CAST(InvoiceDate AS TIMESTAMP)                AS invoice_ts,
    TRY_CAST(UnitPrice AS DECIMAL(12, 3))             AS unit_price,   -- max 3 decimals in the source; DECIMAL keeps sums exact
    TRY_CAST(CustomerID AS INT)                       AS customer_id,
    trim(Country)                                     AS country_raw,
    CASE trim(Country) WHEN 'EIRE' THEN 'Ireland' WHEN 'RSA' THEN 'South Africa' WHEN 'USA' THEN 'United States'
                       WHEN 'Unspecified' THEN 'Unknown' ELSE trim(Country) END AS country
  FROM stg_retail
), d AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY invoice, stock_code, description, quantity, invoice_ts, unit_price, customer_id, country
                               ORDER BY invoice) AS dup_rank
  FROM t
)
SELECT invoice, stock_code, description, quantity, invoice_ts, unit_price, customer_id, country_raw, country,
  CASE WHEN dup_rank > 1 THEN 1 ELSE 0 END                                              AS dq_duplicate,
  CASE WHEN invoice LIKE 'C%' THEN 1 ELSE 0 END                                         AS is_cancellation,
  CASE WHEN invoice LIKE 'A%' THEN 1 ELSE 0 END                                         AS is_adjustment,
  CASE WHEN stock_code IN ('POST', 'DOT', 'M', 'C2', 'D', 'S', 'B', 'BANK CHARGES', 'AMAZONFEE', 'PADS', 'CRUK')
         OR stock_code LIKE 'GIFT!_%' ESCAPE '!' THEN 1 ELSE 0 END                     AS is_non_product,
  CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END                                       AS dq_missing_customer,
  CASE WHEN unit_price IS NULL OR unit_price <= 0 THEN 1 ELSE 0 END                     AS dq_bad_price,
  CASE WHEN quantity IS NULL OR (quantity <= 0 AND invoice NOT LIKE 'C%') THEN 1 ELSE 0 END AS dq_bad_quantity,
  CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END                   AS dq_missing_description,
  CASE WHEN invoice_ts IS NULL THEN 1 ELSE 0 END                                        AS dq_bad_date
FROM d;

-- valid product sales (gross): not duplicated, not cancelled / adjusted, a real product, positive quantity and price, valid date
CREATE OR REPLACE TABLE cln_sales_gross AS
SELECT invoice, stock_code, description, quantity, invoice_ts, unit_price, customer_id, country,
       CAST(ROUND(quantity * unit_price, 2) AS DECIMAL(18, 2)) AS line_revenue
FROM cln_lines_flagged
WHERE dq_duplicate = 0 AND is_cancellation = 0 AND is_adjustment = 0 AND is_non_product = 0
  AND dq_bad_price = 0 AND dq_bad_quantity = 0 AND dq_bad_date = 0;

-- product returns / credit notes (negative quantities on 'C' invoices, real products only)
CREATE OR REPLACE TABLE cln_returns AS
SELECT invoice, stock_code, description, -quantity AS quantity_returned, invoice_ts, unit_price, customer_id, country,
       CAST(ROUND(-quantity * unit_price, 2) AS DECIMAL(18, 2)) AS return_value
FROM cln_lines_flagged
WHERE dq_duplicate = 0 AND is_cancellation = 1 AND is_non_product = 0 AND quantity < 0 AND unit_price > 0;

-- sales lines exactly reversed by a later credit note (same customer, stock code, quantity and price), paired 1:1 in time
-- order (k-th sale with the k-th credit note); a pair only counts when the credit note is not earlier than the sale
-- (credit notes for goods bought before Dec 2010 stay as plain returns). This removes order-entry mistakes such as the 80,995 x PAPER CRAFT LITTLE BIRDIE line cancelled 12 minutes later.
CREATE OR REPLACE TABLE cln_reversed AS
WITH s AS (
  SELECT invoice, stock_code, quantity, unit_price, customer_id, invoice_ts, line_revenue,
         ROW_NUMBER() OVER (PARTITION BY customer_id, stock_code, quantity, unit_price ORDER BY invoice_ts, invoice) AS k
  FROM cln_sales_gross WHERE customer_id IS NOT NULL
), c AS (
  SELECT invoice AS credit_invoice, stock_code, quantity_returned AS quantity, unit_price, customer_id, invoice_ts AS credit_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id, stock_code, quantity_returned, unit_price ORDER BY invoice_ts, invoice) AS k
  FROM cln_returns WHERE customer_id IS NOT NULL
)
SELECT s.invoice, s.stock_code, s.quantity, s.unit_price, s.customer_id, s.invoice_ts, s.line_revenue, c.credit_invoice, c.credit_ts
FROM s JOIN c ON c.customer_id = s.customer_id AND c.stock_code = s.stock_code AND c.quantity = s.quantity
             AND c.unit_price = s.unit_price AND c.k = s.k
WHERE c.credit_ts >= s.invoice_ts;

-- net sales = gross minus the exactly reversed lines; outlier flags are added here (flagged, kept)
CREATE OR REPLACE TABLE cln_sales AS
WITH n AS (
  SELECT g.* FROM cln_sales_gross g
  LEFT JOIN (SELECT DISTINCT invoice, stock_code, quantity, unit_price, customer_id FROM cln_reversed) r
    ON r.invoice = g.invoice AND r.stock_code = g.stock_code AND r.quantity = g.quantity AND r.unit_price = g.unit_price
   AND r.customer_id = g.customer_id
  WHERE r.invoice IS NULL
), q AS (
  SELECT percentile_approx(quantity, 0.25) AS q1, percentile_approx(quantity, 0.75) AS q3,
         percentile_approx(line_revenue, 0.25) AS r1, percentile_approx(line_revenue, 0.75) AS r3,
         percentile_approx(line_revenue, 0.999) AS r999
  FROM n
)
SELECT n.*,
  CASE WHEN n.quantity > q.q3 + 1.5 * (q.q3 - q.q1) THEN 1 ELSE 0 END          AS is_qty_outlier,
  CASE WHEN n.line_revenue > q.r3 + 1.5 * (q.r3 - q.r1) THEN 1 ELSE 0 END      AS is_revenue_outlier,
  CASE WHEN n.line_revenue > q.r999 THEN 1 ELSE 0 END                          AS is_extreme_line
FROM n CROSS JOIN q;
