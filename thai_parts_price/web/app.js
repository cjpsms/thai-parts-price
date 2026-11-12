"use strict";
/* Search -> the user picks products -> basket -> cheapest split.
   Nothing is guessed: the calculation only uses products the user selected. */

const EXAMPLES = ["esp32 devkit", "dht11", "ตัวต้านทาน 10k", "relay 1 channel", "ultrasonic sensor"];
const SHOPS = ["allnewstep", "cybertice", "arduitronics"];
const KEY = "tpp.basket.v1";
const MAX_OFFERS = 12;
const ICON_X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';

const $ = (id) => document.getElementById(id);
const baht = (n) => Number(n).toLocaleString("th-TH", { maximumFractionDigits: 2 });

const state = {
  q: "", qtyHint: 1, results: [], tried: [], loading: false, error: "",
  shop: "all", sort: "best",
  groups: [],          // [{id, name, qty, offers:[{shop,name,price,url,image}]}]
  target: null,        // group id that new picks go into (null = a new group on the first pick)
};

/* ---- tiny DOM helpers (never innerHTML with data) -------------------- */
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function link(href, text, cls) {
  const a = el("a", cls || "", text);
  if (/^https:\/\//.test(href)) { a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}
function thumb(src) {
  if (/^https:\/\//.test(src)) {
    const i = el("img");
    i.loading = "lazy"; i.alt = ""; i.referrerPolicy = "no-referrer"; i.src = src;
    i.onerror = () => i.replaceWith(el("div", "ph"));
    return i;
  }
  return el("div", "ph");
}
function iconBtn(label, onclick) {
  const b = el("button", "x"); b.type = "button"; b.setAttribute("aria-label", label);
  b.insertAdjacentHTML("afterbegin", ICON_X); b.onclick = onclick;
  return b;
}
function parseLine(text) {
  const m = text.match(/\s*[x×]\s*(\d+)\s*$/i) || text.match(/^\s*(\d+)\s*[x×]\s+/i);
  if (!m) return { query: text.trim(), qty: 1 };
  return { query: (text.slice(0, m.index) + text.slice(m.index + m[0].length)).trim(), qty: Math.min(999, +m[1]) };
}
let uid = 0;
const newId = () => "g" + Date.now().toString(36) + (uid++);

/* ---- basket storage -------------------------------------------------- */
function save() { try { localStorage.setItem(KEY, JSON.stringify(state.groups)); } catch (e) { /* private mode etc. */ } }
function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
    if (!Array.isArray(raw)) return;
    state.groups = raw.slice(0, 20).map((g) => ({
      id: newId(), name: String(g.name || "?").slice(0, 200),
      qty: Math.max(1, Math.min(999, parseInt(g.qty, 10) || 1)),
      offers: (Array.isArray(g.offers) ? g.offers : []).slice(0, MAX_OFFERS)
        .filter((o) => o && SHOPS.includes(o.shop) && Number(o.price) > 0)
        .map((o) => ({ shop: o.shop, name: String(o.name || "").slice(0, 200), price: Number(o.price), url: String(o.url || ""), image: String(o.image || "") })),
    })).filter((g) => g.offers.length);
  } catch (e) { /* ignore a broken saved basket */ }
}
const targetGroup = () => state.groups.find((g) => g.id === state.target);

/* ---- search ---------------------------------------------------------- */
async function doSearch(text) {
  const p = parseLine(text);
  if (!p.query) return;
  state.q = p.query; state.qtyHint = p.qty; state.loading = true; state.error = ""; state.shop = "all";
  const same = state.groups.find((g) => g.name.toLowerCase() === p.query.toLowerCase());
  state.target = same ? same.id : null;
  renderResults(); renderBasket();
  try {
    const r = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: p.query }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    state.results = d.results; state.tried = d.tried;
  } catch (e) {
    state.results = []; state.error = "ค้นไม่สำเร็จ (" + e.message + ") ลองใหม่อีกครั้ง";
  }
  state.loading = false;
  renderResults();
  try { history.replaceState(null, "", "/?q=" + encodeURIComponent(p.query)); } catch (e) { /* ignore */ }
}

const isPicked = (url) => { const g = targetGroup(); return !!g && g.offers.some((o) => o.url === url); };

function toggle(r) {
  let g = targetGroup();
  if (!g) {
    g = { id: newId(), name: state.q, qty: state.qtyHint || 1, offers: [] };
    state.groups.push(g); state.target = g.id;
  }
  const i = g.offers.findIndex((o) => o.url === r.url);
  if (i >= 0) g.offers.splice(i, 1);
  else if (g.offers.length < MAX_OFFERS) g.offers.push({ shop: r.shop, name: r.name, price: r.price, url: r.url, image: r.image });
  if (!g.offers.length) { state.groups = state.groups.filter((x) => x !== g); state.target = null; }
  save(); renderResults(); renderBasket();
}

/* ---- results --------------------------------------------------------- */
function sortedResults() {
  let rows = state.results.filter((r) => state.shop === "all" || r.shop === state.shop);
  const by = { price: (a, b) => a.price - b.price, "price-desc": (a, b) => b.price - a.price };
  if (by[state.sort]) rows = rows.slice().sort(by[state.sort]);
  return rows;
}

function card(r) {
  const picked = isPicked(r.url);
  const c = el("div", "card" + (picked ? " sel" : "") + (r.in_stock ? "" : " oos"));
  const t = el("div", "thumb"); t.append(thumb(r.image)); c.append(t);
  const b = el("div", "cbody");
  const sn = el("div", "shopname"); sn.append(el("span", "badge shop", r.shop));
  if (!r.in_stock) sn.append(el("span", "badge oos", "หมด"));
  else if (!r.full) sn.append(el("span", "badge partial", "ตรงบางคำ"));
  b.append(sn, link(r.url, r.name, "cname"));
  const pr = el("div", "cprice", baht(r.price)); pr.append(el("small", "", "บาท")); b.append(pr);
  const btn = el("button", "pick", picked ? "เลือกแล้ว (กดเพื่อเอาออก)" : "เลือก");
  btn.type = "button"; btn.disabled = !r.in_stock && !picked; btn.setAttribute("aria-pressed", picked);
  btn.onclick = () => toggle(r);
  b.append(btn); c.append(b);
  return c;
}

function renderResults() {
  const box = $("results"); box.replaceChildren();
  if (!state.q) {
    box.append(el("div", "empty", "พิมพ์ชื่อสินค้าแล้วกดค้นหา จะเห็นสินค้าจากทุกร้านพร้อมรูปและราคา เลือกอันที่ใช่ได้เลย"));
    return;
  }
  if (state.loading) {
    box.append(el("p", "status", `กำลังค้น "${state.q}" ใน 3 ร้าน...`));
    for (let i = 0; i < 3; i++) box.append(el("div", "skel"));
    return;
  }
  if (state.error) { box.append(el("div", "error", state.error)); return; }
  if (!state.results.length) {
    box.append(el("div", "missing", `ไม่เจอสินค้าสำหรับ "${state.q}" ลองเปลี่ยนคำ เช่น ใช้ชื่อรุ่น หรือคำสั้นลง`));
    return;
  }
  const tb = el("div", "toolbar");
  const counts = { all: state.results.length };
  SHOPS.forEach((s) => { counts[s] = state.results.filter((r) => r.shop === s).length; });
  ["all", ...SHOPS].forEach((s) => {
    const p = el("button", "pill", `${s === "all" ? "ทุกร้าน" : s} (${counts[s]})`);
    p.type = "button"; p.setAttribute("aria-pressed", state.shop === s);
    p.onclick = () => { state.shop = s; renderResults(); };
    tb.append(p);
  });
  tb.append(el("span", "grow"));
  const sel = el("select", "pill"); sel.setAttribute("aria-label", "เรียงลำดับ");
  [["best", "ตรงที่สุดก่อน"], ["price", "ราคาต่ำ - สูง"], ["price-desc", "ราคาสูง - ต่ำ"]].forEach(([v, t]) => {
    const o = el("option", "", t); o.value = v; if (state.sort === v) o.selected = true; sel.append(o);
  });
  sel.onchange = () => { state.sort = sel.value; renderResults(); };
  tb.append(sel);
  box.append(tb);

  const rows = sortedResults();
  let note = `พบ ${rows.length} รายการสำหรับ "${state.q}"`;
  const extra = state.tried.filter((t) => t !== state.q);
  if (extra.length) note += ` (ค้นเพิ่มด้วยคำ: ${extra.slice(0, 4).join(", ")})`;
  box.append(el("p", "status", note));
  const g = el("div", "grid"); rows.forEach((r) => g.append(card(r))); box.append(g);
}

/* ---- basket ---------------------------------------------------------- */
function qtyControl(g) {
  const w = el("div", "qtyctl");
  const minus = el("button", "", "-"), plus = el("button", "", "+"), inp = el("input");
  minus.type = plus.type = "button"; minus.setAttribute("aria-label", "ลดจำนวน"); plus.setAttribute("aria-label", "เพิ่มจำนวน");
  inp.type = "number"; inp.min = 1; inp.max = 999; inp.value = g.qty; inp.setAttribute("aria-label", "จำนวน");
  const set = (v) => { g.qty = Math.max(1, Math.min(999, parseInt(v, 10) || 1)); inp.value = g.qty; save(); };
  minus.onclick = () => set(g.qty - 1); plus.onclick = () => set(g.qty + 1);
  inp.onchange = () => set(inp.value);
  w.append(minus, inp, plus);
  return w;
}

function removeGroup(g) {
  state.groups = state.groups.filter((x) => x !== g);
  if (state.target === g.id) state.target = null;
  save(); renderBasket(); renderResults();
}

function groupCard(g) {
  const c = el("div", "group" + (g.id === state.target ? " active" : ""));
  const h = el("div", "ghead");
  const name = el("input", "gname"); name.value = g.name; name.maxLength = 200; name.setAttribute("aria-label", "ชื่อรายการ");
  name.onchange = () => { g.name = name.value.trim() || g.name; name.value = g.name; save(); };
  name.onfocus = () => { if (state.target !== g.id) { state.target = g.id; renderResults(); renderBasket(); } };
  h.append(name, qtyControl(g), iconBtn("ลบรายการ", () => removeGroup(g)));
  c.append(h);
  g.offers.forEach((o) => {
    const row = el("div", "goffer");
    const t = el("div", "t"); t.append(link(o.url, o.name), el("span", "", `${o.shop} - ${baht(o.price)} บาท`));
    row.append(thumb(o.image), t, iconBtn("เอาสินค้านี้ออก", () => {
      g.offers = g.offers.filter((x) => x !== o);
      if (!g.offers.length) removeGroup(g); else { save(); renderBasket(); renderResults(); }
    }));
    c.append(row);
  });
  return c;
}

function renderBasket() {
  const b = $("basket"); b.replaceChildren();
  const h = el("h2", "", "ตะกร้า"); h.append(el("small", "", `${state.groups.length} รายการ`)); b.append(h);
  if (!state.groups.length) {
    b.append(el("div", "empty", "ยังไม่ได้เลือกสินค้า ค้นหาแล้วกด \"เลือก\" ที่สินค้าที่ใช่"));
  } else {
    state.groups.forEach((g) => b.append(groupCard(g)));
    const go = el("button", "btn", "คำนวณร้านที่ถูกสุด"); go.type = "button"; go.onclick = compute; b.append(go);
    const clear = el("button", "pill", "ล้างตะกร้า"); clear.type = "button"; clear.style.marginTop = "8px";
    clear.onclick = () => { state.groups = []; state.target = null; save(); renderBasket(); renderResults(); $("plan").replaceChildren(); };
    b.append(clear);
  }
  b.append(el("p", "tip", "1 รายการ = ของที่ต้องการ 1 อย่าง เลือกสินค้าหลายร้านในรายการเดียวได้ แปลว่า \"อันไหนก็ได้\" ระบบจะเลือกร้านที่รวมถูกสุดให้ กดที่ชื่อรายการเพื่อเพิ่มสินค้าเข้ารายการนั้น"));
  $("mbar").hidden = !state.groups.length;
  $("mcount").textContent = `ตะกร้า ${state.groups.length} รายการ`;
}

/* ---- plan ------------------------------------------------------------ */
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
  b.append(ul); box.append(a, b);
  return box;
}

function shopCard(ln) {
  const c = el("div", "panel shopcard");
  const h = el("div", "shophead");
  h.append(el("h3", "", ln.shop), el("span", "tot", `${baht(ln.subtotal + ln.fee)} บาท`));
  c.append(h);
  for (const it of ln.items) {
    const row = el("div", "thumbline");
    const nm = el("div", "nm"); nm.append(link(it.url, it.name), el("small", "", `รายการ: ${it.group}`));
    row.append(thumb(it.image), el("span", "q", `${it.qty} x`), nm, el("span", "pr", `${baht(it.unit)} = ${baht(it.unit * it.qty)}`));
    c.append(row);
  }
  const sh = el("div", "ship");
  const l = el("span"); l.append(el("span", "", `สินค้า ${baht(ln.subtotal)} บาท + ค่าส่ง (${(ln.option || "").replace(/^ส่งแบบ\s*/, "")}) `));
  if (ln.fee === 0) l.append(el("span", "badge free", "ส่งฟรี"));
  sh.append(l, el("b", "", ln.fee === 0 ? "0" : `${baht(ln.fee)} บาท`));
  c.append(sh);
  if (ln.fee > 0 && ln.free_at && ln.subtotal < ln.free_at)
    c.append(el("div", "note", `ซื้อเพิ่มอีก ${baht(ln.free_at - ln.subtotal)} บาท ร้านนี้ส่งฟรี`));
  return c;
}

function priceTable(d) {
  const shops = SHOPS.filter((s) => d.groups.some((g) => g.offers[s]));
  const c = el("div", "panel shopcard");
  c.append(el("h2", "", "ราคาต่อชิ้นที่คุณเลือก แยกตามร้าน"));
  const sc = el("div", "scroll"), t = el("table"), hr = el("tr");
  hr.append(el("th", "", "รายการ")); shops.forEach((s) => hr.append(el("th", "", s)));
  const thead = el("thead"); thead.append(hr); t.append(thead);
  const tb = el("tbody");
  for (const g of d.groups) {
    const tr = el("tr"), min = Math.min(...Object.values(g.offers).map((o) => o.unit));
    tr.append(el("td", "", `${g.name}${g.qty > 1 ? " x" + g.qty : ""}`));
    for (const s of shops) {
      const o = g.offers[s], td = el("td");
      if (!o) { td.className = "none"; td.textContent = "ไม่ได้เลือก"; }
      else { td.className = o.unit === min ? "min" : ""; td.append(link(o.url, baht(o.unit))); }
      tr.append(td);
    }
    tb.append(tr);
  }
  t.append(tb); sc.append(t); c.append(sc);
  return c;
}

async function compute() {
  const box = $("plan");
  if (!state.groups.length) return;
  box.replaceChildren(el("div", "skel"));
  try {
    const r = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groups: state.groups.map((g) => ({ name: g.name, qty: g.qty, offers: g.offers })) }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    box.replaceChildren();
    const head = el("div", "planhead"); head.append(el("h2", "", "ผลการคำนวณ"));
    const close = el("button", "pill", "ปิด"); close.type = "button"; close.onclick = () => box.replaceChildren();
    head.append(close); box.append(head, summary(d));
    d.plan.lines.forEach((ln) => box.append(shopCard(ln)));
    box.append(priceTable(d), el("p", "note", "ราคาจริงตอนจ่ายเงินอาจต่างไปเล็กน้อย ค่าส่งคิดจากวิธีส่งที่ถูกสุดของแต่ละร้าน"));
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    box.replaceChildren(el("div", "error", "คำนวณไม่สำเร็จ (" + e.message + ") ลองใหม่อีกครั้ง"));
  }
}

/* ---- start ----------------------------------------------------------- */
$("sform").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("q").value.trim();
  if (v) doSearch(v);
});
$("mgo").onclick = compute;
EXAMPLES.forEach((t) => {
  const b = el("button", "", t); b.type = "button";
  b.onclick = () => { $("q").value = t; doSearch(t); };
  $("try").append(b);
});
load();
renderBasket();
renderResults();
const first = new URLSearchParams(location.search).get("q");
if (first) { $("q").value = first.slice(0, 120); doSearch(first.slice(0, 120)); }
