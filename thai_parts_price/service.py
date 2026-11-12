"""Glue used by the web page: wanted items in -> JSON-able dict out."""
from concurrent.futures import ThreadPoolExecutor

from . import optimize, scrape, search, shipping

MAX_ITEMS = 20
MAX_QUERY = 80
MAX_QTY = 999


def safe_url(shop: str, url: str) -> str:
    """Only hand out links that stay on the shop's own site (scraped data is not trusted)."""
    return url if url.startswith(scrape.SHOPS[shop] + "/") else scrape.SHOPS[shop]


def clean_items(raw) -> list[optimize.Want]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("no items")
    wants = []
    for r in raw[:MAX_ITEMS]:
        q = str(r.get("query", "")).strip()[:MAX_QUERY]
        try:
            qty = max(1, min(MAX_QTY, int(r.get("qty", 1))))
        except (TypeError, ValueError):
            qty = 1
        if q:
            wants.append(optimize.Want(q, qty))
    if not wants:
        raise ValueError("no items")
    return wants


def _offer_json(shop, o):
    return {"name": o.product.name, "unit": o.unit, "partial": o.partial,
            "url": safe_url(shop, o.product.url)}


def build(wants, found, rates) -> dict:
    """found[i] = {shop: ShopResult} for wants[i] (pure: no network)."""
    items, ok_w, ok_o = [], [], []
    for w, res in zip(wants, found):
        offers = {s: o for s, r in res.items() if (o := optimize.pick_offer(r.hits))}
        items.append({"query": w.query, "qty": w.qty, "found": bool(offers),
                      "offers": {s: _offer_json(s, o) for s, o in offers.items()},
                      "tried": sorted({q for r in res.values() for q in r.queries})[:6]})
        if offers:
            ok_w.append(w)
            ok_o.append(offers)
    out = {"items": items, "plan": None, "compare": []}
    if not ok_w:
        return out
    plan = optimize.best_plan(ok_w, ok_o, rates)
    out["plan"] = {
        "total": plan.total, "items_total": plan.items_total, "shipping_total": plan.shipping_total,
        "lines": [{
            "shop": ln.shop, "subtotal": ln.subtotal, "fee": ln.fee,
            "option": ln.option.name.split(" แจ้งโอน")[0] if ln.option else "",
            "free_at": ln.option.free_at() if ln.option else None,
            "items": [{"query": w.query, "qty": w.qty, **_offer_json(ln.shop, o)} for w, o in ln.items],
        } for ln in plan.lines]}
    for name, p in optimize.baselines(ok_w, ok_o, rates).items():
        kind = {"kind": "single", "shop": name[len("everything from "):]} \
            if name.startswith("everything from ") else {"kind": "per_item"}
        out["compare"].append({**kind, "total": p.total, "diff": round(p.total - plan.total, 2)})
    return out


def run(raw_items, rates=None, searcher=search.smart_search) -> dict:
    wants = clean_items(raw_items)
    rates = rates or shipping.load()
    with ThreadPoolExecutor(max_workers=4) as ex:
        found = list(ex.map(lambda w: searcher(w.query), wants))
    return build(wants, found, rates)
