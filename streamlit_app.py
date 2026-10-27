"""Interactive Telangana PDS clustering and anomaly-monitoring dashboard."""

from __future__ import annotations

if __name__ == "__main__":
    from src.dashboard_launcher import launch_if_needed

    launch_if_needed(__file__)

import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st


ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
CLUSTER_COLORS = ["#0F766E", "#EA580C", "#7C3AED", "#2563EB", "#CA8A04"]

st.set_page_config(
    page_title="Telangana PDS analytics",
    page_icon=":material/local_shipping:",
    layout="wide",
)


@st.cache_data(show_spinner="Loading Telangana PDS analytics...")
def load_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    monthly = pd.read_parquet(PROCESSED / "monthly_shop_metrics.parquet")
    shops = pd.read_parquet(PROCESSED / "shop_profiles.parquet")
    clusters = pd.read_csv(PROCESSED / "cluster_profiles.csv")
    summary = json.loads((PROCESSED / "model_summary.json").read_text(encoding="utf-8"))
    return monthly, shops, clusters, summary


def fmt_int(value: float) -> str:
    return f"{value:,.0f}"


def metric_row(monthly: pd.DataFrame) -> None:
    transactions = monthly["noOfTrans"].sum()
    cards = monthly["eligibleCards"].sum()
    portability = monthly["otherShopTransCnt"].sum()
    with st.container(horizontal=True):
        st.metric("Transactions", fmt_int(transactions), border=True)
        st.metric("Active shops", fmt_int(monthly["shopNo"].nunique()), border=True)
        st.metric("Utilization", f"{transactions / cards:.1%}" if cards else "N/A", border=True)
        st.metric(
            "Portability share",
            f"{portability / transactions:.1%}" if transactions else "N/A",
            border=True,
        )
        st.metric("Rice distributed", f"{monthly['totalRice'].sum() / 1_000_000:,.1f}M kg", border=True)


def overview_page(monthly: pd.DataFrame) -> None:
    metric_row(monthly)
    trend = (
        monthly.groupby("date", as_index=False)
        .agg(
            Transactions=("noOfTrans", "sum"),
            **{"Portability transactions": ("otherShopTransCnt", "sum")},
        )
        .melt("date", var_name="Metric", value_name="Count")
    )
    line = (
        alt.Chart(trend)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Month"),
            y=alt.Y("Count:Q", title="Transactions", axis=alt.Axis(format="~s")),
            color=alt.Color("Metric:N", scale=alt.Scale(range=["#0F766E", "#EA580C"])),
            tooltip=[alt.Tooltip("date:T", title="Month"), "Metric:N", alt.Tooltip("Count:Q", format=",")],
        )
        .properties(height=330)
    )
    with st.container(border=True):
        st.subheader("Monthly distribution and portability", icon=":material/timeline:")
        st.altair_chart(line)

    left, right = st.columns(2)
    district = (
        monthly.groupby("distName", as_index=False)
        .agg(Transactions=("noOfTrans", "sum"), Shops=("shopNo", "nunique"))
        .nlargest(12, "Transactions")
    )
    district_chart = (
        alt.Chart(district)
        .mark_bar(cornerRadiusEnd=4, color="#2563EB")
        .encode(
            x=alt.X("Transactions:Q", axis=alt.Axis(format="~s")),
            y=alt.Y("distName:N", sort="-x", title="District"),
            tooltip=[alt.Tooltip("distName:N", title="District"), alt.Tooltip("Transactions:Q", format=",")],
        )
        .properties(height=360)
    )
    with left.container(border=True):
        st.subheader("Highest-volume districts", icon=":material/bar_chart:")
        st.altair_chart(district_chart)

    seasonality = monthly.groupby("month", as_index=False).agg(
        Transactions=("noOfTrans", "sum"), Observed_years=("year", "nunique")
    )
    seasonality["Average yearly transactions"] = seasonality["Transactions"] / seasonality["Observed_years"]
    season_chart = (
        alt.Chart(seasonality)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#0F766E")
        .encode(
            x=alt.X("month:O", title="Month"),
            y=alt.Y("Average yearly transactions:Q", axis=alt.Axis(format="~s")),
            tooltip=["month:O", alt.Tooltip("Average yearly transactions:Q", format=",")],
        )
        .properties(height=360)
    )
    with right.container(border=True):
        st.subheader("Seasonality check", icon=":material/calendar_month:")
        st.altair_chart(season_chart)
        st.caption("Monthly totals are normalized by the number of observed years; 2025 is available through May.")

    top_districts = district["distName"].head(10).tolist()
    commodity = monthly[monthly["distName"].isin(top_districts)][
        ["distName", "totalRice", "wheat"]
    ].rename(columns={"totalRice": "Rice", "wheat": "Wheat"})
    commodity = commodity.melt("distName", var_name="Commodity", value_name="Monthly kg")
    commodity = commodity.sample(min(50_000, len(commodity)), random_state=42)
    boxplot = (
        alt.Chart(commodity)
        .mark_boxplot(extent="min-max", size=12)
        .encode(
            x=alt.X("distName:N", title="District", sort=top_districts, axis=alt.Axis(labelAngle=-35)),
            y=alt.Y("Monthly kg:Q", scale=alt.Scale(type="symlog")),
            color=alt.Color("Commodity:N", scale=alt.Scale(range=["#0F766E", "#EA580C"])),
        )
        .properties(height=360)
    )
    with st.container(border=True):
        st.subheader("Commodity distribution", icon=":material/inventory_2:")
        st.altair_chart(boxplot)
        st.caption("Shop-month distributions for rice and wheat across the ten highest-volume districts; symlog scale retains zero values.")


def cluster_page(
    shops: pd.DataFrame, clusters: pd.DataFrame, summary: dict[str, object]
) -> None:
    with st.container(horizontal=True):
        st.metric("Selected clusters", summary["selected_k"], border=True)
        st.metric("Silhouette score", f"{summary['silhouette_score']:.3f}", border=True)
        st.metric("PCA variance shown", f"{summary['pca_2d_explained_variance']:.1%}", border=True)
        st.metric("DBSCAN noise shops", fmt_int(summary["dbscan_noise_shops"]), border=True)

    left, right = st.columns([1.35, 1])
    sample = shops.sample(min(4_000, len(shops)), random_state=42).copy()
    sample["Cluster"] = sample["cluster_id"].astype(str) + " - " + sample["persona"]
    scatter = (
        alt.Chart(sample)
        .mark_circle(opacity=0.6, size=35)
        .encode(
            x=alt.X("pca_1:Q", title="Principal component 1"),
            y=alt.Y("pca_2:Q", title="Principal component 2"),
            color=alt.Color("cluster_id:N", title="Cluster", scale=alt.Scale(range=CLUSTER_COLORS)),
            tooltip=["shopNo:N", "distName:N", "Cluster:N", alt.Tooltip("risk_score:Q", format=".1f")],
        )
        .properties(height=470)
    )
    with left.container(border=True):
        st.subheader("Shop personas in PCA space", icon=":material/scatter_plot:")
        st.altair_chart(scatter)
        st.caption("A reproducible sample is shown for responsiveness; PCA is used only for visualization.")

    profile = clusters.copy()
    profile["utilization_ratio"] *= 100
    profile["portability_share"] *= 100
    with right.container(border=True):
        st.subheader("Cluster profiles", icon=":material/groups:")
        st.dataframe(
            profile,
            column_config={
                "cluster_id": st.column_config.NumberColumn("Cluster", format="%d", pinned=True),
                "persona": "Persona",
                "shops": st.column_config.NumberColumn("Shops", format=","),
                "avg_monthly_transactions": st.column_config.NumberColumn("Avg transactions", format="%.0f"),
                "avg_cards": st.column_config.NumberColumn("Avg cards", format="%.0f"),
                "utilization_ratio": st.column_config.NumberColumn("Utilization", format="%.1f%%"),
                "portability_share": st.column_config.NumberColumn("Portability", format="%.1f%%"),
                "transaction_cv": st.column_config.NumberColumn("Volatility", format="%.2f"),
                "rice_per_transaction": None,
                "wheat_per_transaction": None,
                "transaction_trend_pct": None,
                "noise_rate": None,
            },
            hide_index=True,
            height=465,
        )

    mapped = shops.dropna(subset=["latitude", "longitude"]).copy()
    mapped = mapped[mapped["latitude"].between(15, 21) & mapped["longitude"].between(76, 82)]
    mapped["color"] = mapped["cluster_id"].map(
        {index: [int(color[i : i + 2], 16) for i in (1, 3, 5)] + [165] for index, color in enumerate(CLUSTER_COLORS)}
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=mapped,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_radius=220,
        pickable=True,
        opacity=0.75,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=17.9, longitude=79.3, zoom=6.4),
        tooltip={"html": "<b>Shop:</b> {shopNo}<br/><b>District:</b> {distName}<br/><b>Persona:</b> {persona}"},
    )
    with st.container(border=True):
        st.subheader("Geospatial cluster map", icon=":material/map:")
        st.pydeck_chart(deck, height=560)
        st.caption(f"Mapped {len(mapped):,} shops with valid Telangana coordinates; colors correspond to Cluster ID.")


def anomaly_page(shops: pd.DataFrame) -> None:
    st.warning(
        "Anomaly flags are screening signals, not proof of fraud. Investigate stock, authentication, and local context before action.",
        icon=":material/policy:",
    )
    with st.container(border=True):
        risk_threshold = st.slider("Minimum risk score", 0, 100, 75)
        only_noise = st.toggle("Show DBSCAN noise only", value=False)
    flagged = shops[shops["risk_score"] >= risk_threshold].copy()
    if only_noise:
        flagged = flagged[flagged["is_dbscan_noise"]]

    with st.container(horizontal=True):
        st.metric("Flagged shops", fmt_int(len(flagged)), border=True)
        st.metric("DBSCAN noise", fmt_int(flagged["is_dbscan_noise"].sum()), border=True)
        st.metric("Districts represented", fmt_int(flagged["distName"].nunique()), border=True)
        st.metric("Median risk", f"{flagged['risk_score'].median():.1f}" if len(flagged) else "N/A", border=True)

    left, right = st.columns([1, 1.7])
    reasons = flagged["alert_reason"].value_counts().rename_axis("Reason").reset_index(name="Shops")
    reason_chart = (
        alt.Chart(reasons)
        .mark_bar(cornerRadiusEnd=4, color="#CA8A04")
        .encode(x="Shops:Q", y=alt.Y("Reason:N", sort="-x"), tooltip=["Reason:N", "Shops:Q"])
        .properties(height=330)
    )
    with left.container(border=True):
        st.subheader("Primary alert reasons", icon=":material/report_problem:")
        st.altair_chart(reason_chart)
    with right.container(border=True):
        st.subheader("Prioritized watchlist", icon=":material/priority_high:")
        table = flagged.sort_values(["is_dbscan_noise", "risk_score"], ascending=False).head(500)
        st.dataframe(
            table[
                [
                    "shopNo",
                    "distName",
                    "persona",
                    "risk_score",
                    "is_dbscan_noise",
                    "alert_reason",
                    "avg_monthly_transactions",
                    "utilization_ratio",
                    "portability_share",
                    "transaction_cv",
                ]
            ],
            column_config={
                "shopNo": st.column_config.TextColumn("Shop", pinned=True),
                "distName": "District",
                "persona": "Persona",
                "risk_score": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100),
                "is_dbscan_noise": st.column_config.CheckboxColumn("DBSCAN noise"),
                "alert_reason": "Primary reason",
                "avg_monthly_transactions": st.column_config.NumberColumn("Avg transactions", format="%.0f"),
                "utilization_ratio": st.column_config.NumberColumn("Utilization", format="percent"),
                "portability_share": st.column_config.NumberColumn("Portability", format="percent"),
                "transaction_cv": st.column_config.NumberColumn("Volatility", format="%.2f"),
            },
            hide_index=True,
            height=430,
        )


def shop_lookup_page(monthly: pd.DataFrame, shops: pd.DataFrame, clusters: pd.DataFrame) -> None:
    with st.form("shop_search", border=True):
        shop_number = st.text_input("Fair Price Shop number", placeholder="Example: 1901001")
        submitted = st.form_submit_button("Find shop", icon=":material/search:")
    if not submitted and not shop_number:
        st.info("Enter an exact shop number to compare its performance with its cluster.")
        return
    match = shops[shops["shopNo"].astype(str).str.strip() == shop_number.strip()]
    if match.empty:
        st.error("No shop was found in the 2023-2025 transaction data.")
        return

    row = match.iloc[0]
    cluster = clusters[clusters["cluster_id"] == row["cluster_id"]].iloc[0]
    st.subheader(f"Shop {row['shopNo']} - {row['distName']}", icon=":material/storefront:")
    st.markdown(
        f":blue-badge[Cluster {int(row['cluster_id'])}] :green-badge[{row['persona']}] "
        f":orange-badge[Risk {row['risk_score']:.1f}/100]"
    )
    with st.container(horizontal=True):
        st.metric("Avg monthly transactions", fmt_int(row["avg_monthly_transactions"]), border=True)
        st.metric("Utilization", f"{row['utilization_ratio']:.1%}", border=True)
        st.metric("Portability", f"{row['portability_share']:.1%}", border=True)
        st.metric("Volatility", f"{row['transaction_cv']:.2f}", border=True)

    history = monthly[monthly["shopNo"] == row["shopNo"]].sort_values("date")
    left, right = st.columns([1.25, 1])
    with left.container(border=True):
        st.subheader("Monthly performance", icon=":material/timeline:")
        st.line_chart(history, x="date", y=["noOfTrans", "otherShopTransCnt"], x_label="Month", y_label="Transactions")

    comparison = pd.DataFrame(
        {
            "Metric": ["Avg transactions", "Utilization", "Portability", "Volatility"],
            "Shop": [
                row["avg_monthly_transactions"],
                row["utilization_ratio"],
                row["portability_share"],
                row["transaction_cv"],
            ],
            "Cluster average": [
                cluster["avg_monthly_transactions"],
                cluster["utilization_ratio"],
                cluster["portability_share"],
                cluster["transaction_cv"],
            ],
        }
    ).melt("Metric", var_name="Benchmark", value_name="Value")
    comparison["Indexed value"] = comparison.groupby("Metric")["Value"].transform(
        lambda values: values / values.iloc[-1] if values.iloc[-1] else np.nan
    )
    compare_chart = (
        alt.Chart(comparison)
        .mark_bar()
        .encode(
            x=alt.X("Indexed value:Q", title="Index (cluster average = 1.0)"),
            y=alt.Y("Metric:N", sort=None),
            color=alt.Color("Benchmark:N", scale=alt.Scale(range=["#EA580C", "#0F766E"])),
            tooltip=["Metric:N", "Benchmark:N", alt.Tooltip("Value:Q", format=".3f")],
        )
        .properties(height=310)
    )
    with right.container(border=True):
        st.subheader("Against cluster average", icon=":material/compare_arrows:")
        st.altair_chart(compare_chart)
        st.caption(f"Primary alert reason: {row['alert_reason']}.")


def methodology_page(summary: dict[str, object]) -> None:
    st.subheader("Capstone explanation", icon=":material/science:")
    st.markdown(
        """
**Domain (3 lines).** Telangana's Public Distribution System uses Fair Price Shops to deliver subsidized food grains and essential commodities. Shop-level transaction, entitlement, portability, and location data describe both demand and execution. Reliable segmentation helps officials focus audits and stock planning where operating patterns differ from peers.

**Project introduction (2 lines).** This project integrates official monthly transaction and card-status files for 2023-May 2025 with the July 2025 FPS location register. It turns roughly half a million shop-month records into interpretable personas, anomaly signals, and an interactive monitoring dashboard.

**Objective (2 lines).** Segment shops into 4-5 operational personas and flag peer-deviant behavior without assuming labeled fraud outcomes. Provide district/year exploration, geospatial hotspots, portability trends, and shop-to-cluster benchmarking for decision support.

**ELT approach.** The downloader reads portal metadata, fetches monthly CSV resources, concatenates each source, normalizes identifiers and numeric fields, aggregates duplicate keys, then joins transactions to card status on district + shop + year + month and locations on district + shop. No MongoDB-to-SQL migration is required because the supplied sources are flat files.

**Cleaning and preprocessing.** Identifiers are kept as strings, numeric coercion converts invalid values to missing, duplicate composite keys are aggregated, ratios use safe denominators, missing modeling values use feature medians, and every model feature is winsorized at the 1st/99th percentile. StandardScaler is fitted before all distance-based models.

**Feature engineering.** The model uses log monthly volume, log card base, utilization, portability share, transaction coefficient of variation, rice/transaction, wheat/transaction, and normalized transaction trend. These separate scale, execution, non-local demand, commodity mix, stability, and direction of change while avoiding redundant raw totals.

**Statistical technique.** A Kruskal-Wallis test checks whether median transaction volume differs across clusters; it is appropriate because shop volumes are strongly skewed and normality is not assumed. PCA compresses standardized features for visualization, not for naming the personas.

**Model building and evaluation.** K-Means is tested for k=2 through 8; the final choice is the better silhouette among k=4 and k=5 to honor the brief's persona range. DBSCAN runs separately on PCA-reduced standardized features to identify local-density noise. Inertia, silhouette score, PCA explained variance, and DBSCAN noise rate are reported.

**Conclusion.** Portability share increased in like-for-like January-May periods, while transaction volume and utilization also rose. Hyderabad, Medchal, and Ranga Reddy combine the largest distribution volumes with the highest portability shares, making them priority candidates for mobility-aware stock planning.

**Business solution.** Use portability-hub forecasts for higher replenishment buffers, route DBSCAN noise shops to evidence-led review, and compare shops against their own persona before escalating. Treat anomaly scores as triage—not guilt—and combine them with authentication, stock ledger, and inspection evidence.
"""
    )
    with st.container(border=True):
        st.subheader("Model facts and limitations", icon=":material/fact_check:")
        st.table(
            {
                "Period": f"{summary['period_start']} to {summary['period_end']}",
                "Monthly records": f"{summary['monthly_rows']:,}",
                "Shop profiles": f"{summary['shops']:,}",
                "Districts": str(summary["districts"]),
                "Selected k": str(summary["selected_k"]),
                "Silhouette": f"{summary['silhouette_score']:.4f}",
                "DBSCAN noise rate": f"{summary['dbscan_noise_rate']:.2%}",
                "Urban/rural purity": "Not computable - no urban/rural field in the official sources",
                "Policy causality": "Not claimed - the selected data starts after ONORC implementation",
            },
            border="horizontal",
            width="content",
        )
    st.caption("Sources: Telangana Open Data Portal datasets linked in the project brief. Open Government License - India.")


if not PROCESSED.exists():
    st.error("Processed data is missing. Run `python build_artifacts.py` first.")
    st.stop()

monthly_all, shops_all, clusters_all, model_summary = load_outputs()

st.title("Telangana PDS shop intelligence", icon=":material/local_shipping:")
st.caption(
    "Official 2023-May 2025 shop transactions joined to card entitlements and July 2025 FPS locations. "
    "Use the filters to compare distribution, portability, personas, and anomalies."
)

with st.sidebar:
    st.subheader("Global filters", icon=":material/filter_alt:")
    selected_year = st.selectbox("Year", ["All", 2023, 2024, 2025], key="year_filter")
    selected_districts = st.multiselect(
        "Districts",
        sorted(monthly_all["distName"].dropna().unique()),
        placeholder="All districts",
        key="district_filter",
    )
    st.caption("2025 transaction data is available through May; card status through June.")
    st.link_button(
        "Official data portal",
        "https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fp-shop-wise-transactions-data",
        icon=":material/open_in_new:",
        type="tertiary",
    )

monthly_filtered = monthly_all.copy()
shops_filtered = shops_all.copy()
if selected_year != "All":
    monthly_filtered = monthly_filtered[monthly_filtered["year"] == selected_year]
if selected_districts:
    monthly_filtered = monthly_filtered[monthly_filtered["distName"].isin(selected_districts)]
    shops_filtered = shops_filtered[shops_filtered["distName"].isin(selected_districts)]

view = st.segmented_control(
    "Analysis view",
    ["Overview", "Clusters", "Anomalies", "Shop lookup", "Methodology"],
    default="Overview",
    key="analysis_view",
)

if monthly_filtered.empty or shops_filtered.empty:
    st.warning("No records match the current filters.")
elif view == "Clusters":
    cluster_page(shops_filtered, clusters_all, model_summary)
elif view == "Anomalies":
    anomaly_page(shops_filtered)
elif view == "Shop lookup":
    shop_lookup_page(monthly_filtered, shops_filtered, clusters_all)
elif view == "Methodology":
    methodology_page(model_summary)
else:
    overview_page(monthly_filtered)
