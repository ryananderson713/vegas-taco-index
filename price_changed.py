#!/usr/bin/env python3
"""
Exit 0 if the scraped prices differ from the committed ones, 1 if not.

Every scrape restamps `updated`, and that timestamp is embedded in the built
HTML too — so a plain `git diff` always reports a change. Comparing only the
store and item data is what actually tells you whether prices moved.
"""

import json
import subprocess
import sys

PATH = "data/vegas_prices.json"


def prices_only(payload):
    return {"stores": payload.get("stores"), "items": payload.get("items")}


def main():
    with open(PATH, encoding="utf-8") as f:
        new = prices_only(json.load(f))

    r = subprocess.run(["git", "show", f"HEAD:{PATH}"], capture_output=True, text=True)
    if r.returncode != 0:
        print("No committed data to compare against — treating as changed.")
        return 0

    try:
        old = prices_only(json.loads(r.stdout))
    except json.JSONDecodeError:
        print("Committed data is unreadable — treating as changed.")
        return 0

    if old == new:
        print("Prices are unchanged.")
        return 1

    old_items = {i["name"]: i for i in (old.get("items") or [])}
    moved = [
        i["name"] for i in (new.get("items") or [])
        if i["name"] in old_items and old_items[i["name"]]["stores"] != i["stores"]
    ]
    added = len(new.get("items") or []) - len(old_items)
    print(f"Prices changed: {len(moved)} item(s) repriced, {added:+d} item(s) on the menu.")
    for name in moved[:10]:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
