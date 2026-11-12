"""CLI:  python -m thai_parts_price "esp32 devkit" "dht11 x3" "ตัวต้านทาน 10k x20"

Each argument is one wanted item; "xN" at the end (or "N x" at the start) is the quantity.
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from . import optimize, search, shipping


def parse_item(text: str) -> optimize.Want:
    m = re.search(r"\s*[x×]\s*(\d+)\s*$", text, re.I) or re.match(r"\s*(\d+)\s*[x×]\s+", text, re.I)
    if m:
        return optimize.Want((text[:m.start()] + text[m.end():]).strip(), int(m.group(1)))
    return optimize.Want(text.strip(), 1)


def baht(x: float) -> str:
    return f"{x:,.0f}" if x == int(x) else f"{x:,.2f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="thai-parts-price", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items", nargs="*", help='wanted items, e.g. "dht11 x3"')
    ap.add_argument("--refresh-shipping", action="store_true",
                    help="re-read every shop's shipping rules from its cart (no order is placed)")
    a = ap.parse_args(argv)

    if a.refresh_shipping:
        d = shipping.refresh()
        print("shipping rules saved", d["fetched"])
        if not a.items:
            return 0
    if not a.items:
        ap.print_help()
        return 1

    rates = shipping.load()
    wants = [parse_item(t) for t in a.items]
    with ThreadPoolExecutor(max_workers=4) as ex:
        found = list(ex.map(lambda w: search.smart_search(w.query), wants))

    ok_w, ok_o = [], []
    for w, res in zip(wants, found):
        offers = {s: o for s, r in res.items() if (o := optimize.pick_offer(r.hits))}
        if not offers:
            print(f"! nothing found for '{w.query}' - try another word")
            continue
        ok_w.append(w)
        ok_o.append(offers)
    if not ok_w:
        return 1

    print()
    for w, offers in zip(ok_w, ok_o):
        print(f"{w.query} x{w.qty}")
        for s, o in sorted(offers.items(), key=lambda kv: kv[1].unit):
            flag = " (partial match)" if o.partial else ""
            print(f"   {s:13} {baht(o.unit):>7}  {o.product.name[:60]}{flag}")

    plan = optimize.best_plan(ok_w, ok_o, rates)
    print("\n=== cheapest basket ===")
    for ln in plan.lines:
        opt = ln.option.name.split(" แจ้งโอน")[0][:40] if ln.option else "-"
        print(f"{ln.shop}  items {baht(ln.subtotal)} + shipping {baht(ln.fee)} ({opt}) = {baht(ln.total)}")
        for w, o in ln.items:
            print(f"     {w.qty} x {baht(o.unit):>6}  {o.product.name[:55]}")
            print(f"              {o.product.url}")
    print(f"TOTAL {baht(plan.total)}  (items {baht(plan.items_total)} + shipping {baht(plan.shipping_total)})")

    print("\ncompared with:")
    for name, p in optimize.baselines(ok_w, ok_o, rates).items():
        diff = p.total - plan.total
        print(f"   {name:42} {baht(p.total):>8}" + (f"   (+{baht(diff)})" if diff > 0.005 else "   (same)"))
    print("\nPrices and shipping change; check at checkout. Shipping = cheapest delivery option per shop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
