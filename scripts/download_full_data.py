#!/usr/bin/env python3
"""Download UCI Online Retail (dataset 352) into data/raw_full/, verify SHA-256 and convert the workbook to one CSV.

Source  : Chen, D. (2015). "Online Retail". UCI Machine Learning Repository, https://doi.org/10.24432/C5BW33
          https://archive.ics.uci.edu/dataset/352/online+retail
Kaggle  : https://www.kaggle.com/datasets/carrie1/ecommerce-data (the same 541,909 lines as data.csv)
Licence : Creative Commons Attribution 4.0 International (CC BY 4.0)
Mirror  : https://archive.ics.uci.edu/static/public/352/online+retail.zip (23,715,478 bytes, contains "Online Retail.xlsx")
Output  : data/raw_full/online_retail.csv - original column names (InvoiceNo, StockCode, Description, Quantity,
          InvoiceDate, UnitPrice, CustomerID, Country), InvoiceDate as 'YYYY-MM-DD HH:MM:SS', CustomerID as an integer
          string (blank when missing), UnitPrice as the exact float from the workbook. UTF-8, LF line endings.
Needs   : pip install openpyxl (only for the one-off xlsx -> csv conversion, ~1 minute).
"""
import csv, hashlib, io, pathlib, sys, time, urllib.request, zipfile

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
SHA = "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b"
SIZE = 23_715_478
HEADER = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
out = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw_full"
out.mkdir(parents=True, exist_ok=True)
z = out / "online_retail.zip"
if not z.exists() or hashlib.sha256(z.read_bytes()).hexdigest() != SHA:
    for i in range(3):
        try:
            print("downloading", URL)
            req = urllib.request.Request(URL, headers={"User-Agent": "curl/8.5.0"})
            with urllib.request.urlopen(req, timeout=300) as r:
                z.write_bytes(r.read())
            break
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {i + 1} failed: {e}"); time.sleep(3 * (i + 1))
got = hashlib.sha256(z.read_bytes()).hexdigest()
print(f"{z.name} {z.stat().st_size:,} bytes (expected {SIZE:,})  {'sha256 OK' if got == SHA else 'CHECKSUM MISMATCH ' + got}")
if got != SHA:
    sys.exit(1)


def txt(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


dst = out / "online_retail.csv"
if not dst.exists():
    import openpyxl
    with zipfile.ZipFile(z) as zf:
        wb = openpyxl.load_workbook(io.BytesIO(zf.read("Online Retail.xlsx")), read_only=True)
    n = 0
    tmp = dst.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for i, r in enumerate(wb.worksheets[0].iter_rows(values_only=True)):
            if i == 0:
                assert [str(c) for c in r[:8]] == HEADER, r
                continue
            if all(c is None for c in r[:8]):
                continue
            inv, code, desc, qty, dt, price, cust, country = r[:8]
            w.writerow([txt(inv), txt(code), "" if desc is None else str(desc), int(qty), dt.strftime("%Y-%m-%d %H:%M:%S"),
                        repr(float(price)) if price is not None else "", "" if cust is None else int(cust), txt(country)])
            n += 1
    tmp.rename(dst)
    print(f"wrote {dst.name}: {n:,} rows")
print(f"{dst.name} {dst.stat().st_size:,} bytes")
