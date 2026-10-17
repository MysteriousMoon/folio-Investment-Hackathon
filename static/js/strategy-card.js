(function(global){
'use strict';
let version=null,current=null,completed=null;
const n=(v,d=2)=>v==null?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:d}).format(v);
const names={stock:'stock',call:'Call option',put:'Put option',future:'futures'};
function render(card){
 const el=document.querySelector('#strategy-card');
 if(!card||!card.markdown)return;
 if(state.workspace&&card.version!==state.workspace.version&&current)return;
 version=card.version;current=card;if(card.trade&&!card.streaming)completed=card;el.hidden=false;
 const saveable=!card.streaming&&(card.trade?.legs||[]).length>0;
 el.innerHTML='<div class="strategy-card-head"><span>Recommendation</span><div class="strategy-card-actions"><small></small>'+(saveable?'<button class="save-investment-button" type="button" aria-label="Add to saved investments" title="Add to saved investments">＋</button>':'')+'</div></div><div class="strategy-card-content rich-text"></div><div class="strategy-legs"></div>';
 el.querySelector('small').textContent=card.streaming?'Generating':'';
 FolioRichText.renderInto(el.querySelector('.strategy-card-content'),card.markdown);
 const legs=card.trade?.legs||[];
 if(legs.length)el.querySelector('.strategy-legs').innerHTML='<table><thead><tr><th>Action</th><th>Underlying / Contract</th><th>Suggested allocation</th></tr></thead><tbody>'+legs.map(l=>`<tr><td>${l.side==='buy'?'buy ':'sell '} ${esc(names[l.instrument])}<small>${n(l.quantity)} ${l.instrument==='stock'?' shares':' contracts'} · Reference ${n(l.entry)} ${esc(l.currency)}</small></td><td>${esc(l.symbol)}${l.strike!=null?' · '+n(l.strike):''}<small>${l.expiry?esc(l.expiry):l.continuous?'Continuous-contract scenario':''}</small></td><td>${l.allocation_pct==null?'Pending':n(l.allocation_pct)+'%'}<small>${l.instrument==='future'?'Notional exposure / Capital':l.instrument==='stock'?'Capital':'Premium / Capital'}</small></td></tr>`).join('')+'</tbody></table><details class="method-details"><summary>View contracts and quantity conventions</summary>'+legs.map(l=>`<p>${esc(l.contract)}: ${n(l.quantity)} ${l.instrument==='stock'?' shares':' contracts'}, Multiplier ${n(l.multiplier)}.</p>`).join('')+'<p>Without a budget, quantities represent one illustrative strategy unit; suggested percentages allow later budget scaling.</p></details>';
 renderAnalysis();
 const add=el.querySelector('.save-investment-button');if(add){add.classList.toggle('saved',window.isCurrentInvestmentSaved?.(card));add.textContent=add.classList.contains('saved')?'✓':'＋';add.onclick=()=>window.saveCurrentInvestment?.(add,card)}
}
function renderAnalysis(){
 const target=document.querySelector('#strategy-analysis');if(!target)return;
 const stock=document.querySelector('#stock-forecast');if(stock)stock.hidden=false;
 const source=current?.trade?current:completed;
 if(!source){target.replaceChildren();return}
 const saved=source.trade;
 if(!saved){target.replaceChildren();return}
 const symbol=target.dataset.symbol;
 const derivativeLegs=(saved.legs||[]).filter(l=>l.instrument!=='stock');
 const curves=(saved.curves||[]).filter(c=>Array.isArray(c.points)&&c.points.length>1&&c.points.every(p=>Number.isFinite(p.price)&&Number.isFinite(p.pnl))&&(
  c.combined?derivativeLegs.length&&(!symbol||(saved.legs||[]).some(l=>l.symbol===symbol)):(!symbol||c.symbol===symbol)&&derivativeLegs.some(l=>l.symbol===c.symbol)
 ));
 const trade={...saved,curves};
 if(curves.length){
  if(stock)stock.hidden=true;
  target.hidden=false;
 }else{
  target.replaceChildren();target.hidden=true;
  if(stock){
   stock.hidden=false;
   if(stock.dataset.derivative==='true'&&!current?.streaming)stock.innerHTML='<div class="research-heading"><h4>Strategy payoff curve</h4></div><p class="forecast-empty">'+(trade.warnings?.length?trade.warnings.map(esc).join(' '):'No complete contract plan yet. Its curve will appear here once generated.')+'</p>';
  }
  return;
 }
 target.innerHTML=(trade.curves||[]).map((c,i)=>`<section class="research-block trade-payoff"><div class="research-heading"><h4>${esc(c.symbol)} · ${c.combined?'Synchronized price scenario':c.expiry?'Expiry payoff curve':'Scenario return curve'}</h4><span>${esc(c.currency)}${c.expiry?' · '+esc(c.expiry):''}</span></div><div class="chart-readout" id="payoff-readout-${i}">Move along the curve to inspect prices and payoff</div><div id="payoff-chart-${i}"></div><div class="trade-risk"><div><span>${c.combined?'Synchronized-scenario maximum loss':'Maximum loss'}</span><strong>${c.max_loss==null?'Theoretically unbounded':n(c.max_loss)+' '+esc(c.currency)}</strong></div><div><span>${c.combined?'Synchronized-scenario maximum gain':'Maximum gain'}</span><strong>${c.max_gain==null?'Theoretically unbounded':n(c.max_gain)+' '+esc(c.currency)}</strong></div><div><span>${c.combined?'Break-even return':'Break-even price'}</span><strong>${c.break_even.length?c.break_even.map(v=>n(v)+(c.combined?'%':'')).join(' / '):'none'}</strong></div></div><div class="trade-scenarios">${c.scenario.map(s=>`<div><span>Underlying ${s.change>0?'+':''}${s.change}%</span><b>${s.pnl>0?'+':''}${n(s.pnl)}</b></div>`).join('')}</div><details class="method-details"><summary>Methodology</summary><p>${esc(c.basis)}. The curve uses all quantities above and actual bid/ask quotes. It shows monetary payoff, not probabilities.${c.continuous?'Futures scenarios use continuous prices and contract multipliers; broker requirements determine margin.':''}</p></details></section>`).join('')+(trade.warnings?.length?'<p class="strategy-warning">'+trade.warnings.map(esc).join(' ')+'</p>':'');
 if(trade.risk_notes?.length)target.insertAdjacentHTML('beforeend','<p class="strategy-risk-notes">'+trade.risk_notes.map(esc).join(' ')+'</p>');
 (trade.curves||[]).forEach((c,i)=>draw(c,i));
}
function draw(c,id){
 const points=c.points,el=document.querySelector('#payoff-chart-'+id);if(!el||points.length<2)return;
 const lo=points[0].price,hi=points.at(-1).price,min=Math.min(0,...points.map(p=>p.pnl)),max=Math.max(0,...points.map(p=>p.pnl)),pad=(max-min)*.12||1;
 const x=p=>60+(p-lo)/(hi-lo)*340,y=v=>205-(v-min+pad)/(max-min+2*pad)*180;
 el.innerHTML=`<svg tabindex="0" viewBox="0 0 420 260" role="img" aria-label="${esc(c.symbol)} strategy payoff curve">${[min,0,max].map(v=>`<line x1="60" x2="400" y1="${y(v)}" y2="${y(v)}" stroke="${v===0?'#bdcadc':'#e4eaf3'}" stroke-dasharray="${v===0?'4 3':'0'}"/><text x="3" y="${y(v)+4}">${n(v,0)}</text>`).join('')}<line x1="${x(c.spot)}" x2="${x(c.spot)}" y1="22" y2="205" stroke="#b5c5e1" stroke-dasharray="3 4"/><polyline points="${points.map(p=>x(p.price)+','+y(p.pnl)).join(' ')}" fill="none" stroke="#365acb" stroke-width="2.5"/><circle class="payoff-point" cx="${x(c.spot)}" cy="${y(points.reduce((a,b)=>Math.abs(a.price-c.spot)<Math.abs(b.price-c.spot)?a:b).pnl)}" r="4" fill="#365acb"/><text x="60" y="240">${n(lo)}${c.combined?'%':''}</text><text x="230" y="240" text-anchor="middle">${c.combined?'Synchronized underlying return':'Underlying price'}</text><text x="400" y="240" text-anchor="end">${n(hi)}${c.combined?'%':''}</text></svg>`;
 const svg=el.querySelector('svg');let index=Math.floor(points.length/2);
 function inspect(idx){index=Math.max(0,Math.min(points.length-1,idx));const p=points[index];document.querySelector('#payoff-readout-'+id).textContent=`${c.combined?'Synchronized move':'Underlying'} ${n(p.price)}${c.combined?'%':''} · Strategy payoff ${p.pnl>=0?'+':''}${n(p.pnl)} ${c.currency}`;svg.querySelector('circle').setAttribute('cx',x(p.price));svg.querySelector('circle').setAttribute('cy',y(p.pnl))}
 svg.onpointermove=e=>{const r=svg.getBoundingClientRect(),price=lo+((e.clientX-r.left)/r.width*420-60)/340*(hi-lo);inspect(points.reduce((a,p,i)=>Math.abs(p.price-price)<Math.abs(points[a].price-price)?i:a,0))};
 svg.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();inspect(index+(e.key==='ArrowRight'?1:-1))}};
}
function pending(context){
 if(version===context.version)return;
 const el=document.querySelector('#strategy-card');
 if(current?.markdown){const status=el.querySelector('.strategy-card-head small');if(status)status.textContent='Updating…';return}
 el.hidden=false;el.innerHTML='<div class="strategy-card-head"><span>Recommendation</span><small>Analyzing…</small></div>';
}
function reset(){version=null;current=null;completed=null;document.querySelector('#strategy-card').hidden=true}
global.FolioStrategyCard=Object.freeze({render,pending,reset,renderAnalysis});
})(window);
