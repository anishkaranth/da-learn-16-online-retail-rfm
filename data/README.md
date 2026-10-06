# data/

- `raw/online_retail.csv` is a **21,303-line sample** of the real dataset (1.86 MB), built by `scripts/make_sample.py` from the full CSV. Lines are copied byte-for-byte with the same header. The rule is deterministic: every line of identified customers with `crc32(CustomerID) % 20 = 0` (complete purchase histories, so RFM and cohorts work), every line of guest invoices with `crc32(InvoiceNo) % 40 = 0`, the full history of customers 12346 and 16446 (the two giant 74,215- and 80,995-unit lines that were cancelled minutes later), and the first examples of every cleaning rule (exact duplicates, A-invoices, each postage/fee/voucher code, zero prices, stock write-offs, missing descriptions, non-standard country labels). `python run_pipeline.py --source sample` runs the whole pipeline on it (31/31 assertions pass).
- `raw_full/` (git-ignored) holds `online_retail.zip` (23,715,478 B, SHA-256 checked) and `online_retail.csv` (541,909 rows, 47,226,068 B), written by `python scripts/download_full_data.py`.
- `clean/customers_rfm.csv` holds all 4,324 identified customers with recency, frequency, monetary, R/F/M scores and segment (full data, from `a_rfm_customers`).
- `clean/sales_lines_sample.csv` holds the cleaned net sales lines (`cln_sales`, typed, standardised and outlier-flagged) for ~10% of orders (invoice number divisible by 10; 51,069 of 519,828 lines). The full table is written to `clean/star/` (git-ignored) by the full run.
- `clean/star/` (git-ignored) holds the full star-schema CSVs (`fact_sales` 519,828 rows + 4 dimensions).

CSV format of the raw files: header `InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country`, UTF-8, LF, `InvoiceDate` as `YYYY-MM-DD HH:MM:SS`, `CustomerID` blank when missing.

Source: UCI Machine Learning Repository, Online Retail (https://archive.ics.uci.edu/dataset/352/online+retail), Chen (2015), CC BY 4.0.
