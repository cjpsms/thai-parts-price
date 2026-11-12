"use strict";
const SHOP_NAME = { allnewstep: "allnewstep", cybertice: "cybertice", arduitronics: "arduitronics" };
const EXAMPLES = ["esp32 devkit", "dht11 x3", "ตัวต้านทาน 10k x20", "relay 1 channel", "ultrasonic sensor"];
const ICON_SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
const ICON_X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';

const $ = (id) => document.getElementById(id);
const baht = (n) => Number(n).toLocaleString("th-TH", { maximumFractionDigits: 2 });

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function link(href, text) {
  const a = el("a", "", text);
  if (/^https:\/\//.test(href)) { a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}

/* ---- input rows ---------------------------------------------------- */
function parseLine(text) {
  const m = text.match(/\s*[x×]\s*(\d+)\s*$/i) || text.match(/^\s*(\d+)\s*[x×]\s+/i);
  if (!m) return { query: text.trim(), qty: 1 };
  return { query: (text.slice(0, m.index) + text.slice(m.index + m[0].length)).trim(), qty: +m[1] };
}

function addRow(query = "", qty = 1, focus = true) {
  const row = el("div", "row");
  const f = el("label", "field"); f.insertAdjacentHTML("afterbegin", ICON_SEARCH);
  const input = el("input"); input.type = "text"; input.placeholder = "ค้นหาสินค้า เช่น esp32 devkit"; input.value = query;
  input.maxLength = 120; input.setAttribute("aria-label", "ชื่อสินค้า");
  f.append(input);
  const q = el("label", "field qty"); q.append(el("span", "", "จำนวน"));
  const n = el("input"); n.type = "number"; n.min = 1; n.max = 999; n.value = qty; n.setAttribute("aria-label", "จำนวน");
  q.append(n);
  const del = el("button", "icon-btn"); del.type = "button"; del.setAttribute("aria-label", "ลบรายการ");
  del.insertAdjacentHTML("afterbegin", ICON_X);
  del.onclick = () => { row.remove(); if (!$("rows").children.length) addRow("", 1, false); };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); if (input.value.trim()) addRow(); } });
  input.addEventListener("paste", (e) => {
    const t = (e.clipboardData || window.clipboardData).getData("text");
    if (!/\n/.test(t)) return;
    e.preventDefault();
    const lines = t.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    lines.forEach((ln, i) => { const p = parseLine(ln); if (i === 0 && !input.value) { input.value = p.query; n.value = p.qty; } else addRow(p.query, p.qty, false); });
  });
  row.append(f, q, del);
  $("rows").append(row);
  if (focus) input.focus();
}

function readItems() {
  const items = [];
  for (const row of $("rows").children) {
    const [t, n] = row.querySelectorAll("input");
    const p = parseLine(t.value);
    const boxQty = Math.max(1, Math.min(999, parseInt(n.value, 10) || 1));
    // "dht11 x3" with the quantity box left at 1 means 3
    if (p.query) items.push({ query: p.query, qty: boxQty === 1 ? Math.min(999, p.qty) : boxQty });
  }
  return items;
}

/* ---- results ------------------------------------------------------- */
function summary(d) {
  const p = d.plan, box = el("div", "summary");
  const a = el("div", "panel");
  a.append(el("h2", "", "ยอดรวมที่ถูกสุด"));
  const big = el("div", "big", baht(p.total)); big.append(el("small", "", "บาท")); a.append(big);
  a.append(el("div", "sub", `สินค้า ${baht(p.items_total)} + ค่าส่ง ${baht(p.shipping_total)} บาท, ซื้อจาก ${p.lines.length} ร้าน`));
  const per = d.compare.find((c) => c.kind === "per_item");
  if (per && per.diff > 0.005) a.append(el("div", "save", `ประหยัด ${baht(per.diff)} บาท เมื่อเทียบกับเลือกถูกสุดทีละชิ้น`));
  else a.append(el("div", "save flat", "เท่ากับวิธีเลือกถูกสุดทีละชิ้น"));
  const b = el("div", "panel");
  b.append(el("h2", "", "เทียบกับวิธีอื่น"));
  const ul = el("ul", "cmp");
  const best = el("li", "best"); best.append(el("span", "", "แบบที่แนะนำ"), el("b", "", baht(p.total))); ul.append(best);
  for (const c of d.compare) {
    const li = el("li");
    li.append(el("span", "", c.kind === "single" ? `ซื้อทั้งหมดที่ ${c.shop}` : "ถูกสุดทีละชิ้น + ค่าส่ง"));
    const r = el("span"); r.append(el("b", "", baht(c.total)));
    if (c.diff > 0.005) r.append(el("span", "diff", `+${baht(c.diff)}`));
    li.append(r); ul.append(li);
  }
  b.append(ul);
  box.append(a, b);
  return box;
}

function shopCard(ln) {
  const c = el("div", "panel shopcard");
  const h = el("div", "shophead");
  h.append(el("h3", "", ln.shop), el("span", "tot", `${baht(ln.subtotal + ln.fee)} บาท`));
  c.append(h);
  for (const it of ln.items) {
    const row = el("div", "line");
    row.append(el("span", "q", `${it.qty} x`));
    const nm = el("div", "nm"); nm.append(link(it.url, it.name));
    const s = el("small", "", it.query);
    if (it.partial) s.append(el("span", "badge partial", "ตรงบางคำ ตรวจก่อนซื้อ"));
    nm.append(s);
    row.append(nm, el("span", "pr", `${baht(it.unit)} = ${baht(it.unit * it.qty)}`));
    c.append(row);
  }
  const sh = el("div", "ship");
  const l = el("span"); l.append(el("span", "", `สินค้า ${baht(ln.subtotal)} บาท + ส่ง ${ln.option || ""} `));
  if (ln.fee === 0) l.append(el("span", "badge free", "ส่งฟรี"));
  sh.append(l, el("b", "", ln.fee === 0 ? "0" : `${baht(ln.fee)} บาท`));
  c.append(sh);
  if (ln.fee > 0 && ln.free_at && ln.subtotal < ln.free_at)
    c.append(el("div", "note", `ซื้อเพิ่มอีก ${baht(ln.free_at - ln.subtotal)} บาท ร้านนี้ส่งฟรี`));
  return c;
}

function priceTable(d) {
  const shops = [...new Set(d.items.flatMap((i) => Object.keys(i.offers)))].sort();
  const c = el("div", "panel shopcard");
  c.append(el("h2", "", "ราคาต่อชิ้นของทุกร้าน"));
  const sc = el("div", "scroll"), t = el("table"), thead = el("thead"), hr = el("tr");
  hr.append(el("th", "", "รายการ"));
  shops.forEach((s) => hr.append(el("th", "", s)));
  thead.append(hr); t.append(thead);
  const tb = el("tbody");
  for (const it of d.items.filter((i) => i.found)) {
    const tr = el("tr"), prices = Object.values(it.offers).map((o) => o.unit), min = Math.min(...prices);
    tr.append(el("td", "", `${it.query}${it.qty > 1 ? " x" + it.qty : ""}`));
    for (const s of shops) {
      const o = it.offers[s], td = el("td");
      if (!o) { td.className = "none"; td.textContent = "ไม่พบ"; }
      else { td.className = o.unit === min ? "min" : ""; td.append(link(o.url, baht(o.unit))); }
      tr.append(td);
    }
    tb.append(tr);
  }
  t.append(tb); sc.append(t); c.append(sc);
  return c;
}

function render(d) {
  const out = $("out"); out.replaceChildren();
  const miss = d.items.filter((i) => !i.found);
  if (miss.length) {
    const m = el("div", "missing");
    m.textContent = "ไม่เจอสินค้า: " + miss.map((i) => i.query).join(", ") + " ลองเปลี่ยนคำค้น (เช่น ตัดคำทั่วไป หรือใช้ชื่อรุ่น)";
    out.append(m);
  }
  if (!d.plan) return;
  out.append(summary(d));
  d.plan.lines.forEach((ln) => out.append(shopCard(ln)));
  out.append(priceTable(d));
  out.append(el("p", "note", "ราคาจริงตอนจ่ายเงินอาจต่างไปเล็กน้อย ค่าส่งคิดจากวิธีส่งที่ถูกสุดของแต่ละร้าน"));
}

async function submit(e) {
  e.preventDefault();
  const items = readItems();
  const out = $("out"), go = $("go");
  if (!items.length) { out.replaceChildren(el("div", "error", "ใส่ชื่อสินค้าอย่างน้อย 1 รายการ")); return; }
  const qs = new URLSearchParams(); items.forEach((i) => qs.append("q", i.qty > 1 ? `${i.query} x${i.qty}` : i.query));
  history.replaceState(null, "", "/?" + qs.toString());
  go.disabled = true; go.textContent = "กำลังค้น...";
  out.replaceChildren(el("div", "skel"), el("div", "skel"));
  try {
    const r = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    render(await r.json());
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    out.replaceChildren(el("div", "error", "ค้นไม่สำเร็จ (" + err.message + ") ลองใหม่อีกครั้ง"));
  } finally {
    go.disabled = false; go.textContent = "หาร้านที่ถูกสุด";
  }
}

$("form").addEventListener("submit", submit);
$("add").onclick = () => addRow();
EXAMPLES.forEach((t) => {
  const b = el("button", "", t); b.type = "button";
  b.onclick = () => {
    const p = parseLine(t), last = $("rows").lastElementChild, inp = last && last.querySelector("input");
    if (inp && !inp.value) { inp.value = p.query; last.querySelectorAll("input")[1].value = p.qty; }
    else addRow(p.query, p.qty, false);
  };
  $("try").append(b);
});

// shareable link: /?q=dht11+x3&q=esp32+devkit fills the list and searches right away
const shared = new URLSearchParams(location.search).getAll("q").map((x) => x.trim()).filter(Boolean).slice(0, 20);
if (shared.length) {
  shared.forEach((t) => { const p = parseLine(t); addRow(p.query, p.qty, false); });
  $("form").requestSubmit();
} else addRow();
