"""
TICKET-074: Clean Legacy Watchlist Data

Cleans up legacy data in watchlist_overrides.json:
- Fixes epoch dates (1970-01-01)
- Validates structure
- Removes stale entries

The overrides file has format:
{
  "add": {"TICKER": {"added_on": "2026-04-01", "note": "..."}},
  "remove": [{"ticker": "TICKER", "date": "2026-04-01"}]
}
"""

import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Union

WATCHLIST_OVERRIDES_FILE = Path("trading_loop_logs/watchlist_overrides.json")
EPOCH_DATE = "1970-01-01"


def clean_add_entry_dates(add_dict: dict) -> tuple[dict, int]:
    """Replace epoch dates in add entries."""
    today = datetime.now().strftime("%Y-%m-%d")
    cleaned_count = 0

    for ticker, info in add_dict.items():
        if not isinstance(info, dict):
            continue
        if info.get("added_on") == EPOCH_DATE:
            print(f"[CLEANUP] Fixing epoch date for +{ticker}: {EPOCH_DATE} -> {today}")
            info["added_on"] = today
            cleaned_count += 1

    return add_dict, cleaned_count


def clean_remove_entries(remove_list: list, max_days: int = 30) -> tuple[list, int]:
    """Remove stale remove entries."""
    if not remove_list:
        return [], 0

    today = date.today()
    cleaned = []
    removed_count = 0

    for entry in remove_list:
        if not isinstance(entry, dict):
            removed_count += 1
            continue

        ticker = entry.get("ticker", "")
        entry_date = entry.get("date", "")

        if not entry_date:
            removed_count += 1
            continue

        try:
            entry_dt = date.fromisoformat(entry_date)
            if (today - entry_dt).days > max_days:
                print(f"[CLEANUP] Removing stale -{ticker} (date: {entry_date})")
                removed_count += 1
                continue
        except ValueError:
            # Invalid date format, keep it
            pass

        cleaned.append(entry)

    return cleaned, removed_count


def load_and_clean_watchlist_overrides(file_path: Path = None) -> dict:
    """Load and clean watchlist overrides."""
    if file_path is None:
        file_path = WATCHLIST_OVERRIDES_FILE

    if not file_path.exists():
        return {"add": {}, "remove": []}

    try:
        with open(file_path) as f:
            overrides = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[CLEANUP] Error loading watchlist overrides: {e}")
        return {"add": {}, "remove": []}

    if not isinstance(overrides, dict):
        print(f"[CLEANUP] Invalid overrides format")
        return {"add": {}, "remove": []}

    # Ensure required keys exist
    if "add" not in overrides:
        overrides["add"] = {}
    if "remove" not in overrides:
        overrides["remove"] = []

    # Clean add entries
    add_fixed = 0
    overrides["add"], add_fixed = clean_add_entry_dates(overrides["add"])

    # Clean remove entries
    remove_cleaned = 0
    overrides["remove"], remove_cleaned = clean_remove_entries(overrides["remove"])

    # Save if changes were made
    if add_fixed > 0 or remove_cleaned > 0:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(overrides, f, indent=2)
        print(f"[CLEANUP] Saved {add_fixed + remove_cleaned} fix(es)")

    return overrides


def main():
    """CLI for watchlist cleanup."""
    print("=" * 60)
    print("TICKET-074: Watchlist Data Cleanup")
    print("=" * 60)

    overrides = load_and_clean_watchlist_overrides()

    print(f"\nAdd entries: {len(overrides.get('add', {}))}")
    for ticker, info in sorted(overrides.get('add', {}).items()):
        added = info.get("added_on", "N/A")
        note = info.get("note", "")[:30]
        print(f"  +{ticker}: added {added} ({note})")

    print(f"\nRemove entries: {len(overrides.get('remove', []))}")
    for entry in overrides.get('remove', []):
        ticker = entry.get("ticker", "UNKNOWN")
        entry_date = entry.get("date", "N/A")
        print(f"  -{ticker}: {entry_date}")

    print("\nCleanup complete")


if __name__ == "__main__":
    main()
