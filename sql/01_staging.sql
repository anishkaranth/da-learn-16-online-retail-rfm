-- 01_staging.sql  Land the UCI Online Retail CSV exactly as text (no type inference). {{RAW_DIR}} is set by run_pipeline.py.
-- Columns keep their original names: InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country.
-- Databricks: read_files('/Volumes/workspace/da_learn_16/raw/online_retail.csv', format => 'csv', header => true,
--             schema => 'InvoiceNo STRING, StockCode STRING, Description STRING, Quantity STRING, InvoiceDate STRING,
--                        UnitPrice STRING, CustomerID STRING, Country STRING')
CREATE OR REPLACE TABLE stg_retail AS
SELECT * FROM read_csv('{{RAW_DIR}}/online_retail.csv', header = true, all_varchar = true,
  names = ['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country']);
