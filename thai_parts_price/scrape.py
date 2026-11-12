"""Scrape product name / price / url from Lnwshop-based Thai electronics shops.

allnewstep, cybertice and arduitronics all run on Lnwshop, so one parser
covers the three of them: /search?q=<query> returns server-rendered HTML where
each product has <div class="product_price" realprice="65">.
"""
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape

SHOPS = {
    "allnewstep": "https://www.allnewstep.com",
    "cybertice": "https://www.cybertice.com",
    "arduitronics": "https://www.arduitronics.com",
}

UA = "Mozilla/5.0 (thai-parts-price; price comparison for personal use)"

_NAME = re.compile(r'class="product_name" title="[^"]*"><a href="(?P<href>[^"]+)"[^>]*>(?P<name>[^<]+)</a>')
_PRICE = re.compile(r'class="product_price[^"]*" realprice="(?P<price>[\d.]+)"')
_IMAGE = re.compile(r'<img class="productImage[^"]*"[^>]*data-src="(?P<src>https://[^"]+)"')


@dataclass
class Product:
    shop: str
    name: str
    price: float
    url: str
    in_stock: bool
    image: str = ""


def fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse(shop: str, base: str, page: str) -> list[Product]:
    out = []
    # every product sits in its own <... class="productArea productItem"> block
    for blk in page.split('class="productArea productItem"')[1:]:
        n, pr = _NAME.search(blk), _PRICE.search(blk)
        if not n or not pr:
            continue
        price = float(pr["price"])
        # price 0 = "coming soon" / not for sale; sold-out items say so after the price
        if price <= 0:
            continue
        sold_out = bool(re.search(r"สินค้าหมด|หมดแล้ว|out of stock", blk[pr.end():pr.end() + 400], re.I))
        img = _IMAGE.search(blk)
        out.append(Product(
            shop=shop,
            name=unescape(n["name"]).strip(),
            price=price,
            url=urllib.parse.urljoin(base + "/", n["href"]),
            in_stock=not sold_out,
            image=img["src"] if img else "",
        ))
    return out


def search(shop: str, query: str) -> list[Product]:
    base = SHOPS[shop]
    page = fetch(f"{base}/search?q={urllib.parse.quote_plus(query)}")
    return parse(shop, base, page)


def search_all(query: str) -> list[Product]:
    results = []
    for shop in SHOPS:
        try:
            results += search(shop, query)
        except Exception as e:  # one shop being down must not kill the others
            print(f"[{shop}] failed: {e}")
    return results
