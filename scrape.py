#!/usr/bin/env python3
"""
Fetch per-store menu prices for every chain across the Las Vegas valley.

Both chains expose price data to unauthenticated requests, but differently:

  Taco Bell  a plain JSON API used by their site and app; no headers needed.
  Del Taco   an Olo ordering backend that rejects requests without the
             `X-Olo-Request: 1` header ("Anti forgery validation failed").

Each adapter returns the same shape, so adding a chain means writing one
function. Writes data/vegas_prices.json, which build.py embeds.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vegas_prices.json")
REQUEST_DELAY = 0.4  # be a polite client

# Sweep the valley: each locator returns only a page of nearby results.
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

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def fetch(url, headers=None, payload=None, tries=3):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        hdrs["Content-Type"] = "application/json"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdrs, data=body)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


# --------------------------------------------------------------------------
# Taco Bell
# --------------------------------------------------------------------------

TB = "https://www.tacobell.com/tacobellwebservices/v4/tacobell"


def taco_bell():
    stores = {}
    for lat, lng in SEED_POINTS:
        try:
            data = fetch(f"{TB}/stores?latitude={lat}&longitude={lng}")
        except Exception as e:
            print(f"  ! Taco Bell locator failed at {lat},{lng}: {e}", file=sys.stderr)
            continue
        for s in data.get("nearByStores", []):
            num, geo = s.get("storeNumber"), s.get("geoPoint") or {}
            if not num or num in stores or not geo.get("latitude"):
                continue
            a = s.get("address") or {}
            stores[num] = {
                "store": f"tb:{num}", "chain": "Taco Bell",
                "address": a.get("line1"), "city": a.get("town"), "zip": a.get("postalCode"),
                "lat": geo.get("latitude"), "lng": geo.get("longitude"),
            }
        time.sleep(REQUEST_DELAY)

    prices = defaultdict(dict)
    ok = 0
    for i, (num, meta) in enumerate(sorted(stores.items()), 1):
        print(f"  [{i}/{len(stores)}] {meta['address']}, {meta['city']}")
        try:
            data = fetch(f"{TB}/products/menu/{num}")
        except Exception as e:
            print(f"    ! menu failed: {e}", file=sys.stderr)
            continue
        for cat in data.get("menuProductCategories", []):
            for p in cat.get("products", []):
                price = (p.get("price") or {}).get("value")
                name = (p.get("name") or "").strip()
                if price and name:
                    cur = prices[name].get(meta["store"])
                    if cur is None or price < cur:
                        prices[name][meta["store"]] = price
        ok += 1
        time.sleep(REQUEST_DELAY)
    return list(stores.values()), prices, ok


# --------------------------------------------------------------------------
# Del Taco (Olo)
# --------------------------------------------------------------------------

DT = "https://order.deltaco.com/api"
OLO = {"X-Olo-Request": "1"}   # without this the API answers 403


def del_taco():
    stores = {}
    for lat, lng in SEED_POINTS:
        try:
            data = fetch(f"{DT}/vendors/search", headers=OLO, payload={
                "latitude": lat, "longitude": lng,
                "handoffMode": "CounterPickup", "timeWantedMode": "Immediate",
            })
        except Exception as e:
            print(f"  ! Del Taco locator failed at {lat},{lng}: {e}", file=sys.stderr)
            continue
        for v in data.get("vendor-search-results", []):
            slug = v.get("slug")
            addr = v.get("address") or {}
            # the locator reaches into Utah and California; keep the valley
            if not slug or slug in stores or v.get("state") != "NV":
                continue
            if not v.get("latitude"):
                continue
            stores[slug] = {
                "store": f"dt:{slug}", "chain": "Del Taco",
                "address": (v.get("streetAddress") or "").title(),
                "city": addr.get("city"), "zip": addr.get("postalCode"),
                "lat": v.get("latitude"), "lng": v.get("longitude"),
            }
        time.sleep(REQUEST_DELAY)

    prices = defaultdict(dict)
    ok = 0
    for i, (slug, meta) in enumerate(sorted(stores.items()), 1):
        print(f"  [{i}/{len(stores)}] {meta['address']}, {meta['city']}")
        try:
            data = fetch(f"{DT}/vendors/{slug}?handoffMode=CounterPickup&modelVariant=v19", headers=OLO)
        except Exception as e:
            print(f"    ! menu failed: {e}", file=sys.stderr)
            continue
        for p in data.get("products", []):
            # combos price through option groups and carry no baseCost
            price, name = p.get("baseCost"), (p.get("name") or "").strip()
            if price and name:
                cur = prices[name].get(meta["store"])
                if cur is None or price < cur:
                    prices[name][meta["store"]] = price
        ok += 1
        time.sleep(REQUEST_DELAY)
    return list(stores.values()), prices, ok


CHAINS = [("Taco Bell", taco_bell), ("Del Taco", del_taco)]


def main():
    all_stores, all_items, counts = [], [], {}

    for label, fn in CHAINS:
        print(f"\n=== {label} ===")
        try:
            stores, prices, ok = fn()
        except Exception as e:
            print(f"  ! {label} failed entirely: {e}", file=sys.stderr)
            continue
        if not ok:
            print(f"  ! {label}: no menus fetched, skipping", file=sys.stderr)
            continue

        # Keep items sold at most of the chain's stores so comparisons are
        # apples-to-apples rather than flagging a regional item as missing.
        threshold = max(2, ok // 2)
        kept = 0
        for name, by_store in prices.items():
            if len(by_store) < threshold:
                continue
            vals = list(by_store.values())
            all_items.append({
                "id": f"{label}|{name}", "name": name, "chain": label,
                "min": min(vals), "max": max(vals), "stores": by_store,
            })
            kept += 1
        # A store whose whole menu is regional (the stadium location, say)
        # contributes nothing comparable — drop it so counts match the rankings.
        priced = {st for name, by_store in prices.items() if len(by_store) >= threshold
                  for st in by_store}
        stores = [s for s in stores if s["store"] in priced]
        dropped = ok - len(stores)
        all_stores.extend(stores)
        counts[label] = {"stores": len(stores), "items": kept}
        print(f"  {len(stores)} stores, {kept} comparable items "
              f"({len(prices) - kept} regional items skipped"
              f"{f', {dropped} store(s) with no comparable menu' if dropped else ''})")

    if not all_items:
        print("\nNothing scraped — keeping the existing data file.", file=sys.stderr)
        return 1

    all_items.sort(key=lambda i: (i["chain"], i["name"].lower()))
    all_stores.sort(key=lambda s: (s["chain"], s["address"] or ""))

    payload = {
        "updated": time.strftime("%Y-%m-%d %H:%M %Z"),
        "chains": [c for c, _ in CHAINS if c in counts],
        "counts": counts,
        "storeCount": len(all_stores),
        "stores": all_stores,
        "items": all_items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)

    print(f"\nWrote {OUT}")
    for c, n in counts.items():
        print(f"  {c}: {n['stores']} stores, {n['items']} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
