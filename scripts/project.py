"""Project-specific settings used by run_pipeline.py (raw files, exports, JSON.shot content)."""
NAME = "da-learn-16-online-retail-rfm"
DATASET = ("UCI Online Retail (Chen 2015, UCI ML Repository id 352, doi:10.24432/C5BW33; Kaggle carrie1/ecommerce-data; "
           "CC BY 4.0; UK online gift retailer, 2010-12-01..2011-12-09, 541,909 invoice lines x 8 columns; "
           "online+retail.zip 23,715,478 B -> online_retail.csv 47,226,068 B)")
RAW_FILES = ["online_retail.csv"]
STAR = ["fact_sales", "dim_customer", "dim_product", "dim_country", "dim_date"]
# Power BI / data/clean sample rule: every invoice whose numeric part is divisible by 10 (~10% of orders, whole baskets)
SAMPLE_WHERE = "CAST(regexp_replace(invoice, '[^0-9]', '') AS INT) % 10 = 0"
METRIC_TABLES = ["a_kpi_headline", "a_monthly", "a_weekday_hour", "a_country", "a_products_top20", "a_product_concentration",
                 "a_product_pareto", "a_rfm_segments", "a_rfm_grid", "a_rfm_score_ranges", "a_cohort_retention",
                 "a_retention_curve", "a_returns_products", "a_extreme_lines"]


def export_full(con, export, root):
    """Full run: full star -> data/clean/star/ (gitignored); sample-sized star + full dims + RFM -> powerbi/data/ and data/clean/."""
    con.execute(f"CREATE OR REPLACE TEMP VIEW fact_sales_sample AS SELECT * FROM fact_sales WHERE {SAMPLE_WHERE}")
    con.execute(f"CREATE OR REPLACE TEMP VIEW cln_sales_sample AS SELECT * FROM cln_sales WHERE {SAMPLE_WHERE}")
    for t in STAR:
        export(con, t, root / "data/clean/star" / f"{t}.csv")
    for t in STAR[1:]:
        export(con, t, root / "powerbi/data" / f"{t}.csv")
    export(con, "fact_sales_sample", root / "powerbi/data/fact_sales.csv")
    export(con, "a_rfm_customers", root / "powerbi/data/rfm_customer.csv")
    export(con, "cln_sales_sample", root / "data/clean/sales_lines_sample.csv")
    export(con, "a_rfm_customers", root / "data/clean/customers_rfm.csv")


def build_shot(q, kpi):
    """Headline snapshot written to results/JSON.shot."""
    return {
        "config": {"sql_dialect": "Spark SQL style (+ DuckDB shims in sql/00), run on DuckDB",
                   "grain": "fact_sales = one net sales line (invoice x stock code); customers = identified CustomerID with a net sale",
                   "revenue": "net merchandise revenue = quantity x unit price (GBP) on valid sales lines, after removing lines "
                              "exactly reversed by a credit note; postage/fees/manual/discount/voucher codes excluded",
                   "cleaning": "exact duplicates removed; C-invoices -> returns; A-invoices, price <= 0, quantity <= 0 on sales "
                               "invoices and non-product codes removed; missing CustomerID kept as guest revenue; country labels standardised",
                   "outlier_rule": "quantity / line revenue above Q3 + 1.5 IQR and line revenue above P99.9 are flagged and kept",
                   "rfm": "snapshot = 2011-12-10 (day after the last invoice); R = days since last order, F = distinct orders, "
                          "M = net revenue; tie-aware quintile scores 1..5 (1 + floor(5*(rank-1)/n)); 9 named segments from R/F (+M)",
                   "cohort": "cohort = month of first net purchase; retention = share of the cohort with a purchase N months later",
                   "sample_rule": "data/raw: every line of customers with crc32(CustomerID) % 20 = 0, every line of guest invoices with "
                                  "crc32(InvoiceNo) % 40 = 0, plus the first examples of each cleaning rule (scripts/make_sample.py)"},
        "headline": kpi,
        "rfm_segments": q("SELECT segment, customers, customer_share_pct, revenue, revenue_share_pct, avg_recency_days, avg_frequency, avg_monetary FROM a_rfm_segments ORDER BY segment"),
        "product_concentration": q("SELECT * FROM a_product_concentration")[0],
        "top_countries": q("SELECT country, revenue, revenue_share_pct, customers, avg_order_value FROM a_country ORDER BY revenue DESC LIMIT 6"),
        "top_products": q("SELECT stock_code, description, revenue, units FROM a_products ORDER BY revenue DESC LIMIT 5"),
        "retention_curve": q("SELECT months_since, cohorts, retention_pct, retention_ex_first_cohort_pct FROM a_retention_curve WHERE months_since IN (1, 2, 3, 6, 9, 12) ORDER BY months_since"),
        "peak_month": q("SELECT year_month, revenue, orders, active_customers FROM a_monthly ORDER BY revenue DESC LIMIT 1")[0],
    }
