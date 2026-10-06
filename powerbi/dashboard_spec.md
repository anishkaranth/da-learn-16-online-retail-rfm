# Dashboard spec - "da-learn-16 Online retail RFM"

Two pages, 16:9. Slicers: dim_date[year_month], dim_country[market] and dim_country[country], rfm_customer[segment].
"Expected" values are the full-data numbers from `results/metrics.json` and `results/tables/` (no filters). Fact-based visuals on the committed sample `fact_sales.csv` show roughly a tenth of these; RFM visuals use `rfm_customer` and match exactly.

**Page 1 - Sales overview**

| # | Visual | Fields | Expected (full data) |
|---|---|---|---|
| 1 | KPI cards | Net Revenue, Orders, Customers, Avg Order Value, Repeat Customer %, UK Share %, Guest Revenue % | £9,861,383.75 / 19,693 / 4,324 / £500.76 / 65.29% / 84.77% / 15.31% |
| 2 | Column: revenue by month | dim_date[year_month], [Net Revenue] | peak 201111 £1,441,294.88; 201102 £504,219.73; 201112 £445,449.10 (8 trading days) |
| 3 | Clustered column: new vs returning customers | dim_date[year_month], [New Customers], [Customers] − [New Customers] | 201111: 322 new, 1,337 returning |
| 4 | Bar: top countries outside the UK | dim_country[country] (filter ≠ United Kingdom), [Net Revenue], tooltip [Customers], [Avg Order Value] | Netherlands £283,479.54 (9 customers), Ireland £261,649.81 (3), Germany £203,961.43 (94) |
| 5 | Bar: top 15 products | dim_product[description], [Net Revenue] (Top N = 15) | Regency Cakestand 3 Tier £170,280.39; White Hanging Heart T-Light Holder £99,941.43 |
| 6 | Matrix heatmap: weekday × hour | dim_date[day_name], fact_sales[invoice_hour], [Orders] | busiest hour 12:00, busiest day Thursday, no Saturdays |

**Page 2 - Customers (RFM and retention)**

| # | Visual | Fields | Expected (full data) |
|---|---|---|---|
| 7 | Clustered bar: segments | rfm_customer[segment], [RFM Customer Share %], [RFM Revenue Share %] | Champions 23.20% of customers / 66.44% of revenue; Lost 18.20% / 4.35% |
| 8 | Table: segment profile | segment, [RFM Customers], [RFM Revenue], [Avg Recency (days)], [Avg Frequency (orders)], [Avg Monetary] | Champions 1,003 / £5,548,928.85 / 12.8 / 10.73 / £5,532.33 |
| 9 | Matrix: R × F grid | rfm_customer[r_score] (rows, descending), rfm_customer[f_score] (columns), [RFM Customers], conditional formatting | R5F5 437 customers (avg £9,013.24); R1F1 631 (avg £324.93) |
| 10 | Matrix: cohort retention | dim_customer[cohort_month] (rows), 'Months Since'[Value] (columns), [Retention %] | 201012 M1 36.58%; all-cohort M1 22.60% (`a_retention_curve`) |
| 11 | Card + table: win-back list | rfm_customer filtered to "06 Cannot lose them" + "07 At risk", customer_id, recency_days, frequency, monetary | 148 + 248 customers, £566,313 |

Reference renders of the same visuals (DuckDB): `results/images/dashboard.png` and the individual PNGs in `results/images/`.
