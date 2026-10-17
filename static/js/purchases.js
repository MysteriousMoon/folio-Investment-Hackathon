(function(global){
'use strict';
let sequence=0,last=null;
const labels={protective_put:'Protective put',call_spread:'call spread',put_spread:'put spread',covered_call:'covered call',collar:'collar protection',straddle:'Straddle',butterfly:'Butterfly spread',iron_condor:'Iron condor',futures_hedge:'Short futures hedge',futures_long:'long futures'};
const n=v=>v==null?'To be confirmed':new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(v);
async function render(p){
 const el=document.querySelector('#purchase-plan');if(!el)return;
 el.hidden=false;const id=++sequence;
 el.innerHTML='<div class="purchase-head"><h4>My purchase list</h4><span>Synchronizing allocation and market data…</span></div>';
 try{
  const res=await request('/api/purchases');const d=await res.json();
  if(id!==sequence||state.portfolio?.version!==p.version)return;
  if(d.version!==p.version){el.innerHTML='<p class="purchase-summary">The list is updating; refresh shortly.</p>';return}
  last=d;
  el.innerHTML=`<div class="purchase-head"><h4>My purchase list</h4><span>Version ${d.version} · Updates with the conversation</span></div><p class="purchase-summary">${d.amount?'Planned investment '+n(d.amount)+' '+esc(d.currency||' (currency to be confirmed)'):'Set allocation weights first; amounts and quantities are calculated once a budget is provided.'}</p>`+d.items.map(i=>`<div class="purchase-row"><div class="purchase-row-top"><strong>${esc(i.symbol||i.name)}</strong><b>${n(i.weight)}%</b></div><p>${esc(i.reason)}</p><div class="purchase-facts"><span>Target amount <b>${n(i.amount)} ${esc(d.currency||'')}</b></span><span>Reference price ${n(i.price)} ${esc(i.quote_currency||'')}</span><span>Planned purchase <b>${i.quantity==null?'To be calculated':n(i.quantity)+'  shares'}</b></span></div><p>${esc(i.quantity_note)}${i.remainder!=null?' · Remainder '+n(i.remainder)+' '+esc(d.currency||''):''}${i.as_of?' · Quote '+esc(i.as_of.slice(0,10)):''}</p><button class="text-action" data-purchase-adjust="${esc(i.symbol||i.name)}">Adjust this allocation</button></div>`).join('')+(d.strategies.length?`<div class="purchase-overlay"><strong>hedge / Derivatives plan</strong><p>${d.strategies.map(k=>esc(labels[k]||k)).join(' · ')}</p><span>Review exposure, capital requirements, and payoff in strategy analysis; select contracts from the option chain.</span></div>`:'')+`<div class="purchase-actions"><button class="chip" id="purchase-export">Export purchase list CSV</button><button class="chip" id="purchase-discuss">Refine purchase plan</button></div><p class="purchase-summary">Quantities use the latest available quotes; no orders are submitted. Confirm FX amounts for cross-currency trades.</p>`;
  el.querySelectorAll('[data-purchase-adjust]').forEach(b=>b.onclick=()=>draft('I want to adjust the purchase-list allocation for  '+b.dataset.purchaseAdjust+'  allocation, '));
  document.querySelector('#purchase-discuss').onclick=()=>draft('Refine my portfolio and purchase list with securities, weights, entry timing, and hedges.');
  document.querySelector('#purchase-export').onclick=download;
 }catch(e){if(id===sequence)el.innerHTML='<div class="purchase-head"><h4>My purchase list</h4></div><p class="purchase-summary">'+esc(e.message)+'</p><button class="chip" id="purchase-retry">Retry</button>';const b=el.querySelector('#purchase-retry');if(b)b.onclick=()=>render(p)}
}
function draft(t){const el=document.querySelector('#prompt');el.value=t;if(innerWidth<=760)mobile('chat');el.focus()}
function download(){if(!last)return;const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';const rows=[['Underlying','Allocation weight%','Target amount','Capital currency','Reference price','Quote currency','Estimated shares','Quote date','Allocation rationale'],...last.items.map(i=>[i.symbol||i.name,i.weight,i.amount,last.currency,i.price,i.quote_currency,i.quantity,i.as_of,i.reason])];const blob=new Blob(['\uFEFF'+rows.map(r=>r.map(v=>cell(/^[=+@\-]/.test(String(v??''))?'\''+v:v)).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Folio-purchase list.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
global.FolioPurchases={render,reset(){sequence++;last=null;document.querySelector('#purchase-plan').hidden=true}};
})(window);
