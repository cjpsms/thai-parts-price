"""Find the cheapest way to buy a whole shopping list across shops.

Shipping is paid once per shop and depends on that shop's subtotal (e.g. free
above 1,500), so "cheapest shop per item" is not the cheapest basket.  We try
every way of assigning items to shops and keep the lowest total of
items + shipping of every shop actually used.
"""
import itertools
from dataclasses import dataclass, field

from . import shipping

EXACT_LIMIT = 2_000_000     # max assignments to brute-force; above this, local search
NEAR_BEST = 0.15            # candidates within this rank of the shop's best match compete on price


@dataclass
class Want:
    query: str
    qty: int = 1


@dataclass
class Offer:
    product: object          # scrape.Product
    partial: bool = False    # not every query word was found in the name

    @property
    def unit(self) -> float:
        return self.product.price


def pick_offer(hits) -> "Offer | None":
    """Best in-stock hit of one shop for one wanted item (cheapest among the closest matches)."""
    live = [h for h in hits if h.product.in_stock]
    pool = [h for h in live if h.full]
    partial = False
    if not pool:
        pool = [h for h in live if h.coverage >= 0.6]
        partial = True
    if not pool:
        return None
    top = max(h.rank for h in pool)
    close = [h for h in pool if h.rank >= top - NEAR_BEST]
    best = min(close, key=lambda h: h.product.price)
    return Offer(best.product, partial)


@dataclass
class ShopLine:
    shop: str
    items: list = field(default_factory=list)   # [(Want, Offer)]
    subtotal: float = 0.0
    fee: float = 0.0
    option: object = None                       # shipping.Option

    @property
    def total(self) -> float:
        return self.subtotal + self.fee


@dataclass
class Plan:
    lines: list
    total: float
    items_total: float
    shipping_total: float


def _build(assign, wants, offers, rates) -> Plan:
    lines = {}
    for i, shop in enumerate(assign):
        ln = lines.setdefault(shop, ShopLine(shop))
        ln.items.append((wants[i], offers[i][shop]))
        ln.subtotal += offers[i][shop].unit * wants[i].qty
    for ln in lines.values():
        ln.fee, ln.option = shipping.cheapest_fee(rates.get(ln.shop, []), ln.subtotal)
    ls = sorted(lines.values(), key=lambda l: l.shop)
    items_total = sum(l.subtotal for l in ls)
    ship = sum(l.fee for l in ls)
    return Plan(ls, items_total + ship, items_total, ship)


def _cost(assign, wants, offers, rates) -> float:
    sub = {}
    for i, shop in enumerate(assign):
        sub[shop] = sub.get(shop, 0.0) + offers[i][shop].unit * wants[i].qty
    return sum(sub.values()) + sum(shipping.cheapest_fee(rates.get(s, []), v)[0] for s, v in sub.items())


def best_plan(wants, offers, rates):
    """offers[i] = {shop: Offer} for wants[i]. Returns the cheapest Plan."""
    choices = [sorted(o) for o in offers]
    size = 1
    for c in choices:
        size *= len(c)
    if size <= EXACT_LIMIT:
        best = min(itertools.product(*choices), key=lambda a: _cost(a, wants, offers, rates))
    else:  # many items: start from the cheapest shop per item, then move single items while it helps
        best = tuple(min(c, key=lambda s: offers[i][s].unit) for i, c in enumerate(choices))
        improved = True
        while improved:
            improved = False
            for i, c in enumerate(choices):
                for s in c:
                    cand = best[:i] + (s,) + best[i + 1:]
                    if _cost(cand, wants, offers, rates) < _cost(best, wants, offers, rates) - 1e-9:
                        best, improved = cand, True
    return _build(best, wants, offers, rates)


def baselines(wants, offers, rates) -> dict:
    """Plans people would make by hand, to show what the optimiser saves."""
    out = {}
    out["cheapest per item (shipping added after)"] = _build(
        tuple(min(o, key=lambda s: o[s].unit) for o in offers), wants, offers, rates)
    for shop in sorted({s for o in offers for s in o}):
        if all(shop in o for o in offers):
            out[f"everything from {shop}"] = _build((shop,) * len(wants), wants, offers, rates)
    return out
