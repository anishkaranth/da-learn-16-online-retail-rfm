#!/usr/bin/env python3
"""Run the SQL pipeline (sql/00..05) on DuckDB and export clean tables, star CSVs, KPI tables, metrics, JSON.shot and SVG charts.

Usage
  python run_pipeline.py --source sample   # data/raw (in git, sample)   -> results/sample/ (metrics, JSON.shot, tables, images)
  python run_pipeline.py --source full     # data/raw_full (download)      -> results/, data/clean/, powerbi/data/
                                           #   (download first: python scripts/download_full_data.py)
  python scripts/render_png.py             # results/images/*.svg -> *.png (headless Chrome)
  python scripts/write_results.py          # (also run automatically by --source full) results/RESULTS.md
Project-specific settings (raw files, star tables, JSON.shot content) live in scripts/project.py.
"""
import argparse, csv, importlib.util, json, pathlib, platform, sys, time
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
SQL_FILES = ["00_duckdb_compat.sql", "01_staging.sql", "02_cleaning.sql", "03_model.sql",
             "04_analysis.sql", "05_quality_checks.sql"]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def split_sql(text):
    """Split on ';' at end of line after removing -- comments (scripts contain no ';' inside strings)."""
    stmts, buf = [], []
    for line in text.splitlines():
        i = line.find("--")
        if i >= 0 and line[:i].count("'") % 2 == 0:
            line = line[:i]
        if not line.strip():
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            s = "\n".join(buf).strip().rstrip(";").strip()
            if s:
                stmts.append(s)
            buf = []
    return stmts


def jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if v.__class__.__name__ == "Decimal":
        return float(v)
    return v


def rows(con, q):
    cur = con.execute(q)
    cols = [d[0] for d in cur.description]
    return [{k: jsonable(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


def export(con, table, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = con.execute(f"SELECT * FROM {table} ORDER BY ALL")
    cols = [d[0] for d in cur.description]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in cur.fetchall():
            w.writerow(["" if v is None else jsonable(v) for v in r])


def run_sql(raw, verbose=True):
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    timings = {}
    for f in SQL_FILES:
        t0 = time.time()
        text = (ROOT / "sql" / f).read_text().replace("{{RAW_DIR}}", raw.as_posix()).replace("{{REF_DIR}}", (ROOT / "data/reference").as_posix())
        for s in split_sql(text):
            try:
                con.execute(s)
            except Exception as e:
                raise SystemExit(f"{f}: {e}\n{s[:400]}")
        timings[f] = round(time.time() - t0, 3)
        if verbose:
            print(f"ran {f:24s} {timings[f]:6.2f}s")
    return con, timings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sample", "full"], default="sample")
    ap.add_argument("--no-charts", action="store_true")
    a = ap.parse_args()
    P = load("project")
    full = a.source == "full"
    raw = ROOT / ("data/raw_full" if full else "data/raw")
    res = ROOT / ("results" if full else "results/sample")
    for f in P.RAW_FILES:
        if not (raw / f).exists():
            raise SystemExit(f"missing {raw}/{f}; run scripts/download_full_data.py (full) or scripts/make_sample.py")

    con, timings = run_sql(raw)
    if full:
        P.export_full(con, export, ROOT)   # data/clean/ + powerbi/data/ (rules in scripts/project.py)
    tables = [r["table_name"] for r in rows(con, "SELECT table_name FROM information_schema.tables "
              "WHERE table_name LIKE 'a\\_%' ESCAPE '\\' OR table_name LIKE 'dq\\_%' ESCAPE '\\' ORDER BY 1")]
    for t in tables:
        export(con, t, res / "tables" / f"{t}.csv")

    kpi = rows(con, "SELECT * FROM a_kpi_headline")[0]
    dq = {
        "row_counts": rows(con, "SELECT * FROM dq_row_counts"),
        "null_rates": rows(con, "SELECT * FROM dq_null_rates"),
        "issues": {r["check_name"]: r["affected_rows"] for r in rows(con, "SELECT * FROM dq_issues")},
        "assertions": {r["check_name"]: r["status"] for r in rows(con, "SELECT * FROM dq_assertions")},
    }
    metrics = {"project": P.NAME, "dataset": P.DATASET, "source_mode": a.source, "kpis": kpi,
               "analysis_tables": [f"tables/{t}.csv" for t in P.METRIC_TABLES],
               "data_quality": dq, "engine": {"duckdb": duckdb.__version__, "python": platform.python_version()},
               "sql_timings_s": timings}
    res.mkdir(parents=True, exist_ok=True)
    (res / "metrics.json").write_text(load("jsonfmt").dumps(metrics) + "\n")
    shot = P.build_shot(lambda q: rows(con, q), kpi)
    shot = {"snapshot": "headline KPIs + run config", "project": P.NAME, "source_mode": a.source,
            "engine": f"duckdb {duckdb.__version__}", **shot,
            "assertions_passed": sum(1 for v in dq["assertions"].values() if v == "PASS"),
            "assertions_total": len(dq["assertions"])}
    (res / "JSON.shot").write_text(load("jsonfmt").dumps(shot) + "\n")
    json.loads((res / "JSON.shot").read_text())  # must be valid JSON
    print(json.dumps(kpi, indent=1))
    print("assertions", shot["assertions_passed"], "/", shot["assertions_total"])
    failed = [k for k, v in dq["assertions"].items() if v != "PASS"]
    if failed:
        raise SystemExit(f"FAILED assertions: {failed}")
    if not a.no_charts:
        load("make_charts").make_all(res / "tables", res / "images")
    if full:
        load("write_results")   # results/RESULTS.md from metrics.json + tables


if __name__ == "__main__":
    main()
