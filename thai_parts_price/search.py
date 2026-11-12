"""Smart search on top of the shops' dumb search boxes.

The shops answer badly: sometimes too loose (every product that contains
"arduino"), sometimes empty (one unknown word kills the whole query), results
are capped (20/30/50) and there is no page 2.  So we:

1. tokenize the query (Thai words are split with a small built-in dictionary),
2. search the full query first,
3. score every result locally by how many query words its name contains,
4. only if a shop gave fewer than `min_good` full matches, try more rounds:
   drop one word at a time (generic words first), then the single most
   specific word, then English/Thai synonyms.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import scrape

# Thai <-> English pairs used for splitting joined Thai text and for matching
# names that are written in the other language.  Extend freely.
SYNONYMS = {
    "ตัวต้านทาน": ["resistor"],
    "ตัวเก็บประจุ": ["capacitor"],
    "ไดโอด": ["diode"],
    "ทรานซิสเตอร์": ["transistor"],
    "เซ็นเซอร์": ["sensor", "เซนเซอร์"],
    "เซนเซอร์": ["sensor", "เซ็นเซอร์"],
    "อุณหภูมิ": ["temperature", "temp"],
    "ความชื้น": ["humidity"],
    "รีเลย์": ["relay"],
    "มอเตอร์": ["motor"],
    "เซอร์โว": ["servo"],
    "จอ": ["lcd", "display", "oled", "tft"],
    "แสดงผล": ["display", "lcd", "oled"],
    "บอร์ด": ["board"],
    "โมดูล": ["module"],
    "สายไฟ": ["wire", "cable", "jumper"],
    "สายจัมเปอร์": ["jumper", "wire"],
    "แบตเตอรี่": ["battery"],
    "แบตเตอรี": ["battery"],
    "ปุ่มกด": ["button", "switch"],
    "สวิตช์": ["switch"],
    "สวิตซ์": ["switch"],
    "ลำโพง": ["speaker", "buzzer"],
    "ไฟ": ["led", "light"],
    "แสง": ["light", "ldr"],
    "ระยะ": ["distance", "ultrasonic"],
    "อัลตราโซนิก": ["ultrasonic"],
    "ไมโครคอนโทรลเลอร์": ["microcontroller", "mcu"],
    "ตัวควบคุม": ["controller", "driver"],
    "ไดรเวอร์": ["driver"],
    "บัดกรี": ["solder"],
    "ขาหยั่ง": ["header", "pin"],
    "เบรดบอร์ด": ["breadboard"],
    "อะแดปเตอร์": ["adapter", "adaptor"],
    "หม้อแปลง": ["transformer"],
    "ไวไฟ": ["wifi"],
    "บลูทูธ": ["bluetooth"],
}

# Words that match almost every product in these shops. They stay in the
# score but weigh little, and are the first to be dropped in retry rounds.
GENERIC = {"arduino", "board", "module", "บอร์ด", "โมดูล", "for", "with", "and",
           "kit", "set", "ชุด", "สำหรับ", "แบบ", "อัน", "ตัว"}

# Words that mean "this is an accessory / a different kind of part". A name with one of
# them is pushed down unless the user typed that word (so "esp32 devkit" prefers the board
# over the "ESP32 ... Screw Shield", and "resistor" over "photoresistor / LDR").
ACCESSORY = {"shield", "case", "box", "sticker", "stand", "holder", "cover", "mount",
             "photoresistor", "ldr", "dependent", "thermistor", "network", "ปรับค่าได้", "กล่อง", "เคส", "สติกเกอร์", "ขาตั้ง"}

_THAI = re.compile(r"[฀-๿]+")
_SPLIT = re.compile(r"[\s,;/+]+")
_SQUASH = re.compile(r"[\s\-_.()/\\\[\]]+")
_DICT = sorted(SYNONYMS, key=len, reverse=True)


def squash(s: str) -> str:
    """lowercase + drop spaces/dashes/dots so 'ESP-32S' ~ 'esp32s', 'UNO R3' ~ 'unor3'."""
    return _SQUASH.sub("", s.lower())


def split_thai(word: str) -> list[str]:
    """Split a Thai run into dictionary words (longest match first).

    Only splits when the dictionary covers the WHOLE run; otherwise the word is
    kept as written, so unknown words are never cut into wrong pieces.
    """
    out, i = [], 0
    while i < len(word):
        hit = next((d for d in _DICT if word.startswith(d, i)), None)
        if not hit:
            return [word]
        out.append(hit)
        i += len(hit)
    return out


@dataclass(frozen=True)
class Token:
    text: str                      # as the user wrote it (lowercased)
    alts: tuple[str, ...] = ()     # synonyms, squashed

    @property
    def generic(self) -> bool:
        return self.text in GENERIC

    @property
    def weight(self) -> float:
        if self.generic:
            return 0.25
        return 1.5 if any(c.isdigit() for c in self.text) else 1.0

    def matches(self, squashed_name: str) -> bool:
        if squash(self.text) in squashed_name:
            return True
        return any(a and a in squashed_name for a in self.alts)


def tokenize(query: str) -> list[Token]:
    tokens = []
    for raw in _SPLIT.split(query.lower().strip()):
        if not raw:
            continue
        pieces = []
        # keep Thai and non-Thai runs apart: "ตัวต้านทาน10k" -> ตัวต้านทาน, 10k
        for part in re.findall(r"[฀-๿]+|[^฀-๿]+", raw):
            pieces += split_thai(part) if _THAI.fullmatch(part) else [part]
        for p in pieces:
            tokens.append(Token(p, tuple(squash(a) for a in SYNONYMS.get(p, ()))))
    return tokens


@dataclass
class Hit:
    product: scrape.Product
    coverage: float        # weighted share of query words found in the name, 0..1
    full: bool             # every query word found
    lead: float = 0.0      # share of the matched weight found at the START of the name, 0..1
    penalty: float = 0.0   # 0.3 when the name looks like an accessory / different part

    @property
    def rank(self) -> float:
        # A board is named "Arduino UNO R3 ..."; accessories say "... for Arduino UNO"
        # at the end. Matches near the start of the name rank higher.
        return round(self.coverage + 0.25 * self.lead - self.penalty, 2)


LEAD_CHARS = 30


def score(products, tokens: list[Token]) -> list[Hit]:
    total = sum(t.weight for t in tokens) or 1.0
    hits = []
    for p in products:
        name = squash(p.name)
        got = [t for t in tokens if t.matches(name)]
        got_w = sum(t.weight for t in got)
        head = name[:LEAD_CHARS]
        lead_w = sum(t.weight for t in got if t.matches(head))
        wanted = {squash(t.text) for t in tokens}
        pen = 0.3 if any(squash(a) in name and squash(a) not in wanted
                         and not any(squash(a) in w for w in wanted) for a in ACCESSORY) else 0.0
        hits.append(Hit(p, got_w / total, len(got) == len(tokens),
                        lead_w / got_w if got_w else 0.0, pen))
    return hits


def retry_queries(tokens: list[Token]) -> list[str]:
    """Queries to try, in order, when the full query was not enough."""
    out = []
    if len(tokens) > 1:
        # drop one word at a time, generic words first, then the least specific
        for t in sorted(tokens, key=lambda t: (not t.generic, t.weight)):
            rest = [x.text for x in tokens if x is not t]
            out.append(" ".join(rest))
        # the single most specific word alone
        best = max(tokens, key=lambda t: (not t.generic, t.weight, len(t.text)))
        out.append(best.text)
    # English synonym of Thai words, so Thai input finds English-named products
    for t in tokens:
        if _THAI.fullmatch(t.text) and t.alts:
            swapped = [t.alts[0] if x is t else x.text for x in tokens]
            out.append(" ".join(swapped))
    seen, uniq = set(), []
    for q in out:
        if q and q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq


@dataclass
class ShopResult:
    shop: str
    hits: list[Hit] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)   # what we actually sent


def search_shop(shop: str, query: str, tokens=None, min_good: int = 3,
                max_rounds: int = 5, fetcher=scrape.search) -> ShopResult:
    tokens = tokens or tokenize(query)
    res = ShopResult(shop)
    by_url = {}
    todo = [query] + retry_queries(tokens)
    for q in todo[:max_rounds]:
        try:
            found = fetcher(shop, q)
        except Exception:
            found = []
        res.queries.append(q)
        for p in found:
            by_url.setdefault(p.url, p)
        hits = score(by_url.values(), tokens)
        if sum(h.full for h in hits) >= min_good:
            break
    res.hits = sorted(score(by_url.values(), tokens),
                      key=lambda h: (-h.full, -h.rank, h.product.price))
    return res


def smart_search(query: str, shops=None, min_good: int = 3, max_rounds: int = 5,
                 fetcher=scrape.search) -> dict[str, ShopResult]:
    """Search every shop in parallel; each shop retries on its own only if it needs to."""
    shops = list(shops or scrape.SHOPS)
    tokens = tokenize(query)
    with ThreadPoolExecutor(max_workers=len(shops)) as ex:
        futs = {s: ex.submit(search_shop, s, query, tokens, min_good, max_rounds, fetcher)
                for s in shops}
    return {s: f.result() for s, f in futs.items()}
