/* Minimal PN-first mockup logic (UI strings in Italian; comments in English) */
const state = {
  dealers: [
    { name: 'DealerA', base_cost: 6.9, free_threshold: 49 },
    { name: 'DealerB', base_cost: 7.5, free_threshold: 59 },
    { name: 'DealerC', base_cost: 0, free_threshold: 0 },
  ],
  items: new Map(), // maker_pn -> { brand, name, offers: [...] }
  cart: [], // { pn, dealer, price, qty, lock }
};

// Sample data: three PNs with offers across dealers
const sample = [
  {
    pn: 'CN-HG601', brand: 'Shimano', name: 'Catena 11v',
    offers: [
      { dealer: 'DealerA', price: 24.9, stock: true, lead: 1, updated: 'oggi' },
      { dealer: 'DealerB', price: 23.5, stock: false, lead: 3, updated: 'ieri' },
      { dealer: 'DealerC', price: 26.0, stock: true, lead: 2, updated: 'oggi' },
    ]
  },
  {
    pn: 'PG-1230', brand: 'SRAM', name: 'Cassetta 12v',
    offers: [
      { dealer: 'DealerA', price: 89.0, stock: true, lead: 2, updated: 'ieri' },
      { dealer: 'DealerB', price: 88.0, stock: true, lead: 2, updated: 'oggi' },
    ]
  },
  {
    pn: 'CS-HG700', brand: 'Shimano', name: 'Cassetta 11v 11-34',
    offers: [
      { dealer: 'DealerA', price: 66.0, stock: false, lead: 4, updated: 'ieri' },
      { dealer: 'DealerC', price: 64.0, stock: true, lead: 3, updated: 'oggi' },
    ]
  },
];

function byId(id){ return document.getElementById(id); }
function fmtEUR(v){ return new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR'}).format(v||0); }
function normPN(p){ return (p||'').toUpperCase().replace(/[^A-Z0-9]/g,''); }

function initDealers(){
  const sel = byId('dealer-select');
  state.dealers.forEach(d => {
    const o = document.createElement('option'); o.value = d.name; o.textContent = d.name; sel.appendChild(o);
  });
}

function addPN(pn){
  const key = normPN(pn); if(!key) return;
  const rec = sample.find(x => normPN(x.pn)===key);
  if(!rec){
    state.items.set(key,{ pn: pn, brand: '', name: 'Non trovato', offers: []});
  } else {
    state.items.set(key, rec);
  }
  renderResults();
}

function currentFilters(){
  // Read UI filter state (dealer multi, stock-only, budget)
  const inStock = byId('in-stock-only').checked;
  const budget = parseFloat(byId('budget').value||'0');
  const dealers = Array.from(byId('dealer-select').selectedOptions).map(o=>o.value);
  return { inStock, budget: isFinite(budget)?budget:0, dealers };
}

function renderResults(){
  const host = document.querySelector('.results');
  host.innerHTML = '';
  const filters = currentFilters();
  for(const [k, rec] of state.items){
    const block = document.createElement('section'); block.className='pn-block';
    const head = document.createElement('div'); head.className='pn-head';
    const title = document.createElement('div'); title.className='pn-title';
    title.textContent = `${rec.pn||k} · ${rec.brand||''} ${rec.name||''}`.trim(); head.appendChild(title);
    const badge = document.createElement('div'); badge.className='badge'; badge.textContent = rec.offers.length? `${rec.offers.length} offerte` : 'non trovato'; head.appendChild(badge);
    block.appendChild(head);
    const tbl = document.createElement('table'); tbl.className='offer-table';
    tbl.innerHTML = `<thead><tr><th>Dealer</th><th>Prezzo</th><th>Stock</th><th>Lead</th><th>Agg.</th><th>Azioni</th></tr></thead>`;
    const tb = document.createElement('tbody');
    const off = rec.offers
      .filter(o => !filters.inStock || o.stock)
      .filter(o => !filters.dealers.length || filters.dealers.includes(o.dealer))
      .filter(o => !(filters.budget>0) || (o.price<=filters.budget));
    off.sort((a,b)=> (a.stock===b.stock? (a.price-b.price) : (a.stock? -1:1)) || (a.lead-b.lead));
    off.forEach(o => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${o.dealer}</td><td>${fmtEUR(o.price)}</td><td class="${o.stock?'ok':'err'}">${o.stock?'✓':'✗'}</td><td>${o.lead}g</td><td>${o.updated}</td><td><button class="btn-sm" data-add="${rec.pn||k}|${o.dealer}|${o.price}">Aggiungi</button></td>`;
      tb.appendChild(tr);
    });
    tbl.appendChild(tb); block.appendChild(tbl); host.appendChild(block);
  }
  host.querySelectorAll('button[data-add]').forEach(btn => btn.addEventListener('click', onAddCart));
}

function onAddCart(ev){
  const [pn, dealer, price] = ev.currentTarget.dataset.add.split('|');
  const it = state.cart.find(x => x.pn===pn && x.dealer===dealer);
  if(it){ it.qty += 1; } else { state.cart.push({ pn, dealer, price: parseFloat(price), qty: 1, lock: false }); }
  renderCart();
}

function renderCart(){
  const host = byId('cart-rows'); host.innerHTML='';
  state.cart.forEach((c,idx)=>{
    const row = document.createElement('div'); row.className='cart-row';
    row.innerHTML = `<div>${c.pn} · ${c.dealer}</div><div>${fmtEUR(c.price)}</div><div><button class="btn-sm" data-minus="${idx}">−</button> ${c.qty} <button class="btn-sm" data-plus="${idx}">+</button></div><div><label class="lock"><input type="checkbox" data-lock="${idx}" ${c.lock?'checked':''}/> lock</label></div>`;
    host.appendChild(row);
  });
  host.querySelectorAll('button[data-minus]').forEach(b=>b.addEventListener('click',e=>{ const i=+e.currentTarget.dataset.minus; state.cart[i].qty=Math.max(0,state.cart[i].qty-1); if(state.cart[i].qty===0) state.cart.splice(i,1); renderCart(); }));
  host.querySelectorAll('button[data-plus]').forEach(b=>b.addEventListener('click',e=>{ const i=+e.currentTarget.dataset.plus; state.cart[i].qty+=1; renderCart(); }));
  host.querySelectorAll('input[data-lock]').forEach(b=>b.addEventListener('change',e=>{ const i=+e.currentTarget.dataset.lock; state.cart[i].lock=e.currentTarget.checked; }));
  recomputeTotals();
}

function shippingFor(dealer, subtotal){
  const d = state.dealers.find(x=>x.name===dealer) || {base_cost:0,free_threshold:0};
  if(d.free_threshold>0 && subtotal>=d.free_threshold) return 0;
  return d.base_cost||0;
}

function recomputeTotals(){
  // Simple greedy across locked rows; shipping summed per dealer in use
  const subtotal = state.cart.reduce((s,c)=> s + c.price*c.qty, 0);
  const dealersUsed = Array.from(new Set(state.cart.map(c=>c.dealer)));
  const shipping = dealersUsed.reduce((s,name)=> s + shippingFor(name, subtotal), 0);
  const vat = subtotal * 0.22;
  const grand = subtotal + shipping + vat;
  byId('subtotal').textContent = fmtEUR(subtotal);
  byId('shipping').textContent = fmtEUR(shipping);
  byId('vat').textContent = fmtEUR(vat);
  byId('grand').textContent = fmtEUR(grand);
}

function bind(){
  byId('add-btn').addEventListener('click', ()=>{ addPN(byId('pn-input').value); byId('pn-input').value=''; });
  byId('paste-btn').addEventListener('click', ()=> byId('paste-modal').showModal());
  byId('paste-apply').addEventListener('click', ()=>{
    const lines = byId('pn-list').value.split(/\n+/).map(s=>s.trim()).filter(Boolean);
    lines.forEach(addPN); byId('paste-modal').close();
  });
  byId('paste-cancel').addEventListener('click', ()=> byId('paste-modal').close());
  ['in-stock-only','budget','dealer-select'].forEach(id=> byId(id).addEventListener('change', renderResults));
  byId('recalc').addEventListener('click', recomputeTotals);
  // preload sample PN
  ['CN-HG601','PG-1230'].forEach(addPN);
  initDealers();
  renderCart();
}

document.addEventListener('DOMContentLoaded', bind);

