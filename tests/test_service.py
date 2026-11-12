import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from thai_parts_price import service
from thai_parts_price.scrape import Product, SHOPS
from thai_parts_price.search import Hit, ShopResult
from thai_parts_price.shipping import Option

RATES = {s: [Option("1", "EMS", "money", steps=[(0, 50), (1500, 0)])] for s in SHOPS}
A, C = "allnewstep", "cybertice"


def pick(shop, price, name="x", url=None, image=""):
    return {"shop": shop, "price": price, "name": name, "url": url or SHOPS[shop] + "/product/1/x", "image": image}


class Safety(unittest.TestCase):
    def test_links_and_images(self):
        self.assertEqual(service.safe_url(A, "javascript:alert(1)"), SHOPS[A])
        self.assertEqual(service.safe_url(A, "https://evil.example/" + SHOPS[A]), SHOPS[A])
        self.assertEqual(service.safe_url(A, SHOPS[A] + "/product/3/x"), SHOPS[A] + "/product/3/x")
        self.assertEqual(service.safe_image("https://cu.lnwfile.com/a.jpg"), "https://cu.lnwfile.com/a.jpg")
        for bad in ("http://cu.lnwfile.com/a.jpg", "https://evil.example/a.jpg", "javascript:1", None, 5):
            self.assertEqual(service.safe_image(bad), "")


class Clean(unittest.TestCase):
    def test_rejects_empty_and_garbage(self):
        for bad in (None, [], "x", [5], [{"name": "a", "offers": []}], [{"name": "a", "offers": [{"shop": "nope", "price": 5}]}]):
            with self.assertRaises(ValueError):
                service.clean_groups(bad)

    def test_bad_prices_and_limits(self):
        g = [{"name": "n" * 999, "qty": 99999, "offers": [pick(A, -5), pick(A, "abc"), pick(A, 10), pick(A, 8)]}]
        (w, offers), = service.clean_groups(g)
        self.assertEqual(len(w.query), service.MAX_NAME)
        self.assertEqual(w.qty, service.MAX_QTY)
        self.assertEqual(offers[A].unit, 8)               # same shop twice -> cheaper one


class Plan(unittest.TestCase):
    def test_uses_only_what_the_user_picked_and_one_shipping_wins(self):
        groups = [
            {"name": "dht11", "qty": 3, "offers": [pick(A, 110), pick(C, 100)]},
            {"name": "relay", "qty": 1, "offers": [pick(A, 100)]},
        ]
        d = service.build_plan(service.clean_groups(groups), RATES)
        self.assertEqual([l["shop"] for l in d["plan"]["lines"]], [A])   # 330+100+50 beats 300+100+100
        self.assertEqual(d["plan"]["total"], 3 * 110 + 100 + 50)
        self.assertEqual(d["compare"][0]["kind"], "per_item")
        self.assertEqual({i["group"] for i in d["plan"]["lines"][0]["items"]}, {"dht11", "relay"})
        self.assertGreater(d["compare"][0]["diff"], 0)

    def test_single_pick_is_forced(self):
        d = service.build_plan(service.clean_groups([{"name": "a", "offers": [pick(C, 200)]}]), RATES)
        self.assertEqual(d["plan"]["lines"][0]["shop"], C)


class Search(unittest.TestCase):
    def test_sorted_full_first_and_junk_hidden(self):
        def hit(name, price, full, cov, lead=1.0):
            return Hit(Product(A, name, price, SHOPS[A] + "/product/1/" + name, True, "https://i.lnwfile.com/a.jpg"), cov, full, lead)
        res = ShopResult(A, [hit("cheap partial", 5, False, 0.5), hit("exact dear", 90, True, 1.0),
                             hit("exact cheap", 40, True, 1.0), hit("junk", 1, False, 0.1)], ["q"])
        d = service.search_products("dht11", searcher=lambda q: {A: res})
        self.assertEqual([r["name"] for r in d["results"]], ["exact cheap", "exact dear", "cheap partial"])

    def test_empty_query(self):
        with self.assertRaises(ValueError):
            service.search_products("   ", searcher=lambda q: {})


if __name__ == "__main__":
    unittest.main()
