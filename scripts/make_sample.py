#!/usr/bin/env python3
"""Build the reproducible raw sample data/raw/online_retail.csv from data/raw_full/online_retail.csv.

Rule (deterministic, no randomness); lines are copied byte-for-byte from the full CSV, in the original order:
  * every line of identified customers with zlib.crc32(CustomerID) % 20 = 0        (~5% of customers, complete histories,
    so RFM scores and cohort retention work on the sample)
  * every line of guest invoices (no CustomerID) with zlib.crc32(InvoiceNo) % 40 = 0  (~2.5% of guest baskets)
  * the complete history of customers 12346 and 16446 (the two largest lines in the file, 74,215 and 80,995 units,
    each cancelled minutes later by a credit note - the reversal rule in sql/02)
  * the first 3 examples of every other cleaning rule: exact duplicate lines (both copies), bad-debt 'A' invoices,
    each non-product stock code (POST, DOT, M, C2, D, S, B, BANK CHARGES, AMAZONFEE, PADS, CRUK, gift vouchers),
    unit price 0, quantity <= 0 on a non-C invoice, missing Description, and each non-standard country label.
"""
import collections, csv, io, pathlib, zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAME = "online_retail.csv"
src, dst = ROOT / "data/raw_full" / NAME, ROOT / "data/raw" / NAME
lines = src.read_bytes().split(b"\n")
if lines[-1] == b"":
    lines = lines[:-1]
head, body = lines[0], lines[1:]
rows = list(csv.reader(io.StringIO(b"\n".join(body).decode("utf-8"))))
assert len(rows) == len(body)
NONPROD = {"POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES", "AMAZONFEE", "PADS", "CRUK"}
copies = collections.Counter(tuple(r) for r in rows)
dup_examples = set(list(dict.fromkeys(tuple(r) for r in rows if copies[tuple(r)] > 1))[:3])   # first 3 duplicated lines
seen = collections.Counter()


def example(kind, limit=3):
    seen[kind] += 1
    return seen[kind] <= limit


keep = []
for line, r in zip(body, rows):
    inv, code, desc, qty, dt, price, cust, country = r
    code_u = code.strip().upper()
    k = False
    if cust:
        k = zlib.crc32(cust.encode()) % 20 == 0 or cust in ("12346", "16446")
    else:
        k = zlib.crc32(inv.encode()) % 40 == 0
    if tuple(r) in dup_examples:
        k = True
    if inv.startswith("A") or (code_u in NONPROD and example(code_u)) or (code_u.startswith("GIFT_") and example("gift")):
        k = True
    if (float(price) == 0 and example("price0")) or (int(qty) <= 0 and not inv.startswith("C") and example("qty0")):
        k = True
    if desc == "" and example("nodesc"):
        k = True
    if country in ("EIRE", "RSA", "USA", "Unspecified") and example(country):
        k = True
    if k:
        keep.append(line)
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_bytes(b"\n".join([head] + keep) + b"\n")
print(f"{dst.relative_to(ROOT)}: {len(keep):,d} of {len(body):,d} lines, {dst.stat().st_size:,d} B")
