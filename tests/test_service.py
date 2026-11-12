import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from thai_parts_price import service
from thai_parts_price.scrape import Product, SHOPS
from thai_parts_price.search import Hit, ShopResult
from thai_parts_price.shipping import Option

RATES = {s: [Option("1", "EMS", "money", steps=[(0, 50), (1500, 0)])] for s in SHOPS}


def result(shop, name, price, url=None):
    p = Product(shop, name, price, url or SHOPS[shop] + "/product/1/x", True)
    return ShopResult(shop, [Hit(p, 1.0, True, 1.0)], ["q"])


class Clean(unittest.TestCase):
    def test_limits(self):
        w = service.clean_items([{"query": "a" * 500, "qty": 99999}, {"query": "  ", "qty": 1}, {"query": "b", "qty": "x"}])
        self.assertEqual(len(w), 2)
        self.assertEqual(len(w[0].query), service.MAX_QUERY)
        self.assertEqual((w[0].qty, w[1].qty), (service.MAX_QTY, 1))

    def test_empty_is_error(self):
        for bad in (None, [], [{"query": ""}], "x"):
            with self.assertRaises(ValueError):
                service.clean_items(bad)


class Build(unittest.TestCase):
    def test_links_stay_on_the_shop(self):
        evil = result("cybertice", "ESP32 board", 100, "javascript:alert(1)")
        d = service.build(service.clean_items([{"query": "esp32"}]), [{"cybertice": evil}], RATES)
        self.assertTrue(d["plan"]["lines"][0]["items"][0]["url"].startswith("https://www.cybertice.com"))

    def test_plan_and_missing_item(self):
        wants = service.clean_items([{"query": "dht11", "qty": 2}, {"query": "zzz"}])
        found = [{"allnewstep": result("allnewstep", "DHT11 sensor", 25)}, {}]
        d = service.build(wants, found, RATES)
        self.assertEqual([i["found"] for i in d["items"]], [True, False])
        self.assertEqual(d["plan"]["total"], 25 * 2 + 50)
        self.assertEqual(d["compare"][0]["kind"], "per_item")

    def test_nothing_found(self):
        d = service.build(service.clean_items([{"query": "zzz"}]), [{}], RATES)
        self.assertIsNone(d["plan"])


if __name__ == "__main__":
    unittest.main()
