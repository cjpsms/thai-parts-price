# thai-parts-price

Compare prices of Arduino / electronics parts across Thai online shops and find the cheapest way to buy a whole shopping list, **including shipping**.

เทียบราคาอุปกรณ์ Arduino / อิเล็กทรอนิกส์จากร้านออนไลน์ในไทย แล้วหาว่าซื้อร้านไหนถูกสุด **รวมค่าส่ง** ทั้งตะกร้า

## Why not just compare item prices?

Shipping is paid once per shop. A shop that is 10 baht dearer per item can still be cheaper overall if you buy several things there and pay shipping once. So the tool optimises the whole basket: item prices + shipping of every shop used.

## Shops

| Shop | Status |
|---|---|
| allnewstep.com (ArduinoAll) | scraping works |
| cybertice.com | scraping works |
| arduitronics.com | scraping works |

All three run on Lnwshop, so one parser covers them (`/search?q=` returns server-rendered HTML).

## Status

Work in progress, built step by step.

- [x] Scraper: name, price, url, in stock
- [x] Smart search: word splitting (Thai dictionary), EN/TH synonyms, local relevance scoring, retry rounds only when a shop gives too few exact matches
- [ ] Shipping rules per shop (fee, free-shipping threshold)
- [ ] Basket optimiser (which item from which shop)
- [ ] CLI

## Usage

Python 3.10+, standard library only.

```python
from thai_parts_price.scrape import search_all

for p in sorted(search_all("arduino uno"), key=lambda p: p.price)[:5]:
    print(p.shop, p.price, p.name)
```

## How the search works

The shops' own search boxes are poor: loose or empty results, capped at 20/30/50 items, no page 2. `search.py` wraps them:

1. split the query into words (Thai is split with a small built-in dictionary, `10k` stays one word),
2. search the full query, then score every result by how many of your words its name contains (`ESP-32S` matches `esp32`; Thai words match their English names),
3. only if a shop gave fewer than 3 exact matches, retry: drop one word at a time (generic words like "arduino" first), then the most specific word alone, then English synonyms of Thai words. At most 5 requests per shop per query.

Known limit: a shop's search may never show a product that its ranking buries. A local index of each shop's catalogue would fix that; not done yet.

## Notes

Reads public search pages only, one request per shop per query. Prices and shipping change; always check at checkout.
