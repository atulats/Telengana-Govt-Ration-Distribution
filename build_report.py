"""Create a polished, self-contained PDF report from processed artifacts."""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE = landscape(A4)
W, H = PAGE
M = 42
NAVY = HexColor("#143642")
GREEN = HexColor("#2D6A4F")
MINT = HexColor("#DDEFE5")
ORANGE = HexColor("#E67E22")
GOLD = HexColor("#F4B942")
INK = HexColor("#213547")
MUTED = HexColor("#657786")
LIGHT = HexColor("#F4F7F5")
GRID = HexColor("#D6E0DC")
RED = HexColor("#B23A48")
CLUSTER_COLORS = [HexColor(x) for x in ["#2D6A4F", "#40916C", "#E67E22", "#1D6996", "#8C6BB1"]]


def read_csv(name: str):
    with (ROOT / "data" / "processed" / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


summary = json.loads((ROOT / "data" / "processed" / "model_summary.json").read_text(encoding="utf-8"))
profiles = read_csv("cluster_profiles.csv")
k_scores = read_csv("kmeans_evaluation.csv")
statewide = read_csv("statewide_monthly.csv")
district_year = read_csv("district_year_summary.csv")


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paragraph(c, text, x, y, width, size=10, leading=14, color=INK, font="Helvetica", max_lines=None):
    c.setFont(font, size)
    c.setFillColor(color)
    lines = wrap(text, font, size, width)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def header(c, page_no, title, kicker="TELANGANA PDS ANALYTICS"):
    c.setFillColor(NAVY)
    c.rect(0, H - 54, W, 54, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, H - 57, W, 3, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(M, H - 22, kicker)
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(white)
    c.drawString(M, H - 43, title)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawRightString(W - M, 20, f"Capstone report  |  page {page_no}")


def card(c, x, y, w, h, value, label, color=GREEN):
    c.setFillColor(LIGHT)
    c.roundRect(x, y, w, h, 8, fill=1, stroke=0)
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x + 14, y + h - 27, value)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 14, y + 12, label.upper())


def section(c, text, x, y):
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, text)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(x, y - 5, x + 44, y - 5)


def bullet(c, text, x, y, width, color=INK):
    c.setFillColor(ORANGE)
    c.circle(x + 3, y + 3, 2.5, fill=1, stroke=0)
    return paragraph(c, text, x + 14, y, width - 14, 9.5, 13, color)


def line_chart(c, rows, x, y, w, h):
    values = [float(r["transactions"]) / 1_000_000 for r in rows]
    ports = [float(r["portability_transactions"]) / 1_000_000 for r in rows]
    vmax = math.ceil(max(values))
    c.setStrokeColor(GRID)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    for tick in range(0, vmax + 1, 2):
        py = y + (tick / vmax) * h
        c.line(x, py, x + w, py)
        c.drawRightString(x - 6, py - 2, str(tick))
    def draw(series, color):
        c.setStrokeColor(color)
        c.setLineWidth(2)
        points = []
        for i, val in enumerate(series):
            px = x + (i / (len(series) - 1)) * w
            py = y + (val / vmax) * h
            points.append((px, py))
        for a, b in zip(points, points[1:]):
            c.line(a[0], a[1], b[0], b[1])
        for px, py in points:
            c.circle(px, py, 1.7, fill=1, stroke=0)
    draw(values, GREEN)
    draw(ports, ORANGE)
    for idx in [0, 11, 23, len(rows) - 1]:
        r = rows[idx]
        px = x + (idx / (len(rows) - 1)) * w
        c.setFillColor(MUTED)
        c.drawCentredString(px, y - 14, r["date"][:7])
    c.setFillColor(GREEN); c.rect(x + w - 150, y + h + 10, 10, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.drawString(x + w - 136, y + h + 7, "All transactions")
    c.setFillColor(ORANGE); c.rect(x + w - 72, y + h + 10, 10, 3, fill=1, stroke=0)
    c.setFillColor(INK); c.drawString(x + w - 58, y + h + 7, "Portable")


def bar_chart(c, labels, values, x, y, w, h, color=GREEN, percent=False):
    vmax = max(values) if values else 1
    bar_h = h / len(values) * 0.58
    gap = h / len(values)
    c.setFont("Helvetica", 8)
    for i, (label, value) in enumerate(zip(labels, values)):
        py = y + h - (i + 1) * gap + 4
        c.setFillColor(MUTED)
        c.drawRightString(x - 8, py + bar_h / 2 - 3, label)
        c.setFillColor(LIGHT)
        c.roundRect(x, py, w, bar_h, 3, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(x, py, max(2, w * value / vmax), bar_h, 3, fill=1, stroke=0)
        c.setFillColor(INK)
        fmt = f"{value:.1%}" if percent else f"{value:.3f}"
        c.drawString(x + min(w * value / vmax + 6, w - 28), py + bar_h / 2 - 3, fmt)


def page1(c):
    c.setFillColor(NAVY); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(GOLD); c.rect(M, H - 92, 56, 4, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9); c.drawString(M, H - 70, "CAPSTONE ANALYTICS SOLUTION")
    c.setFillColor(white); c.setFont("Helvetica-Bold", 30)
    c.drawString(M, H - 135, "Telangana Public Distribution System")
    c.setFont("Helvetica-Bold", 25); c.setFillColor(MINT)
    c.drawString(M, H - 170, "Fair Price Shop personas & anomaly screening")
    paragraph(c, "Official shop transactions, card entitlements, portability activity, and geospatial data translated into operational peer groups and review signals.", M, H - 207, 690, 12, 17, white)
    vals = [("17,491", "shops"), ("499,648", "shop-months"), ("33", "districts"), ("5", "personas")]
    for i, (v, l) in enumerate(vals):
        x = M + i * 185
        c.setFillColor(Color(1, 1, 1, alpha=0.09)); c.roundRect(x, 250, 165, 78, 10, fill=1, stroke=0)
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 24); c.drawString(x + 14, 289, v)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 8); c.drawString(x + 14, 266, l.upper())
    c.setFillColor(white); c.setFont("Helvetica-Bold", 13); c.drawString(M, 210, "Decision headline")
    paragraph(c, "Portability demand is growing faster than total transactions. Hyderabad, Medchal, and Ranga Reddy need mobility-aware replenishment, while 185 density outliers warrant evidence-led review—not automatic enforcement.", M, 185, 720, 12, 18, MINT)
    c.setFillColor(GOLD); c.setFont("Helvetica", 9); c.drawString(M, 42, "Analysis window: January 2023–May 2025  |  Official Telangana Open Data")


def page2(c):
    header(c, 2, "Problem, sources, and data quality")
    section(c, "Problem statement", M, H - 87)
    paragraph(c, "Segment Fair Price Shops into 4–5 interpretable operating personas, expose portability and distribution patterns, and prioritize shops whose behavior differs from comparable peers. The solution must remain explainable, reproducible, and safe for public-sector decision support.", M, H - 110, 748, 10, 14)
    section(c, "Official source integration", M, H - 175)
    labels = ["Monthly transactions", "Monthly card status", "FPS location register"]
    details = ["29 files | Jan 2023–May 2025", "30 files | Jan 2023–Jun 2025", "Latest file | 4 Jul 2025"]
    for i, (label, detail) in enumerate(zip(labels, details)):
        x = M + i * 250
        c.setFillColor(LIGHT); c.roundRect(x, 330, 228, 78, 8, fill=1, stroke=0)
        c.setFillColor(GREEN); c.setFont("Helvetica-Bold", 11); c.drawString(x + 14, 380, label)
        c.setFillColor(MUTED); c.setFont("Helvetica", 9); c.drawString(x + 14, 359, detail)
        c.setFillColor(ORANGE); c.setFont("Helvetica-Bold", 8); c.drawString(x + 14, 340, "OFFICIAL TELANGANA OPEN DATA")
    section(c, "ELT and validation flow", M, 298)
    flow = ["Download metadata + CSVs", "Normalize IDs and numerics", "Aggregate duplicate keys", "Join time-aligned sources", "Engineer + standardize features"]
    for i, label in enumerate(flow):
        x = M + i * 151
        c.setFillColor(MINT if i % 2 == 0 else LIGHT); c.roundRect(x, 232, 132, 42, 7, fill=1, stroke=0)
        paragraph(c, label, x + 9, 257, 114, 8, 10, INK, "Helvetica-Bold", 2)
        if i < len(flow) - 1:
            c.setStrokeColor(ORANGE); c.setLineWidth(2); c.line(x + 135, 253, x + 148, 253)
    q = summary["data_quality"]
    section(c, "Quality facts", M, 195)
    facts = [("Raw transaction rows", f"{q['transaction_rows_raw']:,}"), ("Duplicate transaction keys", str(q['transaction_duplicate_keys'])), ("Duplicate card keys", str(q['card_duplicate_keys'])), ("Unmatched card rows", f"{q['unmatched_card_rows']:,}"), ("Unmatched location rows", f"{q['unmatched_location_rows']:,}")]
    for i, (label, value) in enumerate(facts):
        x = M + i * 151
        card(c, x, 88, 132, 76, value, label, GREEN if i < 3 else ORANGE)
    paragraph(c, "Location gaps affect maps but not the transaction clustering. All unmatched counts remain visible rather than being silently discarded.", M, 62, 748, 8.5, 11, MUTED)


def page3(c):
    header(c, 3, "Exploratory analysis: volume, utilization, and portability")
    section(c, "Statewide monthly pattern", M, H - 88)
    line_chart(c, statewide, 82, 275, 690, 190)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8); c.drawString(82, 250, "Millions of transactions per month")
    jan_may = []
    for year in [2023, 2024, 2025]:
        rows = [r for r in statewide if int(r["year"]) == year and int(r["month"]) <= 5]
        tx = sum(float(r["transactions"]) for r in rows)
        pt = sum(float(r["portability_transactions"]) for r in rows)
        cards = sum(float(r["eligible_cards"]) for r in rows)
        jan_may.append((year, tx, pt, tx / cards, pt / tx))
    section(c, "Like-for-like January–May", M, 220)
    for i, row in enumerate(jan_may):
        year, tx, pt, util, share = row
        x = M + i * 250
        c.setFillColor(LIGHT); c.roundRect(x, 95, 228, 100, 8, fill=1, stroke=0)
        c.setFillColor(GREEN); c.setFont("Helvetica-Bold", 16); c.drawString(x + 14, 168, str(year))
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 10); c.drawString(x + 14, 143, f"{tx/1e6:.2f}M transactions")
        c.setFont("Helvetica", 9); c.drawString(x + 14, 124, f"Portability: {pt/1e6:.2f}M ({share:.1%})")
        c.drawString(x + 14, 107, f"Utilization: {util:.1%}")
    paragraph(c, "Total transactions grew about 2.5% in both comparisons, while portability transactions grew 7.6% and 8.2%. The evidence supports a rising portability trend, not a causal ONORC estimate.", M, 66, 748, 9, 12, MUTED)


def page4(c):
    header(c, 4, "Model design and validation")
    section(c, "Feature space", M, H - 88)
    features = ["Log transaction volume", "Log card base", "Utilization ratio", "Portability share", "Transaction volatility", "Rice intensity", "Wheat intensity", "Normalized trend"]
    for i, feature in enumerate(features):
        x = M + (i % 4) * 190; y = 438 - (i // 4) * 44
        c.setFillColor(MINT); c.roundRect(x, y, 172, 31, 6, fill=1, stroke=0)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 8.5); c.drawString(x + 10, y + 11, feature)
    section(c, "K-Means silhouette by k", M, 375)
    labels = [r["k"] for r in k_scores]
    vals = [float(r["silhouette"]) for r in k_scores]
    bar_chart(c, labels, vals, 95, 118, 250, 220, GREEN)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8); c.drawString(95, 99, "Final k is restricted to 4–5 by the project brief; k=5 performs better.")
    section(c, "Validation facts", 420, 375)
    facts = [("Selected personas", "5"), ("Silhouette score", "0.2172"), ("PCA 2D variance", "53.4%"), ("DBSCAN noise", "185 shops"), ("Noise rate", "1.06%"), ("Kruskal–Wallis", "H = 11,052.9")]
    for i, (label, value) in enumerate(facts):
        x = 420 + (i % 2) * 185; y = 272 - (i // 2) * 76
        card(c, x, y, 165, 60, value, label, CLUSTER_COLORS[i % 5])
    paragraph(c, "Interpretation: the moderate silhouette shows useful but overlapping operating patterns. PCA visualizes structure; DBSCAN supplies an independent density-based screen. The non-parametric test confirms distributional differences without assuming normality.", 420, 100, 350, 9, 13, MUTED)


def page5(c):
    header(c, 5, "Five operational personas")
    headings = ["Persona", "Shops", "Avg tx/mo", "Utilization", "Portability", "Volatility", "Operational use"]
    xs = [M, 270, 330, 410, 495, 585, 670]
    c.setFillColor(NAVY); c.rect(M, 476, W - 2*M, 30, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 8)
    for x, h in zip(xs, headings): c.drawString(x + 5, 487, h)
    actions = {
        "High-throughput anchors": "Protect uptime and queue capacity",
        "Low-volume local shops": "Right-size stock to local demand",
        "Volatile watchlist": "Review first; validate local causes",
        "Portability hubs": "Use mobility-aware buffer stock",
        "High-utilization shops": "Use as stable peer benchmark",
    }
    for i, r in enumerate(profiles):
        y = 410 - i * 76
        c.setFillColor(LIGHT if i % 2 == 0 else white); c.rect(M, y, W - 2*M, 68, fill=1, stroke=0)
        c.setFillColor(CLUSTER_COLORS[i]); c.rect(M, y, 6, 68, fill=1, stroke=0)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 9); c.drawString(M + 14, y + 40, r["persona"])
        c.setFont("Helvetica", 8)
        vals = [f"{int(float(r['shops'])):,}", f"{float(r['avg_monthly_transactions']):,.0f}", f"{float(r['utilization_ratio']):.1%}", f"{float(r['portability_share']):.1%}", f"{float(r['transaction_cv']):.3f}"]
        for x, v in zip(xs[1:6], vals): c.drawString(x + 5, y + 40, v)
        paragraph(c, actions[r["persona"]], xs[6] + 5, y + 47, 120, 7.7, 10, INK, max_lines=3)
        c.setFillColor(MUTED); c.setFont("Helvetica", 7.5); c.drawString(M + 14, y + 18, f"Cluster {r['cluster_id']}  |  DBSCAN noise rate {float(r['noise_rate']):.1%}")
    paragraph(c, "Persona labels describe relative operating behavior, not service quality or wrongdoing. Benchmark shops against their own persona before escalation.", M, 44, 748, 9, 12, MUTED)


def page6(c):
    header(c, 6, "Anomaly screening and business solution")
    section(c, "Evidence-led anomaly workflow", M, H - 88)
    steps = [("1", "Screen", "Risk percentiles + DBSCAN"), ("2", "Compare", "Shop versus persona peers"), ("3", "Validate", "Stock, authentication, closures"), ("4", "Act", "Support, audit, or clear flag")]
    for i, (n, title, desc) in enumerate(steps):
        x = M + i * 190
        c.setFillColor(LIGHT); c.roundRect(x, 382, 172, 80, 8, fill=1, stroke=0)
        c.setFillColor(ORANGE); c.circle(x + 23, 423, 13, fill=1, stroke=0)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 10); c.drawCentredString(x + 23, 419, n)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 11); c.drawString(x + 44, 430, title)
        paragraph(c, desc, x + 44, 412, 115, 8, 10, MUTED, max_lines=2)
    section(c, "Priority district context", M, 348)
    agg = {}
    for r in district_year:
        name = r["distName"]
        d = agg.setdefault(name, [0.0, 0.0, 0.0, set()])
        d[0] += float(r["transactions"]); d[1] += float(r["portability_transactions"]); d[2] += float(r["shops"]); d[3].add(r["year"])
    ranked = sorted(((k, v[1]/v[0], v[0]) for k, v in agg.items() if v[2]/len(v[3]) >= 50), key=lambda z: z[1], reverse=True)[:6]
    bar_chart(c, [r[0] for r in ranked], [r[1] for r in ranked], 145, 112, 245, 205, ORANGE, True)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8); c.drawString(145, 92, "Portability share across the analysis window")
    section(c, "Recommended actions", 455, 348)
    y = 320
    items = [
        "Increase replenishment buffers and peak-day staffing for portability hubs.",
        "Protect device/network uptime at high-throughput anchors.",
        "Use stable high-utilization shops as district-level peer benchmarks.",
        "Review volatile or DBSCAN-noise shops with local records before enforcement.",
        "Refresh models monthly and monitor persona migration, not only static flags.",
    ]
    for item in items: y = bullet(c, item, 455, y, 330) - 9
    c.setFillColor(HexColor("#FFF4E8")); c.roundRect(455, 88, 330, 58, 8, fill=1, stroke=0)
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 9); c.drawString(469, 125, "SAFE USE")
    paragraph(c, "Anomaly scores are triage signals—not proof of fraud. Keep a documented human review step.", 469, 108, 300, 8.5, 11, INK)


def page7(c):
    header(c, 7, "Conclusion, limitations, and reproducibility")
    section(c, "Conclusion", M, H - 88)
    paragraph(c, "The combined data and modeling workflow turns nearly half a million shop-month records into five interpretable personas, a 185-shop density-outlier list, and an interactive monitoring tool. The strongest operating signal is growing portable demand concentrated in major urban districts; the most important governance principle is to investigate anomalies in context.", M, H - 112, 748, 10.5, 15)
    section(c, "Limits that change interpretation", M, 414)
    y = 389
    for item in [
        "No urban/rural field exists in the supplied sources; urban/rural purity is not computable.",
        "The data starts after ONORC implementation; policy causality is not claimed.",
        "A moderate silhouette score means persona boundaries overlap.",
        "Location gaps reduce mapped coverage but do not remove transaction observations.",
        "Cluster IDs may change after retraining; retain feature definitions and persona rules.",
    ]: y = bullet(c, item, M, y, 360) - 7
    section(c, "Capstone guideline coverage", 435, 414)
    mapping = ["Domain + project introduction", "Objective + problem statement", "ELT + cleaning + preprocessing", "EDA + statistical technique", "Model building + evaluation", "Conclusion + business solution"]
    for i, item in enumerate(mapping):
        c.setFillColor(MINT); c.roundRect(435, 365 - i*43, 340, 30, 6, fill=1, stroke=0)
        c.setFillColor(GREEN); c.setFont("Helvetica-Bold", 8); c.drawString(447, 376 - i*43, f"{i+1:02d}")
        c.setFillColor(INK); c.drawString(477, 376 - i*43, item)
    section(c, "Reproduce", M, 150)
    commands = ["python download_data.py", "python build_artifacts.py", "python create_notebook.py", "streamlit run streamlit_app.py"]
    c.setFillColor(NAVY); c.roundRect(M, 48, 733, 78, 8, fill=1, stroke=0)
    c.setFillColor(MINT); c.setFont("Courier", 9)
    for i, cmd in enumerate(commands): c.drawString(M + 16 + (i % 2)*360, 98 - (i//2)*28, cmd)
    c.setFillColor(MUTED); c.setFont("Helvetica", 7.5); c.drawString(M, 31, "Sources: Telangana Open Data Portal datasets named in the project brief. Open Government License – India.")


def main() -> None:
    output = ROOT / "output" / "pdf" / "telangana_pds_cluster_report.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=PAGE)
    c.setTitle("Telangana PDS Fair Price Shop analytics")
    for fn in [page1, page2, page3, page4, page5, page6, page7]:
        fn(c); c.showPage()
    c.save()
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
