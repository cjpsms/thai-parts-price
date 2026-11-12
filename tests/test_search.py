import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from thai_parts_price.scrape import Product
from thai_parts_price.search import tokenize, squash, score, retry_queries, search_shop, split_thai


def P(name, price=10, shop="s"):
    return Product(shop, name, price, "http://x/" + name, True)


class Tokens(unittest.TestCase):
    def test_squash_matches_dashes_and_spaces(self):
        t = tokenize("esp32")[0]
        self.assertTrue(t.matches(squash("ESP-32S DevKit")))
        self.assertTrue(tokenize("uno r3")[1].matches(squash("Arduino UNO-R3")))

    def test_thai_split_only_when_fully_known(self):
        self.assertEqual(split_thai("เซ็นเซอร์อุณหภูมิ"), ["เซ็นเซอร์", "อุณหภูมิ"])
        self.assertEqual(split_thai("จองตั๋ว"), ["จองตั๋ว"])  # unknown -> kept whole

    def test_thai_and_digits_apart(self):
        self.assertEqual([t.text for t in tokenize("ตัวต้านทาน10k")], ["ตัวต้านทาน", "10k"])

    def test_thai_word_matches_english_name(self):
        hit = score([P("Resistor 10K 1/4W")], tokenize("ตัวต้านทาน 10k"))[0]
        self.assertTrue(hit.full)


class Scoring(unittest.TestCase):
    def test_generic_word_alone_scores_low(self):
        toks = tokenize("arduino uno")
        a, b = score([P("IC arduino compatible"), P("Arduino UNO R3")], toks)
        self.assertFalse(a.full)
        self.assertTrue(b.full)
        self.assertLess(a.coverage, 0.3)


    def test_name_starting_with_query_beats_accessory(self):
        toks = tokenize("arduino uno")
        board, acc = score([P("Arduino UNO R3 board"),
                            P("2.4 inch TFT LCD Touch Screen Module shield for Arduino UNO")], toks)
        self.assertTrue(board.full and acc.full)
        self.assertGreater(board.rank, acc.rank)


class Rounds(unittest.TestCase):
    def test_drops_generic_first_then_single_word(self):
        qs = retry_queries(tokenize("arduino uno r3 clone"))
        self.assertEqual(qs[0], "uno r3 clone")      # generic word dropped first
        self.assertIn("r3", qs)                      # most specific word alone (digit)

    def test_no_retry_when_enough_good_results(self):
        calls = []
        def fetch(shop, q):
            calls.append(q)
            return [P("ESP32 DevKit %d" % i) for i in range(5)]
        r = search_shop("s", "esp32", fetcher=fetch)
        self.assertEqual(calls, ["esp32"])
        self.assertEqual(len(r.hits), 5)

    def test_retries_when_zero_results(self):
        def fetch(shop, q):
            return [] if q == "arduino uno r3 clone" else [P("Arduino UNO R3 Clone", 99), P("Arduino UNO R3", 150)]
        r = search_shop("s", "arduino uno r3 clone", fetcher=fetch, min_good=1)
        self.assertEqual(len(r.queries), 2)
        self.assertTrue(r.hits[0].full)
        self.assertEqual(r.hits[0].product.price, 99)  # full match, cheapest first

    def test_failed_fetch_is_not_fatal(self):
        def fetch(shop, q):
            raise OSError("down")
        self.assertEqual(search_shop("s", "esp32", fetcher=fetch).hits, [])


if __name__ == "__main__":
    unittest.main()
