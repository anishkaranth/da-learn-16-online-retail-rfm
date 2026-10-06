#!/usr/bin/env python3
"""Render SVG charts (pure vector shapes, no raster) from the KPI tables exported by run_pipeline.py."""
import csv, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import svgcharts as S

BLUE, ORANGE, GREEN, SAND, NAVY = S.PALETTE[0], S.PALETTE[1], S.PALETTE[2], S.PALETTE[3], S.PALETTE[4]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEG_COLOR = {"Champions": "#1f6f8b", "Loyal": "#3f8fa8", "Potential loyalist": "#81b29a", "New customers": "#a8cdb8",
             "Needs attention": "#f2cc8f", "Cannot lose them": "#b56576", "At risk": "#e07a5f", "Hibernating": "#9c9c9c",
             "Lost": "#5f5f6b"}


def _vmax(vals, room):
    """Axis maximum with head-room for the value labels printed after each bar."""
    return max(vals) * room if vals else None


def rd(t, name):
    with open(pathlib.Path(t) / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f(x):
    return float(x) if x not in ("", None) else 0.0


def ym(v):
    v = int(f(v))
    return f"{MON[v % 100 - 1]} {str(v // 100)[2:]}"


SHORT = [("exact duplicate", "exact duplicates (removed)"), ("cancellation", "C-invoice lines (-> returns)"),
         ("bad-debt", "A-invoice adjustments (removed)"), ("non-product", "postage / fees / vouchers (removed)"),
         ("unit price", "price <= 0 (removed)"), ("quantity <= 0", "qty <= 0 write-offs (removed)"),
         ("sales lines exactly", "reversed by credit note (removed)"), ("missing description", "missing description"),
         ("missing CustomerID", "missing CustomerID (all lines)"), ("net sales lines without", "guest sales lines (kept)"),
         ("country labels", "country label standardised"), ("quantity above", "qty > Q3 + 1.5 IQR (flag)"),
         ("line revenue above Q3", "revenue > Q3 + 1.5 IQR (flag)"), ("line revenue above the 99.9", "revenue > P99.9 (flag)")]


def short(name):
    return next((v for k, v in SHORT if name.startswith(k)), name[:36])


def seg(s):
    return s.split(" ", 1)[1]


def panels(t):
    k = rd(t, "a_kpi_headline")[0]
    mon = sorted(rd(t, "a_monthly"), key=lambda r: int(r["year_month"]))
    peak = max(mon, key=lambda r: f(r["revenue"]))
    wh = rd(t, "a_weekday_hour")
    days = sorted({(int(r["day_of_week"]), r["day_name"]) for r in wh})
    hours = sorted({int(r["invoice_hour"]) for r in wh})
    whv = {(int(r["day_of_week"]), int(r["invoice_hour"])): f(r["orders"]) for r in wh}
    dsum = {d: sum(v for (di, _), v in whv.items() if di == i) for i, d in days}
    hsum = {h: sum(v for (_, hi), v in whv.items() if hi == h) for h in hours}
    top_day, top_hour = max(dsum, key=dsum.get), max(hsum, key=hsum.get)
    core = sum(v for h, v in hsum.items() if 10 <= h <= 15) / sum(hsum.values()) * 100
    has_sat = any(d == "Sat" for _, d in days)
    cty = sorted(rd(t, "a_country"), key=lambda r: -f(r["revenue"]))
    uk = next((r for r in cty if r["country"] == "United Kingdom"), cty[0])
    intl = [r for r in cty if r["country"] != "United Kingdom"][:12]
    prod = sorted(rd(t, "a_products_top20"), key=lambda r: -f(r["revenue"]))[:15]
    conc = rd(t, "a_product_concentration")[0]
    par = sorted(rd(t, "a_product_pareto"), key=lambda r: int(r["pct_products"]))
    coh = rd(t, "a_cohort_retention")
    cohorts = sorted({int(r["cohort_month"]) for r in coh})
    offs = list(range(1, 13))
    cv = {(int(r["cohort_month"]), int(r["months_since"])): f(r["retention_pct"]) for r in coh}
    csz = {int(r["cohort_month"]): int(f(r["cohort_size"])) for r in coh}
    cur = sorted(rd(t, "a_retention_curve"), key=lambda r: int(r["months_since"]))
    cur1 = [r for r in cur if int(r["months_since"]) >= 1]
    segs = sorted(rd(t, "a_rfm_segments"), key=lambda r: r["segment"])
    sd = {seg(r["segment"]): r for r in segs}
    grid = {(int(r["r_score"]), int(r["f_score"])): r for r in rd(t, "a_rfm_grid")}
    rng = {(r["metric"][0], int(r["score"])): r for r in rd(t, "a_rfm_score_ranges")}
    r5, f5 = rng.get(("R", 5)), rng.get(("F", 5))
    grid_sub = (f"R5 = last order <= {int(f(r5['max_value']))} days before the snapshot, F5 = {int(f(f5['min_value']))}+ orders; "
                "cell = customers / avg spend GBP") if r5 and f5 else "cell = customers / avg spend GBP"
    dq = sorted(rd(t, "dq_issues"), key=lambda r: -f(r["affected_rows"]))
    dq = [r for r in dq if not r["check_name"].startswith("total")]
    m1 = next((r for r in cur if int(r["months_since"]) == 1), None)
    ch = sd.get("Champions", {})
    ps = [
        ("monthly_revenue", S.vbar("Net revenue by month (GBP k)", [ym(r["year_month"]) for r in mon],
                                   [f(r["revenue"]) / 1e3 for r in mon], "{:,.0f}",
                                   f"peak {ym(peak['year_month'])}: GBP {f(peak['revenue']) / 1e6:.2f}M from {int(f(peak['orders'])):,} orders; "
                                   f"Dec 11 covers only {int(f(mon[-1]['trading_days']))} trading days (1-9 Dec)",
                                   color=[ORANGE if r is peak else (S.PALETTE[4] if r is mon[-1] else BLUE) for r in mon],
                                   ylabel="GBP thousand", w=760)),
        ("new_vs_returning_customers", S.grouped_vbar("Active customers per month: new vs returning", [ym(r["year_month"]) for r in mon],
                                                      [("new (first purchase)", [f(r["new_customers"]) for r in mon]),
                                                       ("returning", [f(r["returning_customers"]) for r in mon])], "{:.0f}",
                                                      "Dec 10 counts everyone as new (start of the extract); returning buyers carry the autumn peak",
                                                      w=760, ylabel="customers")),
        ("orders_and_customers", S.line("Orders and active customers per month", [ym(r["year_month"]) for r in mon],
                                        [("orders", [f(r["orders"]) for r in mon]), ("active customers", [f(r["active_customers"]) for r in mon])],
                                        "{:,.0f}", f"overall AOV GBP {f(k['avg_order_value']):,.2f} (median GBP {f(k['median_order_value']):,.2f}); "
                                                   f"{f(k['avg_lines_per_order']):.1f} lines per order", every=1, ymin=0, w=760)),
        ("orders_weekday_hour", S.heatmap("Orders by weekday and hour (invoice timestamp)", [d for _, d in days], [str(h) for h in hours],
                                          [[whv.get((di, h)) for h in hours] for di, _ in days], "{:.0f}",
                                          f"{'' if has_sat else 'no Saturday trading; '}{core:.0f}% of orders start 10:00-15:59; busiest day {top_day}, "
                                          f"busiest hour {top_hour}:00",
                                          w=760, h=230, xlabel="hour of day")),
        ("top_countries_ex_uk", S.hbar("Top 12 countries outside the UK by net revenue (GBP k)", [r["country"] for r in intl],
                                       [f(r["revenue"]) / 1e3 for r in intl], "{:,.1f}",
                                       f"UK = {f(uk['revenue_share_pct']):.2f}% of revenue (GBP {f(uk['revenue']) / 1e6:.2f}M); labels: customers, AOV",
                                       notes=[f"({int(f(r['customers']))} cust., AOV {f(r['avg_order_value']):,.0f})" for r in intl],
                                       w=760, vmax=_vmax([f(r["revenue"]) / 1e3 for r in intl], 1.45))),
        ("top_products", S.hbar("Top 15 products by net revenue (GBP k)", [r["description"][:34] for r in prod],
                                [f(r["revenue"]) / 1e3 for r in prod], "{:,.1f}",
                                f"top 10 of {int(f(conc['products'])):,} products = {f(conc['top10_share_pct']):.2f}% of revenue; labels: units sold",
                                notes=[f"({int(f(r['units'])):,} units)" for r in prod], color=GREEN, w=760,
                                vmax=_vmax([f(r["revenue"]) / 1e3 for r in prod], 1.3))),
        ("product_pareto", S.line("Product concentration (Pareto curve)", [f"{r['pct_products']}%" for r in par],
                                  [("cumulative revenue share %", [f(r["cum_revenue_share_pct"]) for r in par])], "{:.0f}",
                                  f"top 20% of products = {f(conc['top20pct_products_share_pct']):.2f}% of revenue; bottom half = "
                                  f"{f(conc['bottom50pct_products_share_pct']):.2f}%", every=2, ymin=0, xlabel="share of products (ranked by revenue)",
                                  w=760)),
        ("cohort_retention_heatmap", S.heatmap("Monthly cohort retention (% of cohort buying again N months later)",
                                               [f"{ym(c)} (n={csz[c]})" for c in cohorts], [f"M{o}" for o in offs],
                                               [[cv.get((c, o)) for o in offs] for c in cohorts], "{:.0f}",
                                               "M0 = 100% by definition (not shown); the Dec 10 cohort includes long-standing customers",
                                               w=760, h=380, vmin=0, vmax=45, xlabel="months since first purchase")),
        ("retention_curve", S.line("Average retention curve (size-weighted over observable cohorts, %)", [f"M{r['months_since']}" for r in cur1],
                                   [("all cohorts", [f(r["retention_pct"]) for r in cur1]),
                                    ("excluding the Dec 10 cohort", [f(r["retention_ex_first_cohort_pct"]) if r["retention_ex_first_cohort_pct"] else None for r in cur1])],
                                   "{:.0f}", f"M1 {f(m1['retention_pct']):.1f}% (all) vs {f(m1['retention_ex_first_cohort_pct']):.1f}% (new customers only); "
                                             "late offsets rest on few cohorts", every=1, ymin=0, w=760)),
        ("rfm_segments", S.grouped_vbar("RFM segments: share of customers vs share of revenue (%)", [seg(r["segment"]).replace("Potential loyalist", "Potential loy.").replace("Cannot lose them", "Cannot lose").replace("Needs attention", "Needs attn.").replace("New customers", "New") for r in segs],
                                        [("customers %", [f(r["customer_share_pct"]) for r in segs]),
                                         ("revenue %", [f(r["revenue_share_pct"]) for r in segs])], "{:.1f}",
                                        f"Champions: {int(f(ch.get('customers')))} customers ({f(ch.get('customer_share_pct')):.1f}%) bring "
                                        f"{f(ch.get('revenue_share_pct')):.1f}% of revenue", w=760, ylabel="%")),
        ("rfm_rf_grid", S.heatmap("RFM grid: customers per Recency x Frequency score (avg spend in label)",
                                  [f"R{r}" for r in range(5, 0, -1)], [f"F{c}" for c in range(1, 6)],
                                  [[f(grid[(r, c)]["customers"]) if (r, c) in grid else None for c in range(1, 6)] for r in range(5, 0, -1)],
                                  "{:.0f}", grid_sub,
                                  notes=[[f"{int(f(grid[(r, c)]['customers']))} / {f(grid[(r, c)]['avg_monetary']):,.0f}" if (r, c) in grid else ""
                                          for c in range(1, 6)] for r in range(5, 0, -1)],
                                  w=760, h=300, xlabel="frequency score (orders)", ylabel="recency score")),
        ("data_quality", S.hbar("Data-quality issues in the raw feed (lines; flags overlap)", [short(r["check_name"]) for r in dq],
                                [f(r["affected_rows"]) for r in dq], "{:,.0f}",
                                "removed: duplicates, A-invoices, fees, price <= 0, write-offs, reversals; C-invoices -> returns; outliers flagged",
                                color=SAND, w=760)),
    ]
    return ps, k, sd


def make_all(tables, out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    ps, k, sd = panels(tables)
    for name, p in ps:
        S.save(p, out / f"{name}.svg")
    ch = sd.get("Champions", {})
    cards = [("Net revenue", f"GBP {f(k['revenue']) / 1e6:.2f}M"), ("Orders", f"{int(f(k['orders'])):,}"),
             ("Customers", f"{int(f(k['customers'])):,}"), ("Avg order value", f"GBP {f(k['avg_order_value']):,.0f}"),
             ("Repeat customers", f"{f(k['repeat_customer_pct']):.1f}%"), ("UK share", f"{f(k['uk_revenue_pct']):.1f}%"),
             ("Champions revenue", f"{f(ch.get('revenue_share_pct')):.1f}%")]
    order = ["monthly_revenue", "rfm_segments", "retention_curve", "rfm_rf_grid", "top_countries_ex_uk", "top_products"]
    dash = [dict(ps)[n] for n in order]
    S.dashboard(out / "dashboard.svg", "Online retail: revenue, customers and RFM segments (UCI Online Retail, Dec 2010 - Dec 2011)",
                f"Rendered from results/tables (SQL on DuckDB, full data: {int(f(k['order_lines'])):,} net sales lines, "
                f"{int(f(k['orders'])):,} orders). Net merchandise revenue in GBP after removing cancellations, reversals, fees and duplicates.",
                cards, dash, cols=2)
    print("charts ->", out, sorted(p.name for p in out.glob("*.svg")))


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parents[1]
    make_all(root / "results/tables", root / "results/images")
