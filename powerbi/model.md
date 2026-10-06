# Power BI model (star schema)

| Table | Rows in `powerbi/data/` | Grain / key | Columns |
|---|---|---|---|
| fact_sales | 51,069 (sample: ~10% of orders) | one net sales line (invoice × stock code) | invoice, date_key, invoice_ts, invoice_hour, customer_id (blank = guest), stock_code, country_key, quantity, unit_price, line_revenue, is_guest, is_qty_outlier, is_revenue_outlier, is_extreme_line |
| dim_date | 305 (full) | trading day, `date_key` (yyyymmdd) | invoice_date, year, month, year_month (yyyymm), day_of_week (1 = Sun), day_name |
| dim_customer | 4,324 (full) | identified customer, `customer_id` | home_country (country of first purchase), first_purchase_date, cohort_month (yyyymm), countries_used |
| dim_product | 3,794 (full) | stock code, `stock_code` | description (most frequent), avg_unit_price, first_sold, last_sold |
| dim_country | 38 (full) | country, `country_key` | country (standardised: EIRE → Ireland, RSA → South Africa, USA → United States, Unspecified → Unknown), market |
| rfm_customer | 4,324 (full) | identified customer, `customer_id` | recency_days, frequency, monetary, first/last_purchase, r_score, f_score, m_score, rfm_code, rfm_total, segment |

Relationships (single direction, many-to-one from fact to dimension):
- fact_sales[date_key] → dim_date[date_key]
- fact_sales[customer_id] → dim_customer[customer_id] (guest lines have no match; that is expected)
- fact_sales[stock_code] → dim_product[stock_code]
- fact_sales[country_key] → dim_country[country_key]
- rfm_customer[customer_id] → dim_customer[customer_id] (one-to-one; filter direction both, so a segment slicer filters fact_sales)

Mark `dim_date` as the date table on `invoice_date`.

**Sizes.** The dimensions and `rfm_customer` are complete. `fact_sales` is **sample-sized**: every invoice whose numeric part is divisible by 10 (`CAST(regexp_replace(invoice, '[^0-9]', '') AS INT) % 10 = 0`), so whole baskets are kept (51,069 of 519,828 lines, 3.6 MB). Fact-based measures on the sample are therefore about 10% of the full totals. `rfm_customer` was computed in SQL on the full data, so the RFM visuals match `results/` exactly. For full-size fact numbers run `python scripts/download_full_data.py && python run_pipeline.py --source full` and load `data/clean/star/fact_sales.csv` (519,828 rows, gitignored) instead.
