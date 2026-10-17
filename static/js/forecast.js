(function(global){
'use strict';
const number=(x,d=2)=>x==null?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:d}).format(x);
const pct=x=>number(x*100,1)+'%';
const colors=['#aa7c82','#365acb','#58a094'];
function valuation(d){
 const f=d.forecast;
 if(!f?.available)return '<div class="forecast-empty">'+esc(f?.reason||'Waiting for financial data.')+'</div>';
 return `<div class="valuation-table"><table><thead><tr><th>Scenario</th><th>EPS</th><th>P/E</th><th>valuation</th><th>Potential return</th></tr></thead><tbody>${f.scenarios.map((s,i)=>`<tr><td><i style="background:${colors[i]}"></i>${s.name}</td><td>${number(s.eps)}</td><td>${number(s.pe,1)}×</td><td>${number(s.price)}</td><td class="${s.return_pct>=0?'up':'down'}">${s.return_pct>0?'+':''}${number(s.return_pct,1)}%</td></tr>`).join('')}</tbody></table></div><p class="forecast-horizon">Future 12 months · ${esc(f.currency)}</p><section class="forecast-assumptions"><h5>Earnings forecast and model assumptions</h5><div class="valuation-table"><table><thead><tr><th>Scenario</th><th>Revenue growth</th><th>Net margin</th><th>Projected net income</th></tr></thead><tbody>${f.scenarios.map(s=>`<tr><td>${s.name}</td><td>${pct(s.growth)}</td><td>${pct(s.margin)}</td><td>${number(s.net_income/1e8)} hundred million</td></tr>`).join('')}</tbody></table></div><p>Growth source: ${esc(f.assumptions.growth_source)}; Observation ${pct(f.assumptions.observed_growth)}, Baseline uses  ${pct(f.assumptions.growth)}.${esc(f.assumptions.share_count)}.</p><p>${esc(f.assumptions.model)}</p><p>Valuation is anchored to the current P/E, not historical peer multiples; scenarios are not probability intervals.</p></section>`;
}
function chart(d){
 if(!d.forecast?.available)return '<div class="forecast-empty">'+esc(d.forecast?.reason||'Waiting for earnings forecast data.')+'</div>';
 return '<div class="forecast-key">'+d.forecast.scenarios.map((s,i)=>`<span><i style="background:${colors[i]}"></i>${s.name}</span>`).join('')+'</div><div id="forecast-readout" class="chart-readout">Future 12-month return scenarios</div><div id="stock-forecast-chart"></div><details class="method-details"><summary>Curve interpretation</summary><p>'+esc(d.forecast.path_method)+' Returns measure price changes, excluding dividends and trading costs.</p></details>';
}
function draw(d){
 const f=d.forecast,el=document.querySelector('#stock-forecast-chart');if(!el||!f?.available)return;
 const values=f.scenarios.flatMap(s=>s.path.map(p=>p.return_pct)),low=Math.min(0,...values),high=Math.max(0,...values),pad=(high-low)*.12||5,min=low-pad,max=high+pad;
 const x=m=>55+m/12*480,y=v=>175-(v-min)/(max-min)*150;
 el.innerHTML=`<svg tabindex="0" viewBox="0 0 600 215" role="img" aria-label="${esc(d.symbol)} twelve-month stock return scenario curves">${[low,0,high].map(v=>`<line x1="55" x2="535" y1="${y(v)}" y2="${y(v)}" stroke="#e0e7f1"/><text x="3" y="${y(v)+4}">${number(v,0)}%</text>`).join('')}${f.scenarios.map((s,i)=>`<polyline fill="none" stroke="${colors[i]}" stroke-width="2.3" points="${s.path.map(p=>x(p.month)+','+y(p.return_pct)).join(' ')}"/>`).join('')}<line class="forecast-cursor" x1="535" x2="535" y1="15" y2="175" stroke="#b5c4dd" stroke-dasharray="3 4"/><text x="55" y="200">Now</text><text x="295" y="200" text-anchor="middle">6 months</text><text x="535" y="200" text-anchor="end">12 months</text></svg>`;
 let month=12;const svg=el.querySelector('svg');function inspect(m){month=Math.max(0,Math.min(12,m));document.querySelector('#forecast-readout').textContent=`Month ${month} · `+f.scenarios.map(s=>s.name+' '+number(s.path[month].return_pct,1)+'%').join(' / ');svg.querySelector('.forecast-cursor').setAttribute('x1',x(month));svg.querySelector('.forecast-cursor').setAttribute('x2',x(month))}
 svg.onpointermove=e=>{const r=svg.getBoundingClientRect();inspect(Math.round(((e.clientX-r.left)/r.width*600-55)/480*12))};svg.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();inspect(month+(e.key==='ArrowRight'?1:-1))}};
}
global.FolioForecast=Object.freeze({valuation,chart,draw});
})(window);
