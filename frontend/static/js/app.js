/* EquiTrack single-page UI. Talks only to the REST API; see docs/MEMBER1_INTEGRATION.md for the contract. */
(() => {
  'use strict';

  // ---------- helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const SYMBOLS = { INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥' };
  const nf = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const num = v => (v === null || v === undefined || v === '' || isNaN(Number(v)) ? null : Number(v));
  const money = (n, cur) => (num(n) === null ? '-' : `${SYMBOLS[cur] || (cur ? cur + ' ' : '₹')}${nf.format(n)}`);
  const sign = n => (n > 0 ? 'gain' : n < 0 ? 'loss' : '');
  const signed = (n, cur) => (num(n) === null ? '-' : `${n > 0 ? '+' : n < 0 ? '-' : ''}${money(Math.abs(n), cur)}`);
  const pct = n => (num(n) === null ? '-' : `${n > 0 ? '+' : ''}${Number(n).toFixed(2)}%`);
  const when = ts => (ts ? new Date(ts).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'time unknown');
  const list = (d, ...keys) => (Array.isArray(d) ? d : keys.map(k => d && d[k]).find(Array.isArray) || []);
  const idOf = o => o._id || o.id;

  async function api(path, { method = 'GET', body } = {}) {
    const res = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON body */ }
    if (!res.ok) throw new Error((data && (data.error || data.message)) || `Request failed (${res.status}). Try again.`);
    return data;
  }

  function toast(msg, kind = '') {
    const el = document.createElement('div');
    el.className = `toast-item ${kind}`;
    el.textContent = msg;
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), kind === 'error' ? 7000 : 4500);
  }

  // ---------- state + normalisers ----------
  const state = { prices: {}, seen: new Set(), polled: false };

  function normStock(o) {
    if (!o) return null;
    const s = o.stock || {};
    const out = {
      symbol: o.stock_symbol || o.symbol || s.symbol, name: o.name || s.name || '', exchange: o.exchange || s.exchange || '',
      currency: o.currency || s.currency,
      price: num(o.last_price ?? o.price ?? o.current_price ?? s.last_price ?? s.price),
      prev: num(o.previous_close ?? s.previous_close),
      ts: o.price_timestamp || o.timestamp || o.fetched_at || s.price_timestamp,
      source: o.data_source || o.source || s.data_source || s.source,
      cached: Boolean(o.cached ?? o.is_cached ?? s.cached),
    };
    if (out.symbol && out.price !== null) state.prices[out.symbol] = { ...state.prices[out.symbol], ...out };
    return out;
  }

  const loadWatchlist = async () => list(await api('/api/watchlist'), 'watchlist', 'items').map(i => ({ id: idOf(i), added_at: i.added_at, s: normStock(i) }));
  const loadAlerts = async () => list(await api('/api/alerts'), 'alerts');
  const loadTransactions = async () => list(await api('/api/transactions'), 'transactions');
  async function loadNotifications() {
    const d = await api('/api/notifications');
    return { items: list(d, 'notifications'), unread: d.unread_count ?? list(d, 'notifications').filter(n => !n.is_read).length };
  }
  async function loadPortfolio() {
    const d = await api('/api/portfolio');
    const holdings = list(d, 'holdings').map(h => {
      const stock = normStock({ ...h, symbol: h.stock_symbol });
      const qty = num(h.quantity) ?? 0, cost = num(h.total_cost_basis) ?? 0;
      const value = num(h.current_value) ?? (stock.price !== null ? qty * stock.price : null);
      return { symbol: h.stock_symbol, qty, avg: num(h.average_purchase_price), cost, value, s: stock,
        unrealized: num(h.unrealized_profit_loss) ?? (value !== null ? value - cost : null), realized: num(h.realized_profit_loss) ?? 0 };
    });
    const sm = d.summary || d;
    const invested = num(sm.total_invested ?? sm.total_investment) ?? holdings.reduce((a, h) => a + h.cost, 0);
    const value = num(sm.current_value ?? sm.portfolio_value) ?? holdings.reduce((a, h) => a + (h.value ?? h.cost), 0);
    const unrealized = num(sm.unrealized_profit_loss) ?? value - invested;
    return { holdings, invested, value, unrealized, realized: num(sm.realized_profit_loss) ?? holdings.reduce((a, h) => a + h.realized, 0),
      ret: num(sm.return_percentage) ?? (invested ? (unrealized / invested) * 100 : 0) };
  }

  // ---------- shared fragments ----------
  const priceCell = s => (s && s.price !== null
    ? `${money(s.price, s.currency)}<span class="sub">${esc(s.source || 'Unknown source')}, ${esc(when(s.ts))}${s.cached ? '<span class="tag cached">cached</span>' : ''}</span>`
    : '<span class="muted">No price yet</span>');
  const change = s => (s && s.price !== null && s.prev ? `<span class="${sign(s.price - s.prev)}">${pct(((s.price - s.prev) / s.prev) * 100)}</span>` : '<span class="muted">-</span>');
  const empty = (msg) => `<div class="empty">${msg}</div>`;
  const errBox = e => `<div class="error-box">${esc(e.message || e)}</div>`;
  const settled = (r, fn) => (r.status === 'fulfilled' ? fn(r.value) : errBox(r.reason));
  const head = (title, sub, actions = '') => `<div class="page-head"><div><h1>${esc(title)}</h1><p class="muted mb-0">${esc(sub)}</p></div><div>${actions}</div></div>`;
  const symbolList = () => `<datalist id="symbols">${Object.keys(state.prices).map(s => `<option value="${esc(s)}">`).join('')}</datalist>`;
  const refreshBtn = sym => `<button class="btn btn-ghost btn-sm" data-action="refresh" data-symbol="${esc(sym)}">Refresh price</button>`;

  // Distance-to-trigger track for one alert.
  function track(a) {
    if (a.is_triggered) return `<div class="track" aria-hidden="true"><div class="track-fill done" style="width:100%"></div></div><div class="track-label">Triggered ${esc(when(a.triggered_at))}</div>`;
    const p = state.prices[a.stock_symbol];
    if (!p || p.price === null) return '<div class="track-label">No price yet. Refresh to see how close it is.</div>';
    const gap = ((a.target_price - p.price) / p.price) * 100;
    const needed = a.condition === 'ABOVE' ? gap : -gap;
    const fill = needed <= 0 ? 1 : Math.min(1, Math.max(0.03, 1 - needed / 20));
    const label = needed <= 0 ? 'Condition already met. It triggers on the next refresh.'
      : `Needs a ${a.condition === 'ABOVE' ? 'rise' : 'drop'} of ${needed.toFixed(2)}% from ${money(p.price, p.currency)}`;
    return `<div class="track" aria-hidden="true"><div class="track-fill" style="width:${Math.round(fill * 100)}%"></div></div><div class="track-label">${esc(label)}</div>`;
  }
  const rule = a => `${a.condition === 'ABOVE' ? 'At or above' : 'At or below'} ${money(a.target_price, (state.prices[a.stock_symbol] || {}).currency)}`;

  function tradeForm({ symbol = '', price = '', side = null }) {
    return `<form class="inline-form" data-form="trade">
      ${side ? `<input type="hidden" name="side" value="${side}">` : `<div class="field"><label for="t-side">Action</label><select class="form-select" id="t-side" name="side"><option value="buy">Buy</option><option value="sell">Sell</option></select></div>`}
      <div class="field"><label for="t-sym${symbol}">Stock</label><input class="form-control" id="t-sym${symbol}" name="stock_symbol" list="symbols" value="${esc(symbol)}" placeholder="AAPL" required data-fill-price></div>
      <div class="field"><label for="t-qty${symbol}">Shares</label><input class="form-control" id="t-qty${symbol}" name="quantity" type="number" min="1" step="1" required></div>
      <div class="field"><label for="t-price${symbol}">Price per share</label><input class="form-control" id="t-price${symbol}" name="price" type="number" min="0.01" step="0.01" value="${esc(price)}" required></div>
      <button class="btn btn-primary" type="submit">${side === 'buy' ? 'Record purchase' : side === 'sell' ? 'Record sale' : 'Record transaction'}</button></form>`;
  }

  function alertForm(symbol = '') {
    return `<form class="inline-form" data-form="alert-create">
      <div class="field"><label for="a-sym${symbol}">Stock</label><input class="form-control" id="a-sym${symbol}" name="stock_symbol" list="symbols" value="${esc(symbol)}" placeholder="AAPL" required></div>
      <div class="field"><label for="a-cond${symbol}">Notify me when the price is</label><select class="form-select" id="a-cond${symbol}" name="condition"><option value="ABOVE">at or above</option><option value="BELOW">at or below</option></select></div>
      <div class="field"><label for="a-target${symbol}">Target price</label><input class="form-control" id="a-target${symbol}" name="target_price" type="number" min="0.01" step="0.01" required></div>
      <button class="btn btn-primary" type="submit">Create alert</button></form>`;
  }

  const notifItem = n => `<div class="notif ${n.is_read ? '' : 'unread'}"><div><div class="msg">${esc(n.message)}</div>
    <div class="muted">${esc(when(n.timestamp))}</div></div>${n.is_read ? '' : `<button class="btn btn-ghost btn-sm" data-action="notif-read" data-id="${esc(idOf(n))}">Mark as read</button>`}</div>`;

  // ---------- views ----------
  const views = {
    async dashboard() {
      const [pf, wl, al, nt] = await Promise.allSettled([loadPortfolio(), loadWatchlist(), loadAlerts(), loadNotifications()]);
      const active = al.status === 'fulfilled' ? al.value.filter(a => !a.is_triggered) : [];
      const hero = settled(pf, p => `<section class="panel hero" aria-label="Portfolio summary"><div class="hero-main"><div class="label">Portfolio value</div>
        <div class="value">${money(p.value)}</div><div class="${sign(p.unrealized)}">${signed(p.unrealized)} (${pct(p.ret)})</div></div>
        <div class="hero-stats"><div class="stat"><div class="label">Total invested</div><div class="value">${money(p.invested)}</div></div>
        <div class="stat"><div class="label">Unrealized profit/loss</div><div class="value ${sign(p.unrealized)}">${signed(p.unrealized)}</div></div>
        <div class="stat"><div class="label">Realized profit/loss</div><div class="value ${sign(p.realized)}">${signed(p.realized)}</div></div>
        <div class="stat"><div class="label">Active alerts</div><div class="value">${active.length}</div></div></div></section>`);
      const wlHtml = settled(wl, items => (items.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Stock</th><th>Price</th><th class="num">Change</th></tr></thead><tbody>
        ${items.map(i => `<tr><td class="sym">${esc(i.s.symbol)}<span class="sub">${esc(i.s.name)}</span></td><td>${priceCell(i.s)}</td><td class="num">${change(i.s)}</td></tr>`).join('')}</tbody></table></div>`
        : empty('Your watchlist is empty. <a href="#/stocks">Find a stock</a> to start watching it.')));
      const alHtml = settled(al, () => (active.length ? active.map(a => `<div class="alert-card"><header><span><strong>${esc(a.stock_symbol)}</strong> ${esc(rule(a))}</span>${refreshBtn(a.stock_symbol)}</header>${track(a)}</div>`).join('')
        : empty('No active alerts. <a href="#/alerts">Create one</a> to hear when a price moves.')));
      const ntHtml = settled(nt, n => (n.items.length ? n.items.slice(0, 5).map(notifItem).join('') : empty('No notifications yet. They appear here when an alert triggers.')));
      return `${head('Dashboard', 'Your virtual portfolio, watchlist and alerts at a glance.')}${hero}
        <div class="grid-2 mb-4"><section class="panel"><h2>Watchlist</h2>${wlHtml}</section><section class="panel"><h2>Alerts close to triggering</h2>${alHtml}</section></div>
        <section class="panel"><h2>Recent notifications</h2>${ntHtml}</section>`;
    },

    async stocks() {
      return `${head('Find stocks', 'Search by ticker symbol or company name.')}
        <section class="panel"><form class="inline-form" data-form="search"><div class="field"><label for="q">Ticker or company</label>
        <input class="form-control" id="q" name="q" placeholder="AAPL" required autocomplete="off"></div><button class="btn btn-primary" type="submit">Search</button></form></section>
        <div id="results"></div><div id="detail"></div>`;
    },

    async watchlist() {
      const items = await loadWatchlist();
      const syms = items.map(i => i.s.symbol).join(',');
      return `${head('Watchlist', 'Stocks you are keeping an eye on.', items.length ? `<button class="btn btn-ghost" data-action="refresh-all" data-symbols="${esc(syms)}">Refresh all prices</button>` : '')}
        <section class="panel"><form class="inline-form" data-form="watch-add"><div class="field"><label for="w-sym">Add a stock</label>
        <input class="form-control" id="w-sym" name="stock_symbol" list="symbols" placeholder="AAPL" required></div><button class="btn btn-primary" type="submit">Add to watchlist</button></form>${symbolList()}</section>
        <section class="panel">${items.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Stock</th><th>Latest price</th><th class="num">Change</th><th></th></tr></thead><tbody>
        ${items.map(i => `<tr><td class="sym">${esc(i.s.symbol)}<span class="sub">${esc(i.s.name)} ${esc(i.s.exchange)}</span></td><td>${priceCell(i.s)}</td><td class="num">${change(i.s)}</td>
        <td><div class="row-actions">${refreshBtn(i.s.symbol)}<a class="btn btn-ghost btn-sm" href="#/alerts?symbol=${encodeURIComponent(i.s.symbol)}">Set alert</a>
        <button class="btn btn-danger-ghost btn-sm" data-action="remove-watch" data-id="${esc(i.id)}">Remove</button></div></td></tr>`).join('')}</tbody></table></div>`
        : empty('Nothing on your watchlist yet. Add a ticker above, or use <a href="#/stocks">Find stocks</a>.')}</section>`;
    },

    async portfolio() {
      const p = await loadPortfolio();
      const stat = (l, v, c = '') => `<div class="stat"><div class="label">${l}</div><div class="value ${c}">${v}</div></div>`;
      return `${head('Portfolio', 'Virtual holdings valued at the latest prices you have refreshed.')}
        <section class="panel hero"><div class="hero-main"><div class="label">Current value</div><div class="value">${money(p.value)}</div><div class="${sign(p.unrealized)}">${pct(p.ret)} return</div></div>
        <div class="hero-stats">${stat('Total invested', money(p.invested))}${stat('Unrealized profit/loss', signed(p.unrealized), sign(p.unrealized))}${stat('Realized profit/loss', signed(p.realized), sign(p.realized))}</div></section>
        <section class="panel"><h2>Record a transaction</h2>${tradeForm({})}${symbolList()}</section>
        <section class="panel"><h2>Holdings</h2>${p.holdings.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Stock</th><th class="num">Shares</th><th class="num">Average cost</th><th>Latest price</th><th class="num">Value</th><th class="num">Unrealized</th><th class="num">Realized</th><th></th></tr></thead><tbody>
        ${p.holdings.map(h => `<tr><td class="sym">${esc(h.symbol)}</td><td class="num">${h.qty}</td><td class="num">${money(h.avg, h.s.currency)}</td><td>${priceCell(h.s)}</td>
        <td class="num">${money(h.value, h.s.currency)}</td><td class="num ${sign(h.unrealized)}">${signed(h.unrealized, h.s.currency)}</td><td class="num ${sign(h.realized)}">${signed(h.realized, h.s.currency)}</td><td>${refreshBtn(h.symbol)}</td></tr>`).join('')}</tbody></table></div>`
        : empty('You hold no shares yet. Record a purchase above to build your virtual portfolio.')}</section>`;
    },

    async transactions() {
      const t = await loadTransactions();
      return `${head('Transactions', 'Every virtual purchase and sale, newest first.')}<section class="panel">${t.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Type</th><th>Stock</th><th class="num">Shares</th><th class="num">Price</th><th class="num">Total</th></tr></thead><tbody>
        ${t.map(x => `<tr><td>${esc(when(x.timestamp))}</td><td>${x.transaction_type === 'SELL' ? 'Sale' : 'Purchase'}</td><td class="sym">${esc(x.stock_symbol)}</td><td class="num">${esc(x.quantity)}</td>
        <td class="num">${money(x.price, (state.prices[x.stock_symbol] || {}).currency)}</td><td class="num">${money(x.total_amount ?? x.quantity * x.price, (state.prices[x.stock_symbol] || {}).currency)}</td></tr>`).join('')}</tbody></table></div>`
        : empty('No transactions yet. Record a purchase from <a href="#/portfolio">Portfolio</a>.')}</section>`;
    },

    async alerts() {
      const [alerts] = await Promise.all([loadAlerts(), loadWatchlist().catch(() => []), loadPortfolio().catch(() => null)]);
      const preset = new URLSearchParams(location.hash.split('?')[1] || '').get('symbol') || '';
      return `${head('Alerts', 'Get notified once when a price crosses your target. Each alert triggers a single time until you reset it.')}
        <section class="panel"><h2>New alert</h2>${alertForm(preset)}${symbolList()}</section>
        <section class="panel">${alerts.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Stock</th><th>Rule</th><th>Distance to trigger</th><th>Status</th><th></th></tr></thead><tbody>
        ${alerts.map(a => `<tr><td class="sym">${esc(a.stock_symbol)}</td><td>${esc(rule(a))}</td><td style="min-width:220px">${track(a)}</td>
        <td><span class="tag ${a.is_triggered ? 'triggered' : 'active'}">${a.is_triggered ? 'Triggered' : 'Active'}</span></td>
        <td><div class="row-actions">${refreshBtn(a.stock_symbol)}${a.is_triggered ? `<button class="btn btn-ghost btn-sm" data-action="alert-reset" data-id="${esc(idOf(a))}">Reset</button>` : ''}
        <button class="btn btn-ghost btn-sm" data-action="alert-edit" data-id="${esc(idOf(a))}" data-symbol="${esc(a.stock_symbol)}" data-condition="${esc(a.condition)}" data-target="${esc(a.target_price)}">Edit</button>
        <button class="btn btn-danger-ghost btn-sm" data-action="alert-delete" data-id="${esc(idOf(a))}">Delete</button></div></td></tr>`).join('')}</tbody></table></div>`
        : empty('No alerts yet. Create one above to be told when a price reaches your target.')}</section>`;
    },

    async notifications() {
      const n = await loadNotifications();
      return `${head('Notifications', 'Messages created when your alerts trigger.', n.unread ? '<button class="btn btn-ghost" data-action="notif-read-all">Mark all as read</button>' : '')}
        ${n.items.length ? n.items.map(notifItem).join('') : empty('No notifications yet. They appear here when an alert triggers.')}`;
    },
  };

  // ---------- routing ----------
  const current = () => (location.hash.replace(/^#\/?/, '') || 'dashboard').split('?')[0];
  async function render(quiet = false) {
    const name = views[current()] ? current() : 'dashboard';
    document.querySelectorAll('[data-nav]').forEach(a => a.classList.toggle('active', a.dataset.nav === name));
    const view = $('#view');
    if (!quiet) view.innerHTML = '<p class="muted">Loading…</p>';
    try { view.innerHTML = await views[name](); } catch (e) { view.innerHTML = head(name[0].toUpperCase() + name.slice(1), '') + errBox(e); }
    if (!quiet) { window.scrollTo(0, 0); }
  }
  const afterChange = () => { if (current() !== 'stocks') render(true); };

  // ---------- actions ----------
  async function showDetail(symbol) {
    const box = $('#detail');
    box.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const s = normStock(await api(`/api/stocks/${encodeURIComponent(symbol)}`));
      box.innerHTML = `<section class="panel"><h2>${esc(s.symbol)} ${esc(s.name)}</h2><p class="muted">${esc(s.exchange)} ${esc(s.currency || '')}</p>
        <p class="fs-4 fw-bold mb-1">${priceCell(s)}</p><div class="row-actions justify-content-start my-3">${refreshBtn(s.symbol)}
        <button class="btn btn-ghost btn-sm" data-action="watch-add" data-symbol="${esc(s.symbol)}">Add to watchlist</button></div>
        <h2 class="mt-3">Buy shares (virtual)</h2>${tradeForm({ symbol: s.symbol, price: s.price ?? '', side: 'buy' })}
        <h2 class="mt-4">Set a price alert</h2>${alertForm(s.symbol)}${symbolList()}</section>`;
    } catch (e) { box.innerHTML = errBox(e); }
  }

  function handleTriggered(data) {
    list(data && data.triggered_alerts).forEach(n => { state.seen.add(idOf(n)); toast(n.message, 'alert'); });
    if (data && data.warning) toast(data.warning, 'warn');
  }

  const actions = {
    async detail(b) { await showDetail(b.dataset.symbol); },
    async refresh(b) {
      const data = await api(`/api/stocks/${encodeURIComponent(b.dataset.symbol)}/refresh`, { method: 'POST' });
      normStock(data); handleTriggered(data);
      toast(`${b.dataset.symbol} price updated.`);
      current() === 'stocks' ? await showDetail(b.dataset.symbol) : render(true);
      pollNotifications();
    },
    async 'refresh-all'(b) {
      let n = 0;
      for (const sym of b.dataset.symbols.split(',').filter(Boolean)) {
        const data = await api(`/api/stocks/${encodeURIComponent(sym)}/refresh`, { method: 'POST' });
        normStock(data); handleTriggered(data); n++;
      }
      toast(`Updated ${n} price${n === 1 ? '' : 's'}.`);
      render(true); pollNotifications();
    },
    async 'watch-add'(b) { await api('/api/watchlist', { method: 'POST', body: { stock_symbol: b.dataset.symbol } }); toast(`${b.dataset.symbol} added to your watchlist.`); afterChange(); },
    async 'remove-watch'(b) { if (confirm('Remove this stock from your watchlist?')) { await api(`/api/watchlist/${encodeURIComponent(b.dataset.id)}`, { method: 'DELETE' }); toast('Removed from your watchlist.'); afterChange(); } },
    async 'alert-delete'(b) { if (confirm('Delete this alert?')) { await api(`/api/alerts/${encodeURIComponent(b.dataset.id)}`, { method: 'DELETE' }); toast('Alert deleted.'); afterChange(); } },
    async 'alert-reset'(b) { await api(`/api/alerts/${encodeURIComponent(b.dataset.id)}/reset`, { method: 'POST' }); toast('Alert reset. It can trigger again.'); afterChange(); },
    async 'alert-edit'(b) {
      const f = $('#edit-alert-modal form');
      f.id.value = b.dataset.id; f.condition.value = b.dataset.condition; f.target_price.value = b.dataset.target;
      $('#edit-alert-symbol').textContent = b.dataset.symbol;
      bootstrap.Modal.getOrCreateInstance($('#edit-alert-modal')).show();
    },
    async 'notif-read'(b) { await api(`/api/notifications/${encodeURIComponent(b.dataset.id)}/read`, { method: 'POST' }); afterChange(); pollNotifications(); },
    async 'notif-read-all'() { await api('/api/notifications/read-all', { method: 'POST' }); afterChange(); pollNotifications(); },
  };

  const forms = {
    async search(f) {
      const q = new FormData(f).get('q').trim();
      const results = list(await api(`/api/stocks?q=${encodeURIComponent(q)}`), 'results', 'stocks');
      $('#detail').innerHTML = '';
      $('#results').innerHTML = `<section class="panel"><h2>Results for ${esc(q)}</h2>${results.length ? `<div class="table-wrap"><table class="table"><tbody>
        ${results.map(r => `<tr><td class="sym">${esc(r.symbol)}<span class="sub">${esc(r.name)}</span></td><td>${esc(r.exchange || '')} ${esc(r.currency || '')}</td>
        <td class="num"><button class="btn btn-primary btn-sm" data-action="detail" data-symbol="${esc(r.symbol)}">View details</button></td></tr>`).join('')}</tbody></table></div>`
        : empty(`No stocks matched "${esc(q)}". Check the ticker symbol and try again.`)}</section>`;
    },
    async 'watch-add'(f) { const d = Object.fromEntries(new FormData(f)); await api('/api/watchlist', { method: 'POST', body: { stock_symbol: d.stock_symbol.trim().toUpperCase() } }); toast(`${d.stock_symbol.toUpperCase()} added to your watchlist.`); afterChange(); },
    async trade(f) {
      const d = Object.fromEntries(new FormData(f));
      const sym = d.stock_symbol.trim().toUpperCase();
      await api(`/api/portfolio/${d.side}`, { method: 'POST', body: { stock_symbol: sym, quantity: parseInt(d.quantity, 10), price: parseFloat(d.price) } });
      toast(d.side === 'buy' ? `Recorded purchase of ${d.quantity} ${sym}.` : `Recorded sale of ${d.quantity} ${sym}.`);
      f.reset(); afterChange();
    },
    async 'alert-create'(f) {
      const d = Object.fromEntries(new FormData(f));
      await api('/api/alerts', { method: 'POST', body: { stock_symbol: d.stock_symbol.trim().toUpperCase(), condition: d.condition, target_price: parseFloat(d.target_price) } });
      toast('Alert created. It triggers once when the price crosses your target.'); f.reset(); afterChange();
    },
    async 'alert-edit'(f) {
      const d = Object.fromEntries(new FormData(f));
      await api(`/api/alerts/${encodeURIComponent(d.id)}`, { method: 'PUT', body: { condition: d.condition, target_price: parseFloat(d.target_price) } });
      bootstrap.Modal.getOrCreateInstance($('#edit-alert-modal')).hide(); toast('Alert saved and re-armed.'); afterChange();
    },
  };

  async function guarded(btnOrForm, fn) {
    const submit = btnOrForm.matches('form') ? btnOrForm.querySelector('[type=submit]') : btnOrForm;
    if (submit) submit.disabled = true;
    try { await fn(); } catch (e) { toast(e.message, 'error'); } finally { if (submit) submit.disabled = false; }
  }
  document.addEventListener('click', e => { const b = e.target.closest('[data-action]'); if (b && actions[b.dataset.action]) guarded(b, () => actions[b.dataset.action](b)); });
  document.addEventListener('submit', e => { const f = e.target.closest('form[data-form]'); if (f && forms[f.dataset.form]) { e.preventDefault(); guarded(f, () => forms[f.dataset.form](f)); } });
  // Pre-fill the price field from the latest known price when a symbol is chosen.
  document.addEventListener('change', e => {
    if (!e.target.matches('[data-fill-price]')) return;
    const p = state.prices[e.target.value.trim().toUpperCase()];
    const price = e.target.form && e.target.form.elements.price;
    if (p && price && !price.value) price.value = p.price;
  });

  // ---------- notifications polling ----------
  async function pollNotifications() {
    try {
      const { items, unread } = await loadNotifications();
      const badge = $('#unread-badge');
      badge.textContent = unread; badge.hidden = !unread;
      const fresh = items.filter(n => !n.is_read && !state.seen.has(idOf(n)));
      if (state.polled && fresh.length) {
        fresh.forEach(n => toast(n.message, 'alert'));
        if (['dashboard', 'alerts', 'notifications'].includes(current())) render(true);
      }
      items.forEach(n => state.seen.add(idOf(n)));
      state.polled = true;
    } catch (_) { /* backend may be restarting; try again next tick */ }
  }

  window.addEventListener('hashchange', () => render());
  render().then(pollNotifications);
  setInterval(pollNotifications, 20000);
})();
