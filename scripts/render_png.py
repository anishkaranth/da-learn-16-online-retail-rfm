#!/usr/bin/env python3
"""Render every results/images/*.svg (and results/sample/images if present) to a PNG next to it with headless Chrome.

The SVGs are written by run_pipeline.py from plain vector shapes; this only rasterises them at 2x for README/preview use.
Needs google-chrome or chromium on PATH (set CHROME=/path/to/chrome to override)."""
import os, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
chrome = os.environ.get("CHROME") or next((shutil.which(c) for c in ["google-chrome", "chromium", "chromium-browser"] if shutil.which(c)), None)
if not chrome:
    sys.exit("no Chrome/Chromium found; set CHROME=...")
dirs = [ROOT / "results/images"] + ([ROOT / "results/sample/images"] if "--sample" in sys.argv else [])
for d in dirs:
    for svg in sorted(d.glob("*.svg")):
        head = svg.read_text()[:400]
        w, h = (int(float(x)) for x in re.search(r'width="([\d.]+)" height="([\d.]+)"', head).groups())
        png = svg.with_suffix(".png")
        with tempfile.TemporaryDirectory() as prof:
            subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                            "--force-device-scale-factor=2", f"--window-size={w},{h}", f"--screenshot={png}", svg.as_uri()],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        print(f"{png.relative_to(ROOT)}  ({w}x{h} @2x, {png.stat().st_size:,} B)")
