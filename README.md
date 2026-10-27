# Telangana PDS Fair Price Shop analytics

This capstone implements the brief in `Telangana_govt_Ration_distribution_clustering.pdf` and follows the narrative structure in `Capstone Explanation Guideline.pdf`. It downloads the official Telangana Open Data resources, builds a reproducible shop-month analytical table, engineers operational features, segments Fair Price Shops into five personas, screens density-based anomalies, and serves the results in Streamlit.

## Delivered outputs

- `Telangana_PDS_Analysis.ipynb` — guided EDA, model interpretation, validation, and recommendations.
- `streamlit_app.py` — interactive overview, cluster, anomaly, map, and shop drill-down dashboard.
- `output/pdf/telangana_pds_cluster_report.pdf` — polished capstone report.
- `data/processed/` — clean monthly records, shop profiles, cluster profiles, model diagnostics, and dashboard aggregates.
- `src/pds_analytics.py` — reusable preparation and modeling functions.
- `download_data.py` and `build_artifacts.py` — reproducible data acquisition and artifact build.

## Official data

The downloader uses the three links supplied in the project brief:

1. [FPS-wise transactions](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fp-shop-wise-transactions-data)
2. [FPS card status](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fair-price-shop-card-status-data)
3. [FPS status, latitude, and longitude](https://data.telangana.gov.in/dataset/telangana-state-civil-supplies-distribution-fair-price-shop-status-latitude-and-longitude)

The analyzed transaction window is January 2023 through May 2025. Card status is available through June 2025 and the location register is dated July 2025; the time-aligned model uses only months present in the transaction data.

## Key results

- 499,648 shop-month records, 17,491 unique shops, and 33 districts were modeled.
- Five interpretable personas were selected: high-throughput anchors, low-volume local shops, volatile watchlist, portability hubs, and high-utilization shops.
- The selected K-Means model has silhouette score 0.2172. This indicates useful but overlapping operational segments, so personas should support decisions rather than be treated as hard natural classes.
- DBSCAN identified 185 local-density outliers (1.06% of shops).
- In like-for-like January–May comparisons, transactions rose 2.49% in 2024 and 2.48% in 2025, while portability transactions rose 7.61% and 8.20%, respectively.
- Hyderabad, Medchal, and Ranga Reddy combine high distribution volume with high portability, making them priority areas for mobility-aware replenishment.

## Run locally

The prepared dashboard can be opened directly using the existing project environment:

```powershell
python streamlit_app.py
```

This starts Streamlit with the project's `.venv` and opens the dashboard in your browser.
`python app.py` and the editor's **Run Python File** action work too. Keep the process
running while using the dashboard; press **Ctrl+C** in the terminal to stop it.
The standard `streamlit run streamlit_app.py` command also opens the browser automatically.

For a fresh installation and data rebuild:

Use Python 3.11+ from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python download_data.py
.\.venv\Scripts\python build_artifacts.py
.\.venv\Scripts\python create_notebook.py
.\.venv\Scripts\python build_report.py
.\.venv\Scripts\streamlit run streamlit_app.py
```

Tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Method summary

Identifiers are normalized as strings; duplicate composite keys are aggregated; transactions are joined to card status by district, shop, year, and month; locations are joined by district and shop. Ratios use safe denominators, missing model values use medians, continuous features are winsorized at the 1st/99th percentiles, and all distance-based models use standardized features.

The model uses log transaction volume, log card base, utilization, portability share, transaction coefficient of variation, rice and wheat intensity, and normalized trend. K-Means is evaluated for k=2–8, with the final choice constrained to the requested 4–5 personas. PCA is used for visualization; DBSCAN supplies an independent density-based anomaly signal; Kruskal–Wallis tests whether cluster transaction distributions differ.

## Important limitations

- The official files contain no urban/rural field, so genuine urban/rural cluster purity cannot be computed. District concentration is only a geographic proxy.
- The selected data begins after ONORC implementation; portability trends are descriptive and do not identify a causal policy effect.
- Anomaly scores are triage signals, not fraud findings. Reviews should incorporate stock ledgers, authentication records, inspections, closures, and local operational context.
- Cluster IDs are model-specific; operational persona names and feature definitions are more stable than the numeric IDs.
