# Vegas Taco Index

Finds the cheapest Taco Bell for a given item across the Las Vegas valley.

Taco Bell locations are largely franchised, and franchisees set their own prices.
The same item can cost meaningfully more a few miles away — most sharply at
tourist locations. This pulls per-store prices and ranks them by price and
driving distance.

## Use it

Open `index.html` in any browser. Search an item, tap it, see every location
ranked cheapest first. Tap **Use my location** to add distances and get a
"drive X miles, save $Y" verdict.

**Basket mode.** Use the +/- steppers to build an actual order, then tap
**Compare basket** to rank every location by what that whole order costs. This
is usually where the money is: a single taco varies by 50c, but a five-item
order swings over $3 across the valley.

A basket total only means something at a location that stocks every item in it,
so stores missing anything are excluded from the ranking and the view says how
many were dropped. The basket persists in `localStorage`, as does your
starting point.

**Published artifacts cannot use geolocation.** The artifact renders in an
iframe with no `allow="geolocation"`, so the browser denies the request no
matter what the viewer permits on their device. Use the **Set your area**
dropdown there instead — it ranks by distance from any of 11 valley areas.

Run locally and the browser's real location works, but only in a secure
context: `https://` or `localhost`, never a `file://` path.

```bash
python3 -m http.server 8777
```

Then open http://localhost:8777

## Refresh the prices

```bash
python3 scrape.py && python3 build.py
```

`scrape.py` takes about two minutes and rewrites `data/vegas_prices.json`.
`build.py` embeds that data into `index.html` and `vegas-taco-index.html`. Prices move
slowly — every few days is plenty, and re-scraping more often just adds load
with no new information.

## Files

| File | Purpose |
|---|---|
| `scrape.py` | Fetches stores and per-store menus, writes `data/vegas_prices.json` |
| `price_changed.py` | Exits 0 only if real prices moved; ignores the timestamp |
| `build.py` | Injects the data into the template, writes `app.html` + `artifact.html` |
| `app.template.html` | The app — markup, styles, and logic, with a `__DATA__` placeholder |
| `index.html` | Standalone page. Open this one; also the GitHub Pages entry point. |
| `vegas-taco-index.html` | Same page without a `<head>`, for publishing as a Claude Artifact |
| `data/vegas_prices.json` | Scraped prices |

Edit `app.template.html`, never `index.html` — the latter is regenerated.

## How the data works

Two undocumented endpoints behind tacobell.com, also used by their mobile app.
Neither needs an account, key, or login:

```
GET /tacobellwebservices/v4/tacobell/stores?latitude={lat}&longitude={lng}
GET /tacobellwebservices/v4/tacobell/products/menu/{storeNumber}
```

The store locator returns roughly 14 results per query, so `scrape.py` sweeps a
grid of eight seed points across the valley and dedupes by store number — that
is the difference between finding 14 stores and finding 55.

Menu items appearing at fewer than half the stores are dropped, so comparisons
stay apples-to-apples rather than flagging a regional item as "unavailable".

## Caveats

- **Unofficial.** These endpoints are undocumented and can change or break
  without notice. Using them likely conflicts with Taco Bell's terms of service.
  Fine for personal use; get advice before building a business on it.
- **Prices are a snapshot**, not live. Check the timestamp in the footer.
- **Base prices only.** App-exclusive deals, rewards offers, and promotions are
  not included, and logging in would be required to see those.
- **Excludes delivery apps** on purpose. DoorDash and Uber Eats mark prices up
  15–25%, which would make in-store comparisons meaningless.
- Distances are straight-line, not driving distance.

## Extending to other chains

The structure generalizes: `scrape.py` produces a normalized
`{stores, items, prices}` shape, and the app reads only that. Adding McDonald's
or Wendy's means writing a new fetcher that emits the same shape — their web
ordering flows also expose per-store pricing without a login, though each needs
its own adapter since there is no shared menu API.

## Hosting on GitHub Pages

Pages serves `index.html` from the repository root, over HTTPS. That matters:
**the browser's real location only works in a secure context**, so on Pages the
"Use my location" button behaves normally. Inside a published Claude Artifact it
never can — that iframe is not granted the geolocation permission — which is why
the app also offers a manual starting point.

### Prices refresh themselves

`.github/workflows/refresh-prices.yml` re-scrapes every Monday at 13:00 UTC,
rebuilds both pages, and pushes only if prices actually moved. Pages redeploys
on its own. Nothing to run by hand.

Whether prices "actually moved" is decided by `price_changed.py`, not by
`git diff`. Every scrape restamps `updated`, and that timestamp is baked into
the built HTML, so a plain diff always looks changed — the script compares only
the store and item data, and names the items that were repriced.

Trigger one immediately from the Actions tab, or:

```bash
gh workflow run refresh-prices.yml
gh run watch
```

To refresh locally instead:

```bash
python3 scrape.py && python3 build.py
git commit -am "Refresh prices" && git push
```

Pages redeploys within a minute or so.
