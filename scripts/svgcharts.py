#!/usr/bin/env python3
"""Tiny pure-vector SVG chart helpers (rect / line / polyline / circle / text only - no raster, no fonts embedded).

Every chart function returns a Panel(width, height, body). `save()` writes one panel as a standalone SVG,
`dashboard()` tiles KPI cards + panels into one multi-panel SVG.
"""
from dataclasses import dataclass
from xml.sax.saxutils import escape

PALETTE = ["#1f6f8b", "#e07a5f", "#81b29a", "#f2cc8f", "#3d405b", "#9c6644", "#6d597a", "#b56576"]
W, H = 640, 360


@dataclass
class Panel:
    w: int
    h: int
    body: str


def _t(x, y, s, size=11, anchor="start", fill="#333", weight=None, rot=None):
    a = f' font-weight="{weight}"' if weight else ""
    r = f' transform="rotate({rot} {x:.0f} {y:.0f})"' if rot is not None else ""
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"{a}{r}>{escape(str(s))}</text>'


def _nice_max(v):
    if v <= 0:
        return 1
    import math
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def _fmt(v, fmt):
    return fmt.format(v) if fmt else f"{v:,.4g}"


def _head(title, subtitle):
    s = _t(12, 22, title, 14, weight="bold", fill="#222")
    if subtitle:
        s += _t(12, 39, subtitle, 10, fill="#777")
    return s


def hbar(title, labels, values, fmt="{:.1f}", subtitle=None, color=None, notes=None, w=W, h=None, xlabel=None, vmax=None):
    """Horizontal bars, first label at the top."""
    if not labels: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    n = len(labels)
    h = h or max(140, 60 + 24 * n + 20)
    lw = min(230, 12 + 6.2 * max((len(str(l)) for l in labels), default=0))
    x0, x1, y0 = lw + 8, w - 70, 52
    bh = (h - y0 - 26) / max(n, 1)
    vmax = vmax or _nice_max(max(values) if values else 1)
    out = [_head(title, subtitle)]
    for i, (l, v) in enumerate(zip(labels, values)):
        y = y0 + i * bh
        bw = max(0, (x1 - x0) * v / vmax)
        c = color[i % len(color)] if isinstance(color, list) else (color or PALETTE[0])
        out.append(f'<rect x="{x0:.0f}" y="{y + bh * .15:.1f}" width="{bw:.1f}" height="{bh * .7:.1f}" fill="{c}"/>')
        out.append(_t(x0 - 6, y + bh * .5 + 4, l, 10, "end"))
        lab = _fmt(v, fmt) + (f"  {notes[i]}" if notes else "")
        out.append(_t(x0 + bw + 4, y + bh * .5 + 4, lab, 9, fill="#444"))
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + n * bh:.0f}" stroke="#999"/>')
    if xlabel:
        out.append(_t((x0 + x1) / 2, h - 6, xlabel, 10, "middle", "#666"))
    return Panel(w, int(h), "".join(out))


def vbar(title, labels, values, fmt="{:.1f}", subtitle=None, color=None, w=W, h=H, ylabel=None, rotate=False, notes=None, vmax=None):
    if not labels: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    n = len(labels)
    x0, x1, y0, y1 = 56, w - 16, 56, h - (78 if rotate else 46)
    vmax = vmax or _nice_max(max(values) if values else 1)
    out = [_head(title, subtitle)]
    for k in range(5):
        gv = vmax * k / 4
        gy = y1 - (y1 - y0) * k / 4
        out.append(f'<line x1="{x0}" y1="{gy:.0f}" x2="{x1}" y2="{gy:.0f}" stroke="#eee"/>')
        out.append(_t(x0 - 4, gy + 3, _fmt(gv, "{:,.4g}"), 9, "end", "#777"))
    bw = (x1 - x0) / max(n, 1)
    for i, (l, v) in enumerate(zip(labels, values)):
        x = x0 + i * bw
        bhh = (y1 - y0) * max(v, 0) / vmax
        c = color[i % len(color)] if isinstance(color, list) else (color or PALETTE[0])
        out.append(f'<rect x="{x + bw * .15:.1f}" y="{y1 - bhh:.1f}" width="{bw * .7:.1f}" height="{bhh:.1f}" fill="{c}"/>')
        out.append(_t(x + bw / 2, y1 - bhh - 4, _fmt(v, fmt), 9, "middle", "#444"))
        if notes:
            out.append(_t(x + bw / 2, y1 - bhh - 15, notes[i], 8, "middle", "#888"))
        if rotate:
            out.append(_t(x + bw / 2 + 3, y1 + 10, l, 9, "end", rot=-35))
        else:
            out.append(_t(x + bw / 2, y1 + 14, l, 9, "middle"))
    out.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#999"/>')
    if ylabel:
        out.append(_t(14, (y0 + y1) / 2, ylabel, 10, "middle", "#666", rot=-90))
    return Panel(w, h, "".join(out))


def line(title, xs, series, fmt="{:,.4g}", subtitle=None, w=W, h=H, ylabel=None, xlabel=None, ymin=None, every=None):
    """series: list of (name, values) sharing xs (categorical labels, equally spaced)."""
    if not xs: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    x0, x1, y0, y1 = 60, w - 18, 56, h - 46
    allv = [v for _, vs in series for v in vs if v is not None]
    lo = ymin if ymin is not None else min(0, min(allv))
    hi = _nice_max(max(allv)) if lo == 0 else max(allv) + (max(allv) - lo) * .08
    if lo != 0 and ymin is None:
        lo = min(allv) - (max(allv) - min(allv)) * .08
    span = (hi - lo) or 1
    out = [_head(title, subtitle)]
    for k in range(5):
        gv = lo + span * k / 4
        gy = y1 - (y1 - y0) * k / 4
        out.append(f'<line x1="{x0}" y1="{gy:.0f}" x2="{x1}" y2="{gy:.0f}" stroke="#eee"/>')
        out.append(_t(x0 - 4, gy + 3, _fmt(gv, fmt), 9, "end", "#777"))
    n = len(xs)
    px = lambda i: x0 + (x1 - x0) * (i / max(n - 1, 1))
    py = lambda v: y1 - (y1 - y0) * (v - lo) / span
    every = every or max(1, n // 10)
    for i, xl in enumerate(xs):
        if i % every == 0 or i == n - 1:
            out.append(_t(px(i), y1 + 14, xl, 9, "middle"))
    for si, (name, vs) in enumerate(series):
        c = PALETTE[si % len(PALETTE)]
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vs) if v is not None)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>')
        if len(series) > 1:
            lx = x0 + 10 + si * 120
            out.append(f'<rect x="{lx}" y="{h - 16}" width="10" height="10" fill="{c}"/>' + _t(lx + 14, h - 7, name, 9))
    out.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#999"/>')
    if ylabel:
        out.append(_t(14, (y0 + y1) / 2, ylabel, 10, "middle", "#666", rot=-90))
    if xlabel and len(series) <= 1:
        out.append(_t((x0 + x1) / 2, h - 6, xlabel, 10, "middle", "#666"))
    return Panel(w, h, "".join(out))


def grouped_vbar(title, labels, groups, fmt="{:.1f}", subtitle=None, w=W, h=H, ylabel=None):
    """groups: list of (name, values) - clustered bars per label."""
    if not labels or not groups: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    x0, x1, y0, y1 = 56, w - 16, 56, h - 50
    vmax = _nice_max(max((v for _, vs in groups for v in vs), default=1))
    out = [_head(title, subtitle)]
    for k in range(5):
        gv = vmax * k / 4; gy = y1 - (y1 - y0) * k / 4
        out.append(f'<line x1="{x0}" y1="{gy:.0f}" x2="{x1}" y2="{gy:.0f}" stroke="#eee"/>' + _t(x0 - 4, gy + 3, _fmt(gv, "{:,.4g}"), 9, "end", "#777"))
    n, g = len(labels), len(groups)
    bw = (x1 - x0) / max(n, 1)
    for i, l in enumerate(labels):
        for j, (_, vs) in enumerate(groups):
            v = vs[i]; bhh = (y1 - y0) * max(v, 0) / vmax
            x = x0 + i * bw + bw * .1 + j * bw * .8 / g
            out.append(f'<rect x="{x:.1f}" y="{y1 - bhh:.1f}" width="{bw * .8 / g:.1f}" height="{bhh:.1f}" fill="{PALETTE[j % 8]}"/>')
            out.append(_t(x + bw * .4 / g, y1 - bhh - 3, _fmt(v, fmt), 8, "middle", "#444"))
        out.append(_t(x0 + i * bw + bw / 2, y1 + 14, l, 9, "middle"))
    for j, (name, _) in enumerate(groups):
        lx = x0 + 10 + j * min(130, (x1 - x0 - 20) // max(g, 1))
        out.append(f'<rect x="{lx}" y="{h - 18}" width="10" height="10" fill="{PALETTE[j % 8]}"/>' + _t(lx + 14, h - 9, name, 9))
    out.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#999"/>')
    if ylabel:
        out.append(_t(14, (y0 + y1) / 2, ylabel, 10, "middle", "#666", rot=-90))
    return Panel(w, h, "".join(out))


def dbar(title, labels, values, fmt="{:+.3f}", subtitle=None, w=W, h=None, xlabel=None, pos_color=None, neg_color=None):
    """Diverging horizontal bars around zero (negative = left, coloured differently)."""
    if not labels: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    n = len(labels)
    h = h or max(140, 60 + 24 * n + 20)
    lw = min(230, 12 + 6.2 * max((len(str(l)) for l in labels), default=0))
    x0, x1, y0 = lw + 8, w - 20, 52
    bh = (h - y0 - 26) / max(n, 1)
    vmax = _nice_max(max(abs(v) for v in values) if values else 1)
    xm = (x0 + x1) / 2
    half = (x1 - x0) / 2 - 40
    out = [_head(title, subtitle)]
    for i, (l, v) in enumerate(zip(labels, values)):
        y = y0 + i * bh
        bw = half * abs(v) / vmax
        bx = xm if v >= 0 else xm - bw
        c = (pos_color or PALETTE[0]) if v >= 0 else (neg_color or PALETTE[1])
        out.append(f'<rect x="{bx:.1f}" y="{y + bh * .15:.1f}" width="{bw:.1f}" height="{bh * .7:.1f}" fill="{c}"/>')
        out.append(_t(x0 - 6, y + bh * .5 + 4, l, 10, "end"))
        tx = xm + bw + 4 if v >= 0 else xm - bw - 4
        out.append(_t(tx, y + bh * .5 + 4, _fmt(v, fmt), 9, "start" if v >= 0 else "end", "#444"))
    out.append(f'<line x1="{xm:.0f}" y1="{y0}" x2="{xm:.0f}" y2="{y0 + n * bh:.0f}" stroke="#999"/>')
    if xlabel:
        out.append(_t((x0 + x1) / 2, h - 6, xlabel, 10, "middle", "#666"))
    return Panel(w, int(h), "".join(out))


def _mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def heatmap(title, rows, cols, values, fmt="{:.0f}", subtitle=None, w=W, h=None, lo_color="#f4f8fb", hi_color="#1f6f8b",
            vmin=None, vmax=None, xlabel=None, ylabel=None, cell_text=True, notes=None):
    """values[i][j] for row label i and column label j (None = empty cell). Colour scales linearly vmin..vmax."""
    if not rows or not cols: return Panel(W, 80, _t(16, 40, title + " (no data)", 12))
    lw = min(150, 14 + 6.2 * max(len(str(r)) for r in rows))
    x0, y0 = lw + 8, 56
    h = h or max(160, y0 + 22 * len(rows) + 44)
    x1, y1 = w - 16, h - (34 if xlabel else 22)
    cw, ch = (x1 - x0) / len(cols), (y1 - y0) / len(rows)
    flat = [v for r in values for v in r if v is not None]
    lo = min(flat) if vmin is None else vmin
    hi = max(flat) if vmax is None else vmax
    span = (hi - lo) or 1
    out = [_head(title, subtitle)]
    for i, rl in enumerate(rows):
        out.append(_t(x0 - 6, y0 + i * ch + ch / 2 + 4, rl, 9, "end"))
        for j, _ in enumerate(cols):
            v = values[i][j]
            if v is None:
                continue
            t = max(0.0, min(1.0, (v - lo) / span))
            out.append(f'<rect x="{x0 + j * cw:.1f}" y="{y0 + i * ch:.1f}" width="{cw - 1:.1f}" height="{ch - 1:.1f}" fill="{_mix(lo_color, hi_color, t)}"/>')
            if cell_text and cw > 18:
                lab = notes[i][j] if notes else _fmt(v, fmt)
                out.append(_t(x0 + j * cw + cw / 2, y0 + i * ch + ch / 2 + 3, lab, 8 if cw < 40 else 9, "middle", "#fff" if t > 0.55 else "#333"))
    for j, cl in enumerate(cols):
        out.append(_t(x0 + j * cw + cw / 2, y1 + 12, cl, 9, "middle"))
    if xlabel:
        out.append(_t((x0 + x1) / 2, h - 6, xlabel, 10, "middle", "#666"))
    if ylabel:
        out.append(_t(12, (y0 + y1) / 2, ylabel, 10, "middle", "#666", rot=-90))
    return Panel(w, int(h), "".join(out))


def _wrap(p: Panel):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{p.w}" height="{p.h}" viewBox="0 0 {p.w} {p.h}" '
            f'font-family="Helvetica,Arial,sans-serif"><rect width="{p.w}" height="{p.h}" fill="#fff"/>{p.body}</svg>\n')


def save(p: Panel, path):
    open(path, "w", encoding="utf-8").write(_wrap(p))


def dashboard(path, title, subtitle, cards, panels, cols=2):
    """cards: list of (label, value_str); panels: list of Panel. Lays panels out in a grid."""
    pw = max((p.w for p in panels), default=W)
    W_ = cols * pw + (cols + 1) * 16
    top = 128
    rows = [panels[i:i + cols] for i in range(0, len(panels), cols)]
    H_ = top + sum(max((p.h for p in r), default=H) + 16 for r in rows) + 10
    out = [f'<rect width="{W_}" height="{H_}" fill="#f6f7f9"/>', _t(16, 30, title, 20, weight="bold", fill="#1f2d3d"),
           _t(16, 50, subtitle, 11, fill="#666")]
    cw = (W_ - 16 * (len(cards) + 1)) / max(len(cards), 1)
    for i, (lab, val) in enumerate(cards):
        x = 16 + i * (cw + 16)
        out.append(f'<rect x="{x:.0f}" y="64" width="{cw:.0f}" height="52" rx="6" fill="#fff" stroke="#dde"/>')
        out.append(_t(x + cw / 2, 91, val, 18, "middle", PALETTE[0], "bold"))
        out.append(_t(x + cw / 2, 108, lab, 10, "middle", "#666"))
    y = top
    for r in rows:
        for j, p in enumerate(r):
            x = 16 + j * (pw + 16)
            out.append(f'<g transform="translate({x},{y})"><rect width="{pw}" height="{p.h}" rx="6" fill="#fff" stroke="#dde"/>{p.body}</g>')
        y += max((p.h for p in r), default=H) + 16
    open(path, "w", encoding="utf-8").write(_wrap(Panel(W_, H_, "".join(out))))
