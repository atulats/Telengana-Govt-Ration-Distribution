"""Download the official Telangana PDS CSV resources used by the project.

The portal publishes one CSV per month.  This script reads the three metadata
snapshots in the repository and downloads the 2023-2025 transactions and card
status files plus the latest FPS location file.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
YEARS = ("2023", "2024", "2025")
SOURCES = {
    "transactions": ROOT / "transactions_metadata.json",
    "card_status": ROOT / "card_status_metadata.json",
    "locations": ROOT / "fps_location_metadata.json",
}


def resource_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dataset, metadata_path in SOURCES.items():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for resource in metadata.get("distribution", []):
            data = resource.get("data", resource)
            title = data.get("title", "")
            url = data.get("downloadURL")
            if not url:
                continue
            if dataset != "locations" and not any(year in title for year in YEARS):
                continue
            filename = Path(unquote(urlparse(url).path)).name
            rows.append(
                {
                    "dataset": dataset,
                    "title": title,
                    "url": url,
                    "filename": filename,
                }
            )
    return rows


def download(row: dict[str, str]) -> dict[str, str | int]:
    destination = RAW_DIR / row["dataset"] / row["filename"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 100:
        return {**row, "bytes": destination.stat().st_size, "status": "cached"}

    request = Request(row["url"], headers={"User-Agent": "Telangana-PDS-Analytics/1.0"})
    with urlopen(request, timeout=120) as response:
        content = response.read()
    if content.lstrip().lower().startswith(b"<!doctype html"):
        raise ValueError(f"Portal returned HTML instead of CSV: {row['url']}")
    destination.write_bytes(content)
    return {**row, "bytes": len(content), "status": "downloaded"}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = resource_rows()
    completed: list[dict[str, str | int]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(download, row): row for row in rows}
        for future in as_completed(futures):
            result = future.result()
            completed.append(result)
            print(f"{result['status']:>10}  {result['dataset']:<12}  {result['filename']}")

    completed.sort(key=lambda item: (str(item["dataset"]), str(item["filename"])))
    (RAW_DIR / "download_manifest.json").write_text(
        json.dumps(completed, indent=2), encoding="utf-8"
    )
    total_bytes = sum(int(item["bytes"]) for item in completed)
    print(f"\nReady: {len(completed)} files, {total_bytes / 1_048_576:.1f} MiB")


if __name__ == "__main__":
    main()
