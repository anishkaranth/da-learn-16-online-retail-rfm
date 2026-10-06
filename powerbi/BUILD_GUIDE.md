# Build guide (Power BI Desktop, Windows)

No `.pbix` is committed: this repo is built on Linux and Power BI Desktop runs on Windows only.

1. Use the committed CSVs in `powerbi/data/` (6 files, ~4.3 MB, UTF-8): full dimensions + `rfm_customer`, and a ~10% order sample of `fact_sales`. For the full fact table run `python scripts/download_full_data.py` then `python run_pipeline.py --source full` and load `data/clean/star/fact_sales.csv` instead.
2. Power BI Desktop > Get data > Text/CSV: load every CSV. In Power Query set `invoice`, `stock_code`, `description`, `country`, `segment`, `rfm_code`, `day_name`, `market`, `home_country` to **Text** (stock codes such as `85123A` and leading zeros must stay text); `customer_id`, `*_key`, `year_month`, `cohort_month`, `quantity`, scores, counts and `is_*` flags to Whole number; `invoice_ts` to Date/Time; `invoice_date`, `first_purchase_date`, `first_purchase`, `last_purchase`, `first_sold`, `last_sold` to Date; `unit_price`, `line_revenue`, `monetary`, `avg_unit_price` to Fixed decimal (currency, GBP).
3. Model view: create the relationships in `model.md`, and mark `dim_date` as the date table.
4. Modeling > New table: `Months Since = GENERATESERIES ( 0, 12, 1 )` (disconnected, for cohort retention).
5. New measures: paste `measures.dax` one measure at a time (all into fact_sales except the RFM ones, which go into rfm_customer).
6. Build the two pages in `dashboard_spec.md`. Check the RFM cards against the "Expected" column (they match exactly); fact-based cards will be ~10% of the expected values on the sample fact.
7. Optional: colour segments as in `results/images/rfm_segments.png` and use conditional formatting (background colour scale) on the R × F and cohort matrices.
8. Save as `da-learn-16-online-retail-rfm.pbix` locally (the binary is not committed).
