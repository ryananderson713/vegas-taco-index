#!/usr/bin/env python3
"""
Fetch per-store Taco Bell menu prices across the Las Vegas valley.

Uses the public tacobell.com web/mobile backend. No account or API key needed.
Writes data/vegas_prices.json, which app.html reads.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

BASE = "https://www.tacobell.com/tacobellwebservices/v4/tacobell"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vegas_prices.json")

# The store locator returns ~14 results per query, so sweep a grid over the
# valley to reach every location instead of just the ones near downtown.
SEED_POINTS = [
    (36.1699, -115.1398),  # downtown
    (36.1147, -115.1728),  # the Strip
    (36.0397, -115.1000),  # Henderson
    (36.2333, -115.2500),  # northwest
    (36.0800, -115.2600),  # southwest / Spring Valley
    (36.2100, -115.0300),  # northeast / Sunrise
    (36.0100, -115.2400),  # Enterprise
    (36.2800, -115.1200),  # North Las Vegas
]

REQUEST_DELAY = 0.4  # be a polite client


def fetch(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def find_stores():
    """Sweep the seed grid and dedupe by store number."""
    stores = {}
    for lat, lng in SEED_POINTS:
        try:
            data = fetch(f"{BASE}/stores?latitude={lat}&longitude={lng}")
        except Exception as e:
            print(f"  ! store lookup failed at {lat},{lng}: {e}", file=sys.stderr)
            continue
        for s in data.get("nearByStores", []):
            num = s.get("storeNumber")
            geo = s.get("geoPoint") or {}
            if not num or num in stores:
                continue
            addr = s.get("address") or {}
            stores[num] = {
                "store": num,
                "address": addr.get("line1"),
                "city": addr.get("town"),
                "zip": addr.get("postalCode"),
                "phone": s.get("phoneNumber"),
                "lat": geo.get("latitude"),
                "lng": geo.get("longitude"),
            }
        time.sleep(REQUEST_DELAY)
    return stores


def fetch_menu(store_num):
    """Return {item_name: price} for one store."""
    data = fetch(f"{BASE}/products/menu/{store_num}")
    out = {}
    for cat in data.get("menuProductCategories", []):
        for p in cat.get("products", []):
            price = (p.get("price") or {}).get("value")
            name = (p.get("name") or "").strip()
            if price and name:
                # Same item can appear in several categories; keep the lowest.
                if name not in out or price < out[name]:
                    out[name] = price
    return out


def main():
    print("Finding Las Vegas Taco Bell locations...")
    stores = find_stores()
    print(f"  found {len(stores)} stores\n")

    prices = defaultdict(dict)
    categories = {}
    ok = 0

    for i, (num, meta) in enumerate(sorted(stores.items()), 1):
        label = f"{meta['address']}, {meta['city']}"
        print(f"[{i}/{len(stores)}] {label}")
        try:
            menu = fetch_menu(num)
        except Exception as e:
            print(f"  ! menu failed: {e}", file=sys.stderr)
            continue
        for name, price in menu.items():
            prices[name][num] = price
        ok += 1
        time.sleep(REQUEST_DELAY)

    if ok == 0:
        print("No menus fetched — aborting so the existing data file is kept.", file=sys.stderr)
        return 1

    # Keep only items sold at most stores, so comparisons are apples-to-apples.
    threshold = max(2, ok // 2)
    items = []
    for name, by_store in prices.items():
        if len(by_store) < threshold:
            continue
        vals = list(by_store.values())
        items.append({
            "name": name,
            "min": min(vals),
            "max": max(vals),
            "stores": by_store,
        })
    items.sort(key=lambda x: x["name"].lower())

    payload = {
        "updated": time.strftime("%Y-%m-%d %H:%M %Z"),
        "storeCount": ok,
        "stores": [stores[n] for n in sorted(stores)],
        "items": items,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1)

    dropped = len(prices) - len(items)
    print(f"\nWrote {OUT}")
    print(f"  {ok} stores, {len(items)} comparable items ({dropped} regional items skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
