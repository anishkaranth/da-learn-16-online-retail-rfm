#!/usr/bin/env python3
"""Write results/RESULTS.md from results/metrics.json + results/tables/*.csv (every number comes from the full-data run)."""
import csv, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "results"
T = RES / "tables"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rd(name):
    with open(T / f"{name}.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(x):
    return float(x) if x not in ("", None) else 0.0


def ym(v):
    v = int(f(v)); return f"{MON[v % 100 - 1]} {v // 100}"


def num(v):
    if v in ("", None):
        return ""
    try:
        x = float(v)
    except ValueError:
        return str(v)
    return f"{int(x):,}" if x.is_integer() and abs(x) >= 1000 else (str(int(x)) if x.is_integer() else f"{x:,.2f}")


def table(rows, cols, heads=None, fmt=None):
    fmt = fmt or {}
    out = ["| " + " | ".join(heads or cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(fmt.get(c, num)(r[c]) for c in cols) + " |")
    return "\n".join(out)


def gbp(v, d=2):
    return f"£{f(v):,.{d}f}"


m = json.loads((RES / "metrics.json").read_text())
k = m["kpis"]
mon = sorted(rd("a_monthly"), key=lambda r: int(r["year_month"]))
tot = sum(f(r["revenue"]) for r in mon)
peak = max(mon, key=lambda r: f(r["revenue"]))
q4 = sum(f(r["revenue"]) for r in mon if r["year_month"] in ("201109", "201110", "201111"))
feb = next(r for r in mon if r["year_month"] == "201102")
segs = sorted(rd("a_rfm_segments"), key=lambda r: r["segment"])
sd = {r["segment"].split(" ", 1)[1]: r for r in segs}
rng = sorted(rd("a_rfm_score_ranges"), key=lambda r: (r["metric"], int(r["score"])))
cur = sorted(rd("a_retention_curve"), key=lambda r: int(r["months_since"]))
cd = {int(r["months_since"]): r for r in cur}
ex = [f(cd[i]["retention_ex_first_cohort_pct"]) for i in range(2, 11) if i in cd]
coh = rd("a_cohort_retention")
c1 = {int(r["cohort_month"]): r for r in coh if r["months_since"] == "1"}
cty = sorted(rd("a_country"), key=lambda r: -f(r["revenue"]))
prod = sorted(rd("a_products_top20"), key=lambda r: int(r["revenue_rank"]))
conc = rd("a_product_concentration")[0]
par = {int(r["pct_products"]): r for r in rd("a_product_pareto")}
ret = sorted(rd("a_returns_products"), key=lambda r: -f(r["return_value"]))[:8]
ext = sorted(rd("a_extreme_lines"), key=lambda r: -f(r["line_revenue"]))[:8]
rc = {r["entity"]: r for r in rd("dq_row_counts")}
iss = rd("dq_issues")
asr = sorted(rd("dq_assertions"), key=lambda r: r["check_name"])
npass = sum(1 for r in asr if r["status"] == "PASS")
wh = rd("a_weekday_hour")
dsum, hsum = {}, {}
for r in wh:
    dsum[r["day_name"]] = dsum.get(r["day_name"], 0) + f(r["orders"])
    hsum[int(r["invoice_hour"])] = hsum.get(int(r["invoice_hour"]), 0) + f(r["orders"])
top_day = {'Sun': 'Sunday', 'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday', 'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday'}[max(dsum, key=dsum.get)]; top_hour = max(hsum, key=hsum.get)
core = sum(v for h, v in hsum.items() if 10 <= h <= 15) / sum(hsum.values()) * 100
ch, lo, cl, ar, hb, lost = (sd[s] for s in ["Champions", "Loyal", "Cannot lose them", "At risk", "Hibernating", "Lost"])
raw = int(f(rc["raw invoice lines (stg_retail)"]["row_count"]))
net = int(f(rc["net sales lines (cln_sales = fact_sales)"]["row_count"]))
uk = cty[0]
intl = [r for r in cty if r["country"] != "United Kingdom"]

md = f"""# Results - da-learn-16 Online retail RFM (UCI Online Retail)

Run: `python run_pipeline.py --source full` on DuckDB {m['engine']['duckdb']} (local, full file: {raw:,} raw invoice lines → {net:,} net sales lines, {int(f(k['orders'])):,} orders, {int(f(k['customers'])):,} identified customers). Databricks was skipped because the workspace hit its resource quota, so there is no live dashboard; every number below is in `metrics.json` and `tables/`. **Revenue = net merchandise revenue in GBP (quantity × unit price) on valid sales lines, after removing duplicates, cancellations (C-invoices), bad-debt adjustments (A-invoices), postage / fee / voucher codes, zero prices, stock write-offs and sales lines exactly reversed by a credit note.** Guest lines (no CustomerID) count in revenue but not in customer metrics, RFM or cohorts. Quality checks: **{npass}/{len(asr)} assertions pass**.

![Dashboard](images/dashboard.png)

## Headline KPIs
| KPI | Value |
|---|---|
| Period | {k['first_date']} .. {k['last_date']} ({len(mon)} calendar months, {int(f(rc['dim_date']['row_count']))} trading days) |
| Net revenue | {gbp(k['revenue'])} |
| Gross sales before reversals / reversed value | {gbp(k['gross_sales_before_reversals'])} / {gbp(k['reversed_sales_value'])} |
| Orders / order lines / units | {int(f(k['orders'])):,} / {int(f(k['order_lines'])):,} / {int(f(k['units'])):,} |
| Average / median order value | {gbp(k['avg_order_value'])} / {gbp(k['median_order_value'])} |
| Lines per order | {f(k['avg_lines_per_order']):.2f} |
| Identified customers / revenue per customer | {int(f(k['customers'])):,} / {gbp(k['revenue_per_customer'])} |
| Repeat customers (2+ orders) | {f(k['repeat_customer_pct']):.2f}% |
| Guest revenue (no CustomerID) | {f(k['guest_revenue_pct']):.2f}% |
| UK share of revenue | {f(k['uk_revenue_pct']):.2f}% ({int(f(k['countries']))} countries in total) |
| Products sold | {int(f(k['products'])):,} stock codes |
| Credit-note returns (all C-invoice product lines) | {gbp(k['returns_value'])} ({f(k['return_rate_pct']):.2f}% of gross sales) |

## Insights
1. **Strongly seasonal, growing into Q4.** {ym(peak['year_month'])} is the peak at {gbp(peak['revenue'], 0)} ({int(f(peak['orders'])):,} orders, {int(f(peak['active_customers'])):,} active customers), {f(peak['revenue']) / f(feb['revenue']):.1f}× February 2011 ({gbp(feb['revenue'], 0)}). September to November 2011 alone bring {q4 / tot * 100:.1f}% of all revenue in the file. December 2011 has only {int(f(mon[-1]['trading_days']))} trading days (1-9 Dec), so its {gbp(mon[-1]['revenue'], 0)} is not a drop.
2. **RFM: a small core carries the business.** **Champions are {int(f(ch['customers'])):,} customers ({f(ch['customer_share_pct']):.1f}%) but {f(ch['revenue_share_pct']):.2f}% of revenue** ({gbp(ch['revenue'], 0)}; {f(ch['avg_frequency']):.1f} orders and {gbp(ch['avg_monetary'], 0)} each, last order {f(ch['avg_recency_days']):.0f} days ago on average). Champions plus Loyal = {f(ch['customer_share_pct']) + f(lo['customer_share_pct']):.1f}% of customers and {f(ch['revenue_share_pct']) + f(lo['revenue_share_pct']):.1f}% of revenue.
3. **Win-back list.** "Cannot lose them" ({int(f(cl['customers']))} customers, {f(cl['avg_frequency']):.1f} orders and {gbp(cl['avg_monetary'], 0)} each, silent for {f(cl['avg_recency_days']):.0f} days) and "At risk" ({int(f(ar['customers']))} customers, {f(ar['avg_frequency']):.1f} orders, {f(ar['avg_recency_days']):.0f} days) together hold {gbp(f(cl['revenue']) + f(ar['revenue']), 0)} ({f(cl['revenue_share_pct']) + f(ar['revenue_share_pct']):.2f}% of identified revenue). Hibernating + Lost are {f(hb['customer_share_pct']) + f(lost['customer_share_pct']):.1f}% of customers but only {f(hb['revenue_share_pct']) + f(lost['revenue_share_pct']):.2f}% of revenue.
4. **Retention is low but flat.** Only **{f(cd[1]['retention_pct']):.1f}%** of a cohort buys again in month 1 ({f(cd[1]['retention_ex_first_cohort_pct']):.1f}% without the Dec 2010 cohort), and for genuinely new cohorts (excluding Dec 2010) the curve then stays flat between {min(ex):.1f}% and {max(ex):.1f}% from M2 to M10 (all cohorts: M3 {f(cd[3]['retention_pct']):.1f}%, M6 {f(cd[6]['retention_pct']):.1f}%), so the customers who come back keep coming back. The Dec 2010 cohort retains far better (M1 {f(c1[201012]['retention_pct']):.1f}%) because the extract starts then and it contains the existing customer base.
5. **UK-centric, with a few big wholesale accounts abroad.** The UK is {f(uk['revenue_share_pct']):.2f}% of revenue. {intl[0]['country']} ({gbp(intl[0]['revenue'], 0)}) comes from only {int(f(intl[0]['customers']))} customers (AOV {gbp(intl[0]['avg_order_value'], 0)} vs {gbp(uk['avg_order_value'], 0)} in the UK) and {intl[1]['country']} (EIRE in the raw file, {gbp(intl[1]['revenue'], 0)}) from {int(f(intl[1]['customers']))}.
6. **Long tail of products.** The top 20% of {int(f(conc['products'])):,} products bring {f(conc['top20pct_products_share_pct']):.2f}% of revenue and the bottom half only {f(conc['bottom50pct_products_share_pct']):.2f}%, yet no item dominates: the top 10 are {f(conc['top10_share_pct']):.2f}% (#1 {prod[0]['description'].title()}, {gbp(prod[0]['revenue'], 0)}).
7. **Ordering pattern.** {core:.0f}% of orders start between 10:00 and 15:59, the busiest hour is {top_hour}:00 and the busiest day is {top_day}; there is no Saturday trading in the file.

## Data quality (before → after)
{table(sorted(rd('dq_row_counts'), key=lambda r: -f(r['row_count'])), ['entity', 'row_count', 'grain'])}

Issue counts (flags overlap, so they do not add up to the removed total):

{table(sorted(iss, key=lambda r: -f(r['affected_rows'])), ['check_name', 'affected_rows'])}

Null rates:

{table(rd('dq_null_rates'), ['column_name', 'raw_missing_pct', 'clean_missing_pct', 'treatment'])}

Assertions ({npass}/{len(asr)} PASS):

{table(asr, ['check_name', 'failed_rows', 'status'])}

![Data quality](images/data_quality.png)

## Monthly trend
{table(mon, ['year_month', 'revenue', 'orders', 'active_customers', 'new_customers', 'returning_customers', 'avg_order_value', 'guest_revenue_pct', 'revenue_mom_pct', 'trading_days'])}

![Monthly revenue](images/monthly_revenue.png)
![New vs returning](images/new_vs_returning_customers.png)
![Orders and customers](images/orders_and_customers.png)
![Weekday x hour](images/orders_weekday_hour.png)

## RFM segmentation
Snapshot 2011-12-10 (the day after the last invoice). R = days since the last order, F = distinct orders, M = net revenue. Scores are **tie-aware quintiles** (`1 + floor(5 × (rank − 1) / n)` with `RANK()`), so customers with equal values always share a score; because {int(f(next(r for r in rng if r['metric'].startswith('F') and r['score'] == '1')['customers'])):,} customers ordered once, F1 is larger than a fifth. Segment rules (first match wins): Champions R≥4 & F≥4; Loyal R≥3 & F≥3; Potential loyalist R≥4 & F=2; New customers R≥4 & F=1; Needs attention R=3; Cannot lose them R≤2 & F≥4 & M≥4; At risk R≤2 & F≥3; Hibernating R=2; Lost R=1.

{table(segs, ['segment', 'customers', 'customer_share_pct', 'revenue', 'revenue_share_pct', 'avg_recency_days', 'avg_frequency', 'avg_monetary', 'median_monetary'])}

What each score means on this data:

{table(rng, ['metric', 'score', 'customers', 'min_value', 'max_value'])}

![RFM segments](images/rfm_segments.png)
![RFM grid](images/rfm_rf_grid.png)

## Cohort retention
Cohort = month of the first net purchase. Retention at offset N = share of the cohort with a purchase in calendar month cohort + N. The curve is size-weighted over the cohorts that can be observed at each offset (late offsets rest on few cohorts; M11-M12 include only the first one or two).

{table(cur, ['months_since', 'cohorts', 'eligible_customers', 'active_customers', 'retention_pct', 'retention_ex_first_cohort_pct'])}

![Cohort heatmap](images/cohort_retention_heatmap.png)
![Retention curve](images/retention_curve.png)

## Countries (top 12 by revenue)
{table(cty[:12], ['country', 'market', 'revenue', 'revenue_share_pct', 'orders', 'customers', 'avg_order_value', 'revenue_per_customer'])}

![Countries](images/top_countries_ex_uk.png)

## Products
Concentration: top 10 = {f(conc['top10_share_pct']):.2f}%, top 100 = {f(conc['top100_share_pct']):.2f}%, top 20% of products = {f(conc['top20pct_products_share_pct']):.2f}%, top 5% = {f(par[5]['cum_revenue_share_pct']):.2f}%, bottom 50% = {f(conc['bottom50pct_products_share_pct']):.2f}% of revenue.

{table(prod[:15], ['revenue_rank', 'stock_code', 'description', 'revenue', 'revenue_share_pct', 'units', 'orders', 'customers'])}

![Top products](images/top_products.png)
![Pareto](images/product_pareto.png)

Most-returned products by value (credit notes; the top lines include the two giant order-entry mistakes that were reversed):

{table(ret, ['stock_code', 'description', 'return_value', 'units_returned', 'credit_notes'])}

Largest single lines kept after reversal netting (flagged `is_extreme_line`, above the 99.9th percentile of line revenue):

{table(ext, ['invoice', 'invoice_date', 'customer_id', 'stock_code', 'description', 'country', 'quantity', 'unit_price', 'line_revenue'])}

## Files
- `metrics.json`: KPIs, data-quality counts and assertions, engine versions and SQL timings.
- `JSON.shot`: headline snapshot (KPIs, RFM segments, countries, products, retention, config). Valid JSON.
- `tables/*.csv`: every `a_*` analysis table and `dq_*` quality table from the full run.
- `images/*.svg` (plain vector shapes, no embedded raster) and `images/*.png` (2× headless-Chrome renders of the same SVGs).
- `sample/`: the same outputs from the committed raw sample (`--source sample`) - small numbers, for smoke-testing only.
"""
(RES / "RESULTS.md").write_text(md)
print("wrote results/RESULTS.md", len(md), "chars")
