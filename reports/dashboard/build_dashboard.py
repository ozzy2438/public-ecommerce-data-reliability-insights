#!/usr/bin/env python3
"""Build the local, self-contained Phase 3 decision dashboard."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
KPI_PATH = ROOT / "reports" / "analysis" / "kpi_results.json"
QUALITY_PATH = ROOT / "reports" / "data_quality_report.md"
OUTPUT_PATH = ROOT / "reports" / "dashboard" / "index.html"

BG = "#0b1220"
CARD = "#111c2e"
GRID = "#2a3b55"
TEXT = "#e8eef7"
MUTED = "#91a4bd"
TEAL = "#4fd1c5"
YELLOW = "#f6c85f"
PINK = "#ff8fa3"
PURPLE = "#a78bfa"
GREEN = "#80d48c"


def reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def load_quality_counts(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"Summary:\s+\*\*(\d+) FAIL\*\*,\s+\*\*(\d+) WARN\*\*,\s+\*\*(\d+) PASS\*\*",
        text,
    )
    if not match:
        raise ValueError(f"could not parse quality summary from {path}")
    fail, warn, passed = (int(item) for item in match.groups())
    return {"PASS": passed, "WARN": warn, "FAIL": fail}


def validate_inputs(kpis: dict[str, Any], quality: dict[str, int]) -> None:
    required = {
        "total_revenue_gbp",
        "total_orders",
        "avg_order_value_gbp",
        "repeat_purchase_rate_pct",
        "returning_customer_revenue_pct",
        "returning_customer_revenue_gbp",
        "attributed_revenue_gbp",
        "guest_revenue_gbp",
        "guest_revenue_pct",
        "monthly_revenue",
        "top_10_products",
        "top_10_countries",
        "cancellation_rate_pct",
    }
    missing = sorted(required - kpis.keys())
    if missing:
        raise ValueError(f"KPI artifact is missing: {', '.join(missing)}")
    if len(kpis["monthly_revenue"]) < 2:
        raise ValueError("monthly_revenue must contain at least two months")
    if len(kpis["top_10_products"]) < 5 or len(kpis["top_10_countries"]) < 5:
        raise ValueError("KPI artifact must contain at least five products and countries")
    if sum(quality.values()) == 0:
        raise ValueError("quality summary is empty")

    # Guardrails prevent a local rebuild from silently drifting from the
    # accepted Phase 2 evidence chain.
    expected = {
        "total_revenue_gbp": 10642110.80,
        "total_orders": 19960,
        "returning_customer_revenue_pct": 93.09,
        "attributed_revenue_gbp": 8887208.89,
        "guest_revenue_gbp": 1754901.91,
        "guest_revenue_pct": 16.49,
    }
    for key, expected_value in expected.items():
        actual = kpis[key]
        if isinstance(expected_value, float):
            if not math.isclose(float(actual), expected_value, abs_tol=0.001):
                raise ValueError(f"accepted KPI changed for {key}: {actual!r}")
        elif actual != expected_value:
            raise ValueError(f"accepted KPI changed for {key}: {actual!r}")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def money(value: float) -> str:
    return f"£{float(value):,.2f}"


def pct(value: float, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}%"


def short_label(value: str, length: int = 30) -> str:
    value = " ".join(str(value).split())
    return value if len(value) <= length else value[: length - 1].rstrip() + "…"


def svg(title: str, body: str, height: int) -> str:
    return (
        f'<svg class="chart" role="img" aria-label="{esc(title)}" '
        f'viewBox="0 0 900 {height}" preserveAspectRatio="xMidYMid meet">'
        f"<title>{esc(title)}</title>{body}</svg>"
    )


def grid_lines(bottom: float, top: float, left: float, right: float, ticks: tuple[int, ...], maximum: float) -> str:
    output: list[str] = []
    for tick in ticks:
        y = bottom - (tick / maximum) * (bottom - top)
        output.append(
            f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" />'
            f'<text x="{left - 12:.1f}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="{MUTED}" font-size="12">{esc(money(tick))}</text>'
        )
    return "".join(output)


def monthly_revenue_chart(monthly: list[dict[str, Any]]) -> str:
    left, right, top, bottom = 80, 870, 28, 248
    values = [float(item["revenue_gbp"]) for item in monthly]
    maximum = max(values) * 1.12
    step = (right - left) / max(1, len(monthly) - 1)
    points = [
        (
            left + index * step,
            bottom - value / maximum * (bottom - top),
        )
        for index, value in enumerate(values)
    ]
    path = " ".join(
        ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    area = f"{path} L{right:.1f},{bottom:.1f} L{left:.1f},{bottom:.1f} Z"
    body = [
        grid_lines(bottom, top, left, right, (0, 400000, 800000, 1200000, 1600000), maximum),
        f'<path d="{area}" fill="{TEAL}" opacity="0.10" />',
        f'<path d="{path}" fill="none" stroke="{TEAL}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />',
    ]
    peak_index = values.index(max(values))
    for index, (item, (x, y)) in enumerate(zip(monthly, points)):
        color = YELLOW if index == peak_index else TEAL
        suffix = "*" if item["month"] == "2011-12" else ""
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" stroke="{BG}" stroke-width="3" />')
        body.append(
            f'<text x="{x:.1f}" y="{bottom + 28}" text-anchor="end" '
            f'transform="rotate(-38 {x:.1f} {bottom + 28})" fill="{MUTED}" font-size="12">'
            f'{esc(item["month"])}{suffix}</text>'
        )
    body.extend(
        [
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{GRID}" />',
            f'<text x="{right}" y="20" text-anchor="end" fill="{MUTED}" font-size="12">* partial month</text>',
        ]
    )
    return svg("Monthly valid revenue in GBP", "".join(body), 320)


def mom_chart(monthly: list[dict[str, Any]]) -> str:
    changes = monthly[1:]
    left, right, top, bottom, base = 72, 874, 26, 274, 150
    max_abs = max(abs(float(item["mom_growth_pct"])) for item in changes)
    scale = (base - top) / max_abs
    slot = (right - left) / len(changes)
    body = [
        f'<line x1="{left}" y1="{base}" x2="{right}" y2="{base}" stroke="{TEXT}" stroke-width="2" />',
        f'<text x="{left - 12}" y="{base + 4}" text-anchor="end" fill="{MUTED}" font-size="12">0%</text>',
    ]
    for tick in (-60, -30, 30, 60):
        y = base - tick * scale
        if top <= y <= bottom:
            body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{GRID}" />')
            body.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="{MUTED}" font-size="12">{tick}%</text>')
    for index, item in enumerate(changes):
        value = float(item["mom_growth_pct"])
        x = left + index * slot + slot * 0.20
        width = slot * 0.60
        y = base - value * scale if value >= 0 else base
        height = abs(value * scale)
        color = GREEN if value >= 0 else PINK
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="5" fill="{color}" opacity="0.90" />')
        label_y = y - 8 if value >= 0 else y + height + 18
        body.append(f'<text x="{x + width / 2:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="{TEXT}" font-size="11">{esc(pct(value))}</text>')
        body.append(f'<text x="{x + width / 2:.1f}" y="{bottom + 26}" text-anchor="middle" fill="{MUTED}" font-size="11">{esc(item["month"][-5:])}</text>')
    return svg("Month-over-month revenue change", "".join(body), 320)


def horizontal_bar_chart(
    title: str,
    rows: list[dict[str, Any]],
    label_key: str,
    value_key: str,
    value_formatter: Any,
    secondary_key: str | None = None,
) -> str:
    left, right, top, row_height = 275, 870, 30, 48
    values = [float(row[value_key]) for row in rows]
    maximum = max(values) * 1.12
    body = [
        f'<line x1="{left}" y1="{top - 8}" x2="{left}" y2="{top + row_height * len(rows) - 12}" stroke="{GRID}" />'
    ]
    for index, row in enumerate(rows):
        y = top + index * row_height
        label = short_label(str(row[label_key]))
        value = float(row[value_key])
        width = value / maximum * (right - left)
        secondary = f" · {row[secondary_key]:,} orders" if secondary_key else ""
        opacity = 1.0 - index * 0.08
        body.extend(
            [
                f'<text x="{left - 14}" y="{y + 22}" text-anchor="end" fill="{TEXT}" font-size="13">{esc(label)}</text>',
                f'<rect x="{left}" y="{y + 7}" width="{right - left}" height="24" rx="6" fill="{GRID}" opacity="0.55" />',
                f'<rect x="{left}" y="{y + 7}" width="{width:.1f}" height="24" rx="6" fill="{TEAL if index == 0 else PURPLE}" opacity="{opacity:.2f}" />',
                f'<text x="{min(left + width + 10, 770):.1f}" y="{y + 24}" fill="{TEXT}" font-size="12">{esc(value_formatter(value))}{esc(secondary)}</text>',
            ]
        )
    return svg(title, "".join(body), top + row_height * len(rows) + 18)


def revenue_mix_chart(kpis: dict[str, Any]) -> str:
    total = float(kpis["total_revenue_gbp"])
    returning = float(kpis["returning_customer_revenue_gbp"])
    attributed = float(kpis["attributed_revenue_gbp"])
    guest = float(kpis["guest_revenue_gbp"])
    parts = [
        ("Returning known-customer", returning, TEAL),
        ("Other attributed", attributed - returning, PURPLE),
        ("Guest", guest, YELLOW),
    ]
    left, top, width, height = 80, 92, 740, 58
    body = [
        f'<text x="{left}" y="38" fill="{TEXT}" font-size="16" font-weight="700">Valid revenue composition</text>',
        f'<text x="{left}" y="62" fill="{MUTED}" font-size="13">Returning share uses attributed revenue; guest revenue remains in total revenue.</text>',
    ]
    x = left
    for label, value, color in parts:
        segment_width = width * value / total
        body.append(f'<rect x="{x:.1f}" y="{top}" width="{segment_width:.1f}" height="{height}" fill="{color}" />')
        if segment_width > 85:
            body.append(f'<text x="{x + segment_width / 2:.1f}" y="{top + 34}" text-anchor="middle" fill="{BG}" font-size="12" font-weight="700">{pct(value / total * 100, 1)}</text>')
        x += segment_width
    for index, (label, value, color) in enumerate(parts):
        lx = left + index * 250
        body.extend(
            [
                f'<rect x="{lx}" y="183" width="12" height="12" rx="3" fill="{color}" />',
                f'<text x="{lx + 20}" y="194" fill="{TEXT}" font-size="12">{esc(label)}</text>',
                f'<text x="{lx + 20}" y="214" fill="{MUTED}" font-size="12">{esc(money(value))}</text>',
            ]
        )
    return svg("Revenue composition by customer attribution", "".join(body), 240)


def quality_chart(quality: dict[str, int]) -> str:
    rows = [("PASS", quality["PASS"], GREEN), ("WARN", quality["WARN"], YELLOW), ("FAIL", quality["FAIL"], PINK)]
    maximum = max(1, max(value for _, value, _ in rows))
    left, base, top = 150, 220, 38
    body = [
        f'<line x1="{left}" y1="{base}" x2="{left + 600}" y2="{base}" stroke="{GRID}" />',
        f'<text x="{left}" y="28" fill="{MUTED}" font-size="13">Automated checks in the accepted quality handoff</text>',
    ]
    bar_width = 120
    for index, (label, value, color) in enumerate(rows):
        x = left + 55 + index * 190
        height = (base - top) * value / maximum
        body.extend(
            [
                f'<rect x="{x}" y="{base - height:.1f}" width="{bar_width}" height="{height:.1f}" rx="8" fill="{color}" opacity="0.90" />',
                f'<text x="{x + bar_width / 2}" y="{base - height - 12:.1f}" text-anchor="middle" fill="{TEXT}" font-size="18" font-weight="700">{value}</text>',
                f'<text x="{x + bar_width / 2}" y="{base + 26}" text-anchor="middle" fill="{TEXT}" font-size="13">{label}</text>',
            ]
        )
    return svg("Data quality check status", "".join(body), 280)


def kpi_card(label: str, value: str, note: str) -> str:
    return f'<div class="kpi"><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{esc(value)}</div><div class="kpi-note">{esc(note)}</div></div>'


def render(kpis: dict[str, Any], quality: dict[str, int]) -> str:
    monthly = kpis["monthly_revenue"]
    products = kpis["top_10_products"][:5]
    countries = kpis["top_10_countries"][:5]
    peak = max(monthly, key=lambda item: float(item["revenue_gbp"]))
    style = f"""
:root {{ color-scheme: dark; --bg: {BG}; --card: {CARD}; --grid: {GRID}; --text: {TEXT}; --muted: {MUTED}; --teal: {TEAL}; --yellow: {YELLOW}; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1180px, calc(100% - 36px)); margin: 0 auto; }}
header {{ padding: 52px 0 28px; border-bottom: 1px solid var(--grid); }}
.eyebrow {{ color: var(--teal); text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 800; }}
h1 {{ margin: 8px 0 10px; font-size: clamp(30px, 5vw, 52px); line-height: 1.05; }}
.lede {{ max-width: 820px; color: var(--muted); font-size: 17px; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 10px 22px; color: var(--muted); font-size: 13px; margin-top: 20px; }}
.meta span {{ color: var(--text); }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 26px 0; }}
.kpi, .panel {{ background: var(--card); border: 1px solid var(--grid); border-radius: 14px; }}
.kpi {{ padding: 18px; min-height: 132px; }}
.kpi-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
.kpi-value {{ margin-top: 8px; color: var(--teal); font-size: 27px; font-weight: 800; }}
.kpi-note {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
main {{ padding: 10px 0 58px; }}
h2 {{ font-size: 22px; margin: 32px 0 14px; }}
h3 {{ margin: 0 0 8px; font-size: 17px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 16px; }}
.panel {{ padding: 18px; overflow: hidden; }}
.panel.wide {{ grid-column: 1 / -1; }}
.panel p {{ color: var(--muted); margin: 0 0 10px; }}
.chart {{ display: block; width: 100%; min-height: 220px; }}
.callout {{ border-left: 4px solid var(--yellow); padding: 14px 18px; background: #171d2d; border-radius: 0 12px 12px 0; color: var(--text); }}
.callout strong {{ color: var(--yellow); }}
.actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
.action {{ padding: 16px; border: 1px solid var(--grid); border-radius: 12px; background: #0f192a; }}
.action b {{ color: var(--teal); }}
a {{ color: var(--teal); }}
footer {{ padding: 22px 0 40px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--grid); }}
@media (max-width: 640px) {{ .wrap {{ width: min(100% - 22px, 1180px); }} header {{ padding-top: 30px; }} .panel {{ padding: 10px; }} .chart {{ min-height: 180px; }} }}
"""
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="description" content="Decision dashboard for the accepted Public E-Commerce Data Reliability Phase 3 KPI handoff">',
        "<title>Public E-Commerce | Decision Dashboard</title>",
        f"<style>{style}</style></head><body>",
        '<header><div class="wrap">',
        '<div class="eyebrow">Accepted Phase 3 evidence · local-only</div>',
        "<h1>Public E-Commerce<br>Decision Dashboard</h1>",
        '<p class="lede">A self-contained view of the accepted KPI handoff: where revenue peaks, how much is attributable to returning customers, which products and markets matter, and which quality warnings shape the decision.</p>',
        '<div class="meta"><div>Evidence base: <span>6a9489b828940480858badb830b6e59a0b176b95</span></div><div>Currency: <span>GBP (£)</span></div><div>Source period: <span>2010-12-01 to 2011-12-09</span></div></div>',
        "</div></header>",
        '<main class="wrap">',
        '<section aria-labelledby="scorecard"><h2 id="scorecard">Decision scorecard</h2><div class="kpis">',
        kpi_card("Valid revenue", money(kpis["total_revenue_gbp"]), "non-cancelled, positive sales"),
        kpi_card("Orders", f'{int(kpis["total_orders"]):,}', "distinct positive-sales invoices"),
        kpi_card("Average order value", money(kpis["avg_order_value_gbp"]), "revenue ÷ orders"),
        kpi_card("Returning share", pct(kpis["returning_customer_revenue_pct"]), "of attributed revenue"),
        kpi_card("Guest revenue", pct(kpis["guest_revenue_pct"]), money(kpis["guest_revenue_gbp"])),
        kpi_card("Cancellation rate", pct(kpis["cancellation_rate_pct"]), "invoice-count rate"),
        "</div>",
        f'<div class="callout"><strong>Decision signal:</strong> {esc(pct(kpis["returning_customer_revenue_pct"]))} of known-customer revenue comes from returning customers, while guest orders still contribute {esc(money(kpis["guest_revenue_gbp"]))} ({esc(pct(kpis["guest_revenue_pct"]))} of total valid revenue). Retention and consent-based attribution should be managed together.</div></section>',
        '<section aria-labelledby="trends"><h2 id="trends">Revenue and trend signals</h2><div class="grid">',
        f'<article class="panel wide"><h3>Monthly valid revenue</h3><p>Peak: {esc(peak["month"])} at {esc(money(peak["revenue_gbp"]))}. December is marked partial.</p>{monthly_revenue_chart(monthly)}</article>',
        f'<article class="panel"><h3>Month-over-month movement</h3><p>Positive bars indicate growth versus the prior month; the first month has no prior-month comparison.</p>{mom_chart(monthly)}</article>',
        f'<article class="panel"><h3>Revenue composition</h3><p>Returning and other attributed revenue are separated from guest revenue to keep denominators explicit.</p>{revenue_mix_chart(kpis)}</article>',
        "</div></section>",
        '<section aria-labelledby="mix"><h2 id="mix">Product and market mix</h2><div class="grid">',
        f'<article class="panel"><h3>Top retail products</h3><p>Service/admin codes DOT, POST, and M are excluded.</p>{horizontal_bar_chart("Top retail products by revenue", products, "description", "total_revenue", money)}</article>',
        f'<article class="panel"><h3>Top countries</h3><p>United Kingdom concentration is visible in both revenue and order volume.</p>{horizontal_bar_chart("Top countries by revenue", countries, "country", "total_revenue", money, "order_count")}</article>',
        "</div></section>",
        '<section aria-labelledby="quality"><h2 id="quality">Reliability guardrails</h2><div class="grid">',
        f'<article class="panel"><h3>Accepted data-quality handoff</h3><p>Warnings are preserved audit characteristics, not silently discarded records.</p>{quality_chart(quality)}</article>',
        '<article class="panel"><h3>Interpretation rules</h3><div class="actions">',
        '<div class="action"><b>Seasonality</b><br>November is the peak complete month; December covers only the first nine days.</div>',
        '<div class="action"><b>Attribution</b><br>Returning-customer share excludes guest revenue from its denominator; guest revenue stays in total revenue.</div>',
        '<div class="action"><b>Product scope</b><br>Product ranking is StockCode-level because the source has no product taxonomy.</div>',
        '<div class="action"><b>Cancellations</b><br>The 16.12% metric is an invoice-count rate, not matched cancellation value.</div>',
        "</div></article>",
        "</div></section>",
        '<section aria-labelledby="actions"><h2 id="actions">Recommended actions</h2><div class="actions">',
        '<div class="action"><b>1 · Retain</b><br>Test loyalty, replenishment, and re-engagement journeys for identified customers; measure incremental lift.</div>',
        '<div class="action"><b>2 · Attribute</b><br>Improve consent-based account capture and monitor the guest-revenue share without forced identities.</div>',
        '<div class="action"><b>3 · Prepare</b><br>Use September–November acceleration to plan inventory, staffing, and marketing capacity.</div>',
        '<div class="action"><b>4 · Diversify</b><br>Validate shipping, tax, and product fit in secondary markets before expansion investment.</div>',
        "</div></section>",
        '<p style="margin-top:32px;color:var(--muted);font-size:13px">Sources: <a href="../analysis/kpi_results.json">accepted KPI JSON</a> · <a href="../analysis/kpi_summary.csv">portable KPI summary</a> · <a href="../data_quality_report.md">data-quality handoff</a> · <a href="../final_project_report.md">full project report</a></p>',
        "</main>",
        '<footer><div class="wrap">Generated locally from accepted evidence. No pipeline run, curated database write, remote, or network dependency is required.</div></footer>',
        "</body></html>",
    ]
    return "".join(parts) + "\n"


def validate_output(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    chart_count = text.count('<svg class="chart"')
    if chart_count < 5:
        raise ValueError(f"dashboard contains {chart_count} SVG charts; at least five are required")
    for required in (
        "Monthly valid revenue",
        "Month-over-month movement",
        "Top retail products",
        "Top countries",
        "Revenue composition",
        "Accepted data-quality handoff",
    ):
        if required not in text:
            raise ValueError(f"dashboard is missing chart section: {required}")
    if "£10,642,110.80" not in text:
        raise ValueError("dashboard is missing the accepted total revenue")
    return chart_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate an existing dashboard without rewriting it")
    args = parser.parse_args()
    if args.check:
        count = validate_output(OUTPUT_PATH)
        print(f"Validated {OUTPUT_PATH.relative_to(ROOT)} ({count} rendered SVG charts)")
        return

    kpis = load_json(KPI_PATH)
    quality = load_quality_counts(QUALITY_PATH)
    validate_inputs(kpis, quality)
    OUTPUT_PATH.write_text(render(kpis, quality), encoding="utf-8")
    count = validate_output(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} ({count} rendered SVG charts)")
    print(f"Source: {KPI_PATH.relative_to(ROOT)}")
    print("Pipeline and curated data were not modified.")


if __name__ == "__main__":
    main()
