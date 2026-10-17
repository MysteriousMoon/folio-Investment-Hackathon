(function(global){
'use strict';
const colors=['#365acb','#8ba8d8','#70aaa7','#c9a76a'];
const n=(v,d=2)=>v==null?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:d}).format(v);
let data=[],scenario=1;
const legend=ds=>'<div class="forecast-key">'+ds.map((d,i)=>`<span><i style="background:${colors[i]}"></i>${esc(d.symbol)}</span>`).join('')+'</div>';
function table(head,rows){return '<div class="valuation-table comparison-matrix"><table><thead><tr>'+head.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'}
function risk(ds){
 const rows=[['Annual volatility','annual_vol'],['Historical maximum drawdown','historical_max_drawdown'],['3-month VaR95','var95'],['3-month CVaR95','cvar95']];
 const first=ds.find(d=>d.comparison_risk)?.comparison_risk;
 return '<div class="research-heading"><h4>Security risk comparison</h4></div>'+legend(ds)+table(['Metric',...ds.map(d=>esc(d.symbol))],rows.map(([label,key])=>[label,...ds.map(d=>d.comparison_risk?n(d.comparison_risk[key])+'%':'—')]))+'<div id="comparison-distribution"></div>'+(first?`<details class="method-details"><summary>Shared sample and methodology</summary><p>${esc(first.start)}  to  ${esc(first.end)}, ${first.samples} common trading days. VaR/CVaR over  3 months with zero log drift; distributions share the same bins.</p></details>`:'<p class="forecast-empty">Insufficient common trading dates to compare risk.</p>');
}
function forecast(ds){
 return '<div class="research-heading"><h4>Forecast return comparison</h4></div>'+legend(ds)+'<div class="comparison-scenarios">'+['conservative','base','optimistic'].map((s,i)=>`<button data-compare-scenario="${i}" aria-pressed="${i===scenario}">${s}</button>`).join('')+'</div><p id="comparison-forecast-readout" class="chart-readout">Future 12 months · Returns shown as percentages</p><div id="comparison-forecast-chart"></div><p class="forecast-horizon">Compare the same scenario; no probabilities are assigned.</p>';
}
function valuation(ds){
 let html='<div class="research-heading"><h4>Future valuation comparison</h4></div>'+table(['Underlying / Scenario','EPS','PE','valuation','Potential return'],ds.flatMap(d=>d.forecast?.available?d.forecast.scenarios.map((s,i)=>[esc(d.symbol)+'<small>'+s.name+' · '+esc(d.currency)+'</small>',n(s.eps),n(s.pe,1)+'×',n(s.price),(s.return_pct>0?'+':'')+n(s.return_pct,1)+'%']):[[esc(d.symbol),'—','—','—','—']]));
 html+='<section class="forecast-assumptions"><h5>Earnings forecast and model assumptions</h5>'+table(['Underlying','Base revenue growth','Net margin','Base P/E'],ds.map(d=>{const a=d.forecast?.assumptions;return [esc(d.symbol),a?n(a.growth*100,1)+'%':'—',a?n(a.margin*100,1)+'%':'—',a?n(a.pe,1)+'×':'—']}))+'<p>Each company uses the same revenue, margin, EPS and PE model, holding diluted shares constant. Conservative/optimistic cases adjust growth, margins, and valuation multiples; paths interpolate scenario valuations geometrically.</p>'+ds.filter(d=>!d.forecast?.available).map(d=>'<p>'+esc(d.symbol)+': '+esc(d.forecast?.reason||'Insufficient financial data')+'</p>').join('')+'</section>';
 return html;
}
function drawDistribution(ds){
 const el=document.querySelector('#comparison-distribution'),good=ds.filter(d=>d.comparison_risk?.histogram);if(!el||!good.length)return;
 const h=good[0].comparison_risk.histogram,max=Math.max(1,...good.flatMap(d=>d.comparison_risk.histogram.map(b=>b.probability)));
 el.innerHTML=`<svg viewBox="0 0 420 190" role="img" aria-label="${esc(ds.map(d=>d.symbol).join(' and '))} risk distributions with shared bins">${good.map(d=>`<polyline fill="none" stroke="${colors[ds.indexOf(d)]}" stroke-width="2" points="${d.comparison_risk.histogram.map((b,i)=>`${45+(i+.5)/h.length*345},${150-b.probability/max*125}`).join(' ')}"/>`).join('')}<text x="45" y="175">${n(h[0].low,0)}%</text><text x="390" y="175" text-anchor="end">${n(h.at(-1).high,0)}%</text></svg>`;
}
function drawForecast(){
 const el=document.querySelector('#comparison-forecast-chart');if(!el)return;
 const series=data.filter(d=>d.forecast?.available).map(d=>({d,path:d.forecast.scenarios[scenario].path}));
 if(!series.length){el.innerHTML='<p class="forecast-empty">No comparable forecast data available.</p>';return}
 const values=series.flatMap(s=>s.path.map(p=>p.return_pct)),low=Math.min(0,...values),high=Math.max(0,...values),pad=(high-low)*.15||1,min=low-pad,max=high+pad;
 const x=t=>50+t/12*335,y=v=>185-(v-min)/(max-min)*155;
 el.innerHTML=`<svg tabindex="0" viewBox="0 0 420 230" role="img" aria-label="${esc(series.map(s=>s.d.symbol).join(' and '))} forecast return comparison">${[low,0,high].map(v=>`<line x1="50" x2="385" y1="${y(v)}" y2="${y(v)}" stroke="#e3eaf3"/><text x="2" y="${y(v)+4}">${n(v,0)}%</text>`).join('')}${series.map(s=>`<polyline fill="none" stroke="${colors[data.indexOf(s.d)]}" stroke-width="2.3" points="${s.path.map(p=>x(p.month)+','+y(p.return_pct)).join(' ')}"/>`).join('')}<text x="50" y="214">Now</text><text x="385" y="214" text-anchor="end">12 months</text></svg>`;
 let month=12;const svg=el.querySelector('svg');function inspect(m){month=Math.max(0,Math.min(12,m));document.querySelector('#comparison-forecast-readout').textContent='Month '+month+' · '+series.map(s=>s.d.symbol+' '+n(s.path[month].return_pct,1)+'%').join(' / ')}
 svg.onpointermove=e=>{const r=svg.getBoundingClientRect();inspect(Math.round(((e.clientX-r.left)/r.width*420-50)/335*12))};svg.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();inspect(month+(e.key==='ArrowRight'?1:-1))}};
}
function draw(ds){data=ds;drawDistribution(ds);drawForecast();document.querySelectorAll('[data-compare-scenario]').forEach(b=>b.onclick=()=>{scenario=+b.dataset.compareScenario;document.querySelectorAll('[data-compare-scenario]').forEach(x=>x.setAttribute('aria-pressed',String(+x.dataset.compareScenario===scenario)));drawForecast()})}
global.FolioComparison=Object.freeze({risk,forecast,valuation,draw});
})(window);
