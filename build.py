#!/usr/bin/env python3
"""
Inject scraped price data into app.template.html.

Writes two files from the same template:
  index.html               standalone page (own <head>) — GitHub Pages entry
                           point, and what you open locally
  vegas-taco-index.html    body-only page for publishing as a Claude Artifact,
                           which supplies its own <head> and rejects one of ours
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "vegas_prices.json")
TPL = os.path.join(HERE, "app.template.html")

# Only the standalone build gets these: the Artifact runtime supplies its own
# <head>, and its CSP blocks the sibling files a manifest points at anyway.
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0A0512">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Taco Index">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
</head>
<body>
"""


def main():
    if not os.path.exists(DATA):
        print("No data/vegas_prices.json — run scrape.py first.", file=sys.stderr)
        return 1

    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    # Drop stores that returned no prices so the app never renders a dead row,
    # then restate the counts from what actually ships.
    priced = {s for i in data["items"] for s in i["stores"]}
    data["stores"] = [s for s in data["stores"] if s["store"] in priced]
    data["storeCount"] = len(data["stores"])
    per_chain = {}
    for s_ in data["stores"]:
        per_chain.setdefault(s_["chain"], {"stores": 0, "items": 0})["stores"] += 1
    for i in data["items"]:
        per_chain.setdefault(i["chain"], {"stores": 0, "items": 0})["items"] += 1
    data["counts"] = per_chain
    data["chains"] = [c for c in data.get("chains", per_chain) if c in per_chain]

    with open(TPL, encoding="utf-8") as f:
        tpl = f.read()

    if "__DATA__" not in tpl:
        print("Template is missing the __DATA__ placeholder.", file=sys.stderr)
        return 1

    # ensure_ascii keeps ®/™/… as \u escapes, so the page is byte-safe even if a
    # server sends no charset. </ would otherwise close the script tag early.
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    body = tpl.replace("__DATA__", blob)

    targets = {
        "index.html": HEAD + body + "\n</body>\n</html>\n",
        "vegas-taco-index.html": body,
    }
    for name, content in targets.items():
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote {name}  ({os.path.getsize(path) / 1024:.0f} KB)")

    print(f"  {len(data['stores'])} stores, {len(data['items'])} items, updated {data['updated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
