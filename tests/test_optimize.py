import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from thai_parts_price.scrape import Product
from thai_parts_price.optimize import Want, Offer, best_plan, baselines, pick_offer
from thai_parts_price.search import Hit
from thai_parts_price.shipping import Option, parse_options, cheapest_fee

# every shop: 50 baht shipping, free from 1500
RATES = {s: [Option("1", "EMS", "money", steps=[(0, 50), (1500, 0)])] for s in ("A", "B")}


def O(price, shop="A"):
    return Offer(Product(shop, "x", price, "u", True))


class Shipping(unittest.TestCase):
    def test_steps_and_fixed(self):
        o = Option("1", "EMS", "money", steps=[(0, 40), (1500, 0)])
        self.assertEqual((o.fee(0), o.fee(1499.99), o.fee(1500)), (40, 40, 0))
        self.assertEqual(Option("2", "J&T", "fixed", price=70).fee(5000), 70)

    def test_cheapest_option_wins_and_pickup_skipped(self):
        types = {
            "1": {"name": "EMS", "format": "money", "config": {"conditions": [
                {"rule": {"min_money": 0}, "price": 50}, {"rule": {"min_money": 1500}, "price": 0}]}},
            "2": {"name": "J&T", "format": "fixed", "price": 30},
            "3": {"name": "รับเองที่โกดัง", "format": "free"},
        }
        opts = parse_options(types)
        self.assertEqual(len(opts), 2)                      # pickup dropped
        self.assertEqual(cheapest_fee(opts, 100)[0], 30)
        self.assertEqual(cheapest_fee(opts, 2000)[0], 0)


class Basket(unittest.TestCase):
    def test_dearer_shop_wins_when_shipping_paid_once(self):
        # cj's example: shop B is 10 baht dearer per item, but both items are in B
        # and A only has one of them cheaper -> two shippings lose to one.
        wants = [Want("a"), Want("b")]
        offers = [{"A": O(100), "B": O(110)}, {"B": O(100)}]
        plan = best_plan(wants, offers, RATES)
        self.assertEqual([l.shop for l in plan.lines], ["B"])
        self.assertEqual(plan.total, 210 + 50)
        naive = baselines(wants, offers, RATES)["cheapest per item (shipping added after)"]
        self.assertEqual(naive.total, 100 + 100 + 50 + 50)  # two shops, two shippings
        self.assertLess(plan.total, naive.total)

    def test_free_shipping_threshold_changes_the_split(self):
        # moving the 200 item to B pushes B over 1500 -> its shipping becomes free
        wants = [Want("big"), Want("small")]
        offers = [{"A": O(1400), "B": O(1400)}, {"A": O(190), "B": O(200)}]
        plan = best_plan(wants, offers, RATES)
        self.assertEqual(len(plan.lines), 1)
        self.assertEqual(plan.shipping_total, 0)
        self.assertEqual(plan.total, 1400 + 190)

    def test_quantity_counts(self):
        plan = best_plan([Want("r", 20)], [{"A": O(5)}], RATES)
        self.assertEqual(plan.items_total, 100)

    def test_many_items_falls_back_to_local_search(self):
        import thai_parts_price.optimize as opt
        old, opt.EXACT_LIMIT = opt.EXACT_LIMIT, 1
        try:
            wants = [Want(str(i)) for i in range(6)]
            offers = [{"A": O(100), "B": O(105)} for _ in wants]
            self.assertEqual(len(best_plan(wants, offers, RATES).lines), 1)
        finally:
            opt.EXACT_LIMIT = old


class Picking(unittest.TestCase):
    def H(self, price, full=True, cov=1.0, stock=True, lead=1.0):
        return Hit(Product("A", "n", price, "u%s" % price, stock), cov, full, lead)

    def test_cheapest_among_close_matches_skips_out_of_stock(self):
        o = pick_offer([self.H(50, stock=False), self.H(120), self.H(100)])
        self.assertEqual(o.unit, 100)

    def test_partial_only_when_no_full_match(self):
        o = pick_offer([self.H(80, full=False, cov=0.7)])
        self.assertTrue(o.partial)
        self.assertIsNone(pick_offer([self.H(80, full=False, cov=0.3)]))


if __name__ == "__main__":
    unittest.main()
