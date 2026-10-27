"""Build cleaned data, features, clustering outputs, and report inputs."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

from src.pds_analytics import fit_models, load_raw_data, prepare_monthly, save_outputs


def main() -> None:
    transactions, cards, locations = load_raw_data(ROOT / "data" / "raw")
    raw_transaction_rows = len(transactions)
    raw_card_rows = len(cards)
    monthly, quality = prepare_monthly(transactions, cards, locations)
    quality["transaction_rows_raw"] = raw_transaction_rows
    quality["card_rows_raw"] = raw_card_rows
    result = fit_models(monthly)
    save_outputs(result, ROOT / "data" / "processed", quality)
    print(
        f"Built {len(result.monthly):,} monthly rows and {len(result.shops):,} shop profiles; "
        f"selected k={result.evaluation['selected_k']} "
        f"(silhouette={result.evaluation['silhouette_score']})."
    )


if __name__ == "__main__":
    main()
