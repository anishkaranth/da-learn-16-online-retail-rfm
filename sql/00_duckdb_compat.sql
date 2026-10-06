-- 00_duckdb_compat.sql  (DuckDB ONLY - skip on Databricks, where these functions are built in)
CREATE OR REPLACE MACRO to_date(s) AS TRY_CAST(s AS DATE);
CREATE OR REPLACE MACRO percentile_approx(x, p) AS quantile_cont(x, p);
CREATE OR REPLACE MACRO dayofweek(d) AS (isodow(CAST(d AS DATE)) % 7) + 1;
CREATE OR REPLACE MACRO unix_date(d) AS date_diff('day', DATE '1970-01-01', CAST(d AS DATE));
