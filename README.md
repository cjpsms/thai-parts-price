# thai-parts-price

Compare prices of Arduino / electronics parts across Thai online shops and find the cheapest way to buy a whole shopping list, **including shipping**.

เทียบราคาอุปกรณ์ Arduino / อิเล็กทรอนิกส์จากร้านออนไลน์ในไทย แล้วหาว่าซื้อร้านไหนถูกสุด **รวมค่าส่ง** ทั้งตะกร้า

## Why not just compare item prices?

Shipping is paid once per shop. A shop that is 10 baht dearer per item can still be cheaper overall if you buy several things there and pay shipping once. So the tool optimises the whole basket: item prices + shipping of every shop used.

## Shops

| Shop | Status |
|---|---|
| [allnewstep.com](https://www.allnewstep.com) (ArduinoAll) | scraping works |
| [cybertice.com](https://www.cybertice.com) | scraping works |
| [arduitronics.com](https://www.arduitronics.com) | scraping works |

All three run on Lnwshop, so one parser covers them (`/search?q=` returns server-rendered HTML).

## Status

Work in progress, built step by step.

- [x] Scraper: name, price, url, in stock
- [x] Smart search: word splitting (Thai dictionary), EN/TH synonyms, local relevance scoring, retry rounds only when a shop gives too few exact matches
- [x] Shipping rules per shop, read from the shops' carts (fee steps, free-shipping threshold)
- [x] Basket optimiser (which item from which shop, items + shipping)
- [x] CLI
- [x] Web page (local server)

## Usage

Python 3.10+, standard library only.

```
python -m thai_parts_price "esp32 devkit" "dht11 x3" "ตัวต้านทาน 10k x20" "relay 1 channel"
```

Each argument is one wanted item; `xN` at the end is the quantity. It searches the three shops, picks the best match per shop, then prints the cheapest basket (which item from which shop) with items + shipping, and compares it with what you would pay buying the cheapest item each time.

### Web page (recommended)

```
python -m thai_parts_price --serve        # http://127.0.0.1:4027/
```

A small local web server (standard library only, 127.0.0.1) with separate pages and files in `thai_parts_price/web/`. It works like a shop aggregator and **never guesses what a product is**:

1. search a word: products from all shops show up with picture, name and price,
2. you pick the ones that are right (several shops for one wanted item means "any of these is fine"),
3. the cheapest split is calculated from your picks only, with shipping, and compared with other ways of buying.

The basket is remembered in your browser. `/shipping` shows each shop's shipping rules. A search can be shared as a link: `/?q=esp32+devkit`. Only a fixed list of files is served; scraped links and images are only shown if they stay on the shops' own hosts.

The command line (above) picks products automatically from the search words, so it can pick a wrong item; use the web page when it matters.

```
python -m thai_parts_price --refresh-shipping   # re-read the shops' shipping rules
python tests/test_search.py && python tests/test_optimize.py && python tests/test_service.py
```

## Shipping

Shipping is paid once per shop and depends on that shop's subtotal (for example free above 1,500 baht). The rules are read from each shop's own cart (Lnwshop keeps the cart in a cookie; no order is placed, nothing is paid) and saved in `data/shipping_rates.json`. For each shop the cheapest delivery option is used; "pick up at the shop" is ignored. The optimiser tries every way of splitting the list between shops, so putting more items in one shop can win even when its items cost more.

## How the search works

The shops' own search boxes are poor: loose or empty results, capped at 20/30/50 items, no page 2. `search.py` wraps them:

1. split the query into words (Thai is split with a small built-in dictionary, `10k` stays one word),
2. search the full query, then score every result by how many of your words its name contains (`ESP-32S` matches `esp32`; Thai words match their English names),
3. only if a shop gave fewer than 3 exact matches, retry: drop one word at a time (generic words like "arduino" first), then the most specific word alone, then English synonyms of Thai words. At most 5 requests per shop per query.

Names that look like accessories or a different part (shield, case, LDR, thermistor, resistor network...) are ranked lower unless you typed that word. Known limit: a shop's search may never show a product that its ranking buries; if an item is not found, try another word.

## Notes

Reads public search pages only, one request per shop per query. Prices and shipping change; always check at checkout.

## License

[0BSD](LICENSE): do whatever you want with it.
