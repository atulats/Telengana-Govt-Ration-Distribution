"""Generate the reproducible capstone notebook from the saved model artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

import nbformat as nbf


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def md(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    nb["cells"] = [
        md("""
# Telangana PDS Fair Price Shop segmentation

**Capstone objective.** Use official Telangana Civil Supplies data to understand shop-level distribution patterns, create 4–5 operational personas, identify peer-deviant shops, and translate the results into practical monitoring and stock-planning actions.

The analysis uses [FPS-wise transactions](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fp-shop-wise-transactions-data), [FPS card status](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fair-price-shop-card-status-data), and [FPS locations](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fair-price-shop-status-latitude-and-longitude). Transactions cover January 2023–May 2025.
"""),
        code("""
from pathlib import Path
import json
import altair as alt
import numpy as np
import pandas as pd

ROOT = Path.cwd()
PROCESSED = ROOT / "data" / "processed"
monthly = pd.read_parquet(PROCESSED / "monthly_shop_metrics.parquet")
shops = pd.read_parquet(PROCESSED / "shop_profiles.parquet")
profiles = pd.read_csv(PROCESSED / "cluster_profiles.csv")
k_scores = pd.read_csv(PROCESSED / "kmeans_evaluation.csv")
statewide = pd.read_csv(PROCESSED / "statewide_monthly.csv", parse_dates=["date"])
district_year = pd.read_csv(PROCESSED / "district_year_summary.csv")
summary = json.loads((PROCESSED / "model_summary.json").read_text())
summary
"""),
        md("""
## 1. Domain and problem statement

Telangana's Public Distribution System operates through Fair Price Shops that serve cardholders and portable beneficiaries. The business problem is not merely to rank shops by size: officials need peer groups that separate local low-volume shops, high-throughput anchors, high-utilization shops, portability hubs, and unstable operations. The resulting personas can guide replenishment, monitoring, and evidence-led inspection.
"""),
        md("""
## 2. ELT, cleaning, and quality controls

`download_data.py` reads the official portal metadata and downloads monthly CSV resources. `build_artifacts.py` calls reusable functions in `src/pds_analytics.py`. Identifiers remain strings; numeric fields are coerced; duplicate keys are aggregated; transactions and card status are joined on district + shop + year + month; locations are joined on district + shop. Ratios use safe denominators and the model uses winsorization, median imputation, and standardization.
"""),
        code("""
quality = pd.Series(summary["data_quality"], name="value").rename_axis("check").reset_index()
quality
"""),
        md("""
The small number of unmatched card and location rows is retained and made explicit. Location gaps affect mapping, not the core transaction clustering. No duplicate shop-month keys remain after aggregation.
"""),
        md("## 3. Exploratory analysis"),
        code("""
year_summary = (statewide.groupby("year", as_index=False)
                .agg(transactions=("transactions", "sum"),
                     portability_transactions=("portability_transactions", "sum"),
                     eligible_cards=("eligible_cards", "sum")))
year_summary["utilization"] = year_summary.transactions / year_summary.eligible_cards
year_summary["portability_share"] = year_summary.portability_transactions / year_summary.transactions
year_summary
"""),
        code("""
trend = statewide.melt("date", value_vars=["transactions", "portability_transactions"],
                       var_name="series", value_name="count")
alt.Chart(trend).mark_line(point=True).encode(
    x=alt.X("date:T", title="Month"),
    y=alt.Y("count:Q", title="Transactions"),
    color=alt.Color("series:N", title="Series"),
    tooltip=["date:T", "series:N", alt.Tooltip("count:Q", format=",")],
).properties(width=760, height=330, title="Statewide monthly transactions")
"""),
        code("""
jan_may = (statewide[statewide.month <= 5].groupby("year", as_index=False)
           .agg(transactions=("transactions", "sum"),
                portability=("portability_transactions", "sum"),
                cards=("eligible_cards", "sum")))
jan_may["transaction_growth"] = jan_may.transactions.pct_change()
jan_may["portability_growth"] = jan_may.portability.pct_change()
jan_may["utilization"] = jan_may.transactions / jan_may.cards
jan_may["portability_share"] = jan_may.portability / jan_may.transactions
jan_may
"""),
        md("""
Like-for-like January–May transaction counts increased about 2.5% in both 2024 and 2025. Portability transactions grew faster—7.6% and 8.2%—and portability share reached roughly 37.5% in 2025. This is a descriptive trend, not a causal estimate of ONORC impact.
"""),
        code("""
monthly[["eligibleCards", "noOfTrans", "otherShopTransCnt", "totalRice", "wheat"]].corr()
"""),
        md("""
Eligible cards and transaction volume are strongly associated (about 0.88). Because raw scale variables are redundant and highly skewed, the model uses transformed averages plus ratios and variability features.
"""),
        md("## 4. Feature engineering and statistical technique"),
        code("""
pd.DataFrame({"model_feature": summary["model_features"]})
"""),
        md("""
The features represent scale, beneficiary utilization, portable demand, month-to-month stability, commodity intensity, and direction of change. A Kruskal–Wallis test is used because transaction distributions are skewed; it confirms that transaction distributions differ across the five clusters (H = 11,052.9, p < 0.001). Statistical significance does not imply perfect separation, so effect interpretation relies on cluster profiles and the silhouette score.
"""),
        md("## 5. Model selection and validation"),
        code("""
alt.Chart(k_scores).mark_line(point=True).encode(
    x=alt.X("k:O", title="Number of clusters"),
    y=alt.Y("silhouette:Q", scale=alt.Scale(zero=False), title="Silhouette score"),
    tooltip=["k:O", alt.Tooltip("silhouette:Q", format=".3f")],
).properties(width=620, height=300, title="K-Means validation (k = 2–8)")
"""),
        md("""
The brief asks for 4–5 operational personas. Within that range, k=5 has the better silhouette score (0.2172 versus 0.2064). The moderate score indicates overlapping real-world shop behavior, so clusters are best treated as operational benchmarks rather than immutable classes. PCA explains 53.4% of standardized variance in two dimensions and is used only for visualization. DBSCAN separately identifies 185 local-density outliers (1.06%).
"""),
        code("""
sample = shops.sample(min(4000, len(shops)), random_state=42)
alt.Chart(sample).mark_circle(size=28, opacity=0.45).encode(
    x=alt.X("pca_1:Q", title="Principal component 1"),
    y=alt.Y("pca_2:Q", title="Principal component 2"),
    color=alt.Color("cluster:N", title="Cluster"),
    tooltip=["shopNo:N", "distName:N", "persona:N", alt.Tooltip("risk_score:Q", format=".1f")],
).properties(width=720, height=420, title="Shop personas in PCA space")
"""),
        md("## 6. Cluster personas"),
        code("""
display_cols = ["cluster_id", "persona", "shops", "avg_monthly_transactions", "avg_cards",
                "utilization_ratio", "portability_share", "transaction_cv", "noise_rate"]
profiles[display_cols].round(3)
"""),
        md("""
- **Portability hubs** have the highest average volume and portability share; use mobility-aware forecasts and larger replenishment buffers.
- **High-throughput anchors** serve large card bases with near-full utilization; prioritize uptime and queue capacity.
- **High-utilization shops** form the largest stable group; use them as a peer benchmark.
- **Low-volume local shops** have smaller, locally oriented demand; right-size stock and avoid comparing them directly with urban hubs.
- **Volatile watchlist** shops combine low utilization, high variation, and the highest DBSCAN noise rate; review them first, but do not treat the flag as proof of wrongdoing.
"""),
        md("## 7. Anomaly review and business solution"),
        code("""
watchlist = shops.sort_values(["dbscan_noise", "risk_score"], ascending=[False, False])
watchlist[["shopNo", "distName", "persona", "risk_score", "dbscan_noise", "primary_alert_reason"]].head(20)
"""),
        md("""
Recommended operating workflow: (1) forecast stock by persona and district; (2) apply higher buffers to portability hubs; (3) route density-noise and high-risk shops to a review queue; (4) compare each shop with its own persona; and (5) close the loop using stock ledgers, biometric/authentication failures, closure logs, and field inspection evidence.

The dashboard operationalizes this workflow with district/year filters, geospatial persona maps, anomaly reasons, a risk threshold, and exact shop-to-cluster benchmarking.
"""),
        md("""
## 8. Limitations and conclusion

The official sources do not contain an urban/rural label, so genuine urban/rural cluster purity cannot be calculated; district concentration is only a geographic proxy. The data window begins after ONORC, so no causal policy-impact claim is made. Anomaly scores are screening signals, and cluster numbers may change when new months are added.

Within those limits, the solution provides a reproducible, explainable segmentation of 17,491 shops across 33 districts. The combination of five personas, DBSCAN screening, and the Streamlit drill-down gives officials a practical way to plan stock, recognize portability pressure, and prioritize evidence-led review.
"""),
    ]
    output = ROOT / "Telangana_PDS_Analysis.ipynb"
    nbf.write(nb, output)
    print(f"Wrote {output.name} with {len(nb['cells'])} cells")


if __name__ == "__main__":
    main()
