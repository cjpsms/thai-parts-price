"""Glue for the web page.

Flow: the page searches (`search`), the USER picks the products that are right, and
`plan` only ever works with those picks - nothing is guessed about what a product is.
A basket "group" is one wanted thing; it may hold picks from several shops, meaning
"any of these is fine", and the optimiser chooses the shop.
"""
from urllib.parse import urlparse

from . import optimize, scrape, search, shipping

MAX_GROUPS = 20
MAX_OFFERS = 12
MAX_NAME = 200
MAX_QTY = 999
MAX_RESULTS = 150
MIN_COVERAGE = 0.2          # hide results that share almost no word with the query


def safe_url(shop: str, url) -> str:
    """Links must stay on the shop's own site (scraped / posted data is not trusted)."""
    base = scrape.SHOPS[shop]
    return url if isinstance(url, str) and url.startswith(base + "/") else base


def safe_image(url) -> str:
    """Only https images from the shops' image host (lnwfile.com)."""
    if not isinstance(url, str):
        return ""
    try:
        u = urlparse(url)
    except ValueError:
        return ""
    host = u.hostname or ""
    return url if u.scheme == "https" and (host == "lnwfile.com" or host.endswith(".lnwfile.com")) else ""


# ---- search -----------------------------------------------------------------

def search_products(query: str, searcher=search.smart_search) -> dict:
    query = str(query or "").strip()[:120]
    if not query:
        raise ValueError("empty query")
    found = searcher(query)
    rows = []
    for shop, res in found.items():
        for h in res.hits:
            if h.coverage < MIN_COVERAGE:
                continue
            p = h.product
            rows.append({"shop": shop, "name": p.name, "price": p.price, "in_stock": p.in_stock,
                         "url": safe_url(shop, p.url), "image": safe_image(p.image),
                         "full": h.full, "rank": h.rank})
    rows.sort(key=lambda r: (not r["full"], -r["rank"], r["price"]))
    return {"query": query, "results": rows[:MAX_RESULTS],
            "tried": sorted({q for r in found.values() for q in r.queries})[:8]}


# ---- plan from the user's picks ---------------------------------------------

def clean_groups(raw) -> list[tuple[optimize.Want, dict]]:
    """Validate the posted basket. Returns [(Want, {shop: Offer})]; raises ValueError."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("empty basket")
    out = []
    for g in raw[:MAX_GROUPS]:
        if not isinstance(g, dict):
            raise ValueError("bad group")
        name = str(g.get("name", "")).strip()[:MAX_NAME] or "?"
        try:
            qty = max(1, min(MAX_QTY, int(g.get("qty", 1))))
        except (TypeError, ValueError):
            qty = 1
        offers = {}
        for o in (g.get("offers") or [])[:MAX_OFFERS]:
            shop = o.get("shop") if isinstance(o, dict) else None
            if shop not in scrape.SHOPS:
                continue
            try:
                price = float(o.get("price"))
            except (TypeError, ValueError):
                continue
            if not (0 < price < 1_000_000):
                continue
            prod = scrape.Product(shop, str(o.get("name", ""))[:MAX_NAME], price,
                                  safe_url(shop, o.get("url")), True, safe_image(o.get("image")))
            # same shop picked twice for one wanted thing: keep the cheaper
            if shop not in offers or price < offers[shop].unit:
                offers[shop] = optimize.Offer(prod)
        if offers:
            out.append((optimize.Want(name, qty), offers))
    if not out:
        raise ValueError("nothing selected")
    return out


def _offer_json(o):
    return {"name": o.product.name, "unit": o.unit, "url": o.product.url, "image": o.product.image}


def build_plan(groups, rates) -> dict:
    wants = [w for w, _ in groups]
    offers = [o for _, o in groups]
    plan = optimize.best_plan(wants, offers, rates)
    out = {
        "groups": [{"name": w.query, "qty": w.qty, "offers": {s: _offer_json(o) for s, o in os.items()}}
                   for w, os in groups],
        "plan": {
            "total": plan.total, "items_total": plan.items_total, "shipping_total": plan.shipping_total,
            "lines": [{
                "shop": ln.shop, "subtotal": ln.subtotal, "fee": ln.fee,
                "option": ln.option.name.split(" แจ้งโอน")[0] if ln.option else "",
                "free_at": ln.option.free_at() if ln.option else None,
                "items": [{"group": w.query, "qty": w.qty, **_offer_json(o)} for w, o in ln.items],
            } for ln in plan.lines]},
        "compare": [],
    }
    for name, p in optimize.baselines(wants, offers, rates).items():
        kind = {"kind": "single", "shop": name[len("everything from "):]} \
            if name.startswith("everything from ") else {"kind": "per_item"}
        out["compare"].append({**kind, "total": p.total, "diff": round(p.total - plan.total, 2)})
    return out


def plan_from_picks(raw, rates=None) -> dict:
    return build_plan(clean_groups(raw), rates or shipping.load())
