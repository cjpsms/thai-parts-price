"use strict";
const baht = (n) => Number(n).toLocaleString("th-TH", { maximumFractionDigits: 2 });
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

function describe(o) {
  if (o.kind === "fixed") return `${baht(o.price)} บาท คงที่`;
  const s = o.steps, parts = [];
  s.forEach(([lo, price], i) => {
    const hi = s[i + 1] ? s[i + 1][0] : null;
    const range = hi !== null ? `ยอดไม่ถึง ${baht(hi)} บาท` : `ยอดตั้งแต่ ${baht(lo)} บาท`;
    parts.push(`${range}: ${price === 0 ? "ส่งฟรี" : baht(price) + " บาท"}`);
  });
  return parts.join("   |   ");
}

fetch("/api/shipping").then((r) => r.json()).then((d) => {
  document.getElementById("when").textContent = "อ่านล่าสุด " + d.fetched;
  const box = document.getElementById("rules");
  for (const [shop, opts] of Object.entries(d.shops)) {
    const c = el("div", "panel shopcard");
    c.append(el("h2", "", shop));
    for (const o of opts) {
      const row = el("div", "line"); row.style.gridTemplateColumns = "1fr";
      const nm = el("div", "nm"); nm.append(el("span", "", o.name.split(" แจ้งโอน")[0]));
      nm.append(el("small", "", describe(o)));
      row.append(nm); c.append(row);
    }
    box.append(c);
  }
}).catch(() => { document.getElementById("rules").append(el("div", "error", "โหลดกฎค่าส่งไม่ได้")); });
