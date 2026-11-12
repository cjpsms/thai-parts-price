"""Shipping rules per shop, read from the shops' own cart (no order is ever placed).

Lnwshop keeps the cart in a cookie: PUT /api/lnwme/cart/cookie adds a product,
and the cart JSON at lnw.me then lists every delivery option of the shop with
its price rule (by order total, or a fixed price).  Rules are saved in
data/shipping_rates.json so normal runs need no extra requests; refresh them
with `python -m thai_parts_price --refresh-shipping`.
"""
import http.cookiejar
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date

from . import scrape

RATES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "shipping_rates.json")
_H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


@dataclass
class Option:
    id: str
    name: str
    kind: str                                    # "money" = step by order total, "fixed"
    price: float = 0.0                           # used when kind == "fixed"
    steps: list = field(default_factory=list)    # [(min_money, price), ...] sorted by min

    def fee(self, subtotal: float) -> float:
        if self.kind == "fixed":
            return self.price
        fee = self.steps[0][1] if self.steps else 0.0
        for lo, price in self.steps:
            if subtotal >= lo:
                fee = price
        return fee


    def free_at(self):
        """Order total from which this option is free, or None."""
        zeros = [lo for lo, price in self.steps if price == 0 and lo > 0]
        return min(zeros) if self.kind == "money" and zeros else None


def parse_options(shipping_types: dict) -> list[Option]:
    """Turn the cart's `shipping_types` into Options, skipping pickup and unsupported formats."""
    out = []
    for sid, t in shipping_types.items():
        fmt = t.get("format")
        if fmt == "free" or t.get("pickup_type") or "รับเอง" in (t.get("name") or ""):
            continue  # collecting at the shop is not delivery
        if fmt == "fixed":
            out.append(Option(str(sid), t["name"], "fixed", price=float(t.get("price") or 0)))
        elif fmt == "money":
            conds = (t.get("config") or {}).get("conditions") or []
            steps = sorted((float(c["rule"]["min_money"] or 0), float(c["price"])) for c in conds)
            if steps:
                out.append(Option(str(sid), t["name"], "money", steps=steps))
        # other formats (e.g. by weight) are skipped: product weights are 0 in these shops
    return out


def cheapest_fee(options: list[Option], subtotal: float):
    """(fee, option) of the cheapest delivery option for this order total."""
    if not options:
        return 0.0, None
    return min(((o.fee(subtotal), o) for o in options), key=lambda x: x[0])


# ---- reading the rules from the shop ----------------------------------------

def _cart(base: str, product_id: str) -> dict:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    body = json.dumps({"action": "addProductQuantity", "product_id": product_id, "quantity": 1}).encode()
    req = urllib.request.Request(base + "/api/lnwme/cart/cookie", method="PUT", data=body,
                                 headers={**_H, "Content-Type": "application/json"})
    out = json.loads(op.open(req, timeout=20).read().decode())
    web, oid, sec = re.match(r"https://lnw\.me/cart/([^/]+)/(\d+)\?s=(\w+)",
                             out["cart"]["checkout_url"]).groups()
    url = f"https://lnw.me/api/shop/{web}/cart/{oid}?s={sec}"
    return json.loads(op.open(urllib.request.Request(url, headers=_H), timeout=20).read().decode())["cart"]


def fetch_shop_options(shop: str) -> list[Option]:
    base = scrape.SHOPS[shop]
    for q in ("dht11", "led", "resistor"):
        for p in scrape.search(shop, q):
            m = re.search(r"/product/(\d+)", p.url)
            if p.in_stock and m:
                return parse_options(_cart(base, m.group(1))["shipping_types"])
    raise RuntimeError(f"{shop}: no product found to read shipping from")


def refresh(path: str = RATES_PATH) -> dict:
    data = {"fetched": date.today().isoformat(), "shops": {}}
    for shop in scrape.SHOPS:
        opts = fetch_shop_options(shop)
        data["shops"][shop] = [o.__dict__ for o in opts]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def load(path: str = RATES_PATH) -> dict[str, list[Option]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {shop: [Option(**{**o, "steps": [tuple(s) for s in o["steps"]]}) for o in opts]
            for shop, opts in data["shops"].items()}
