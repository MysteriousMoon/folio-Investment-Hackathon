/* Conversation-driven research canvas. Only typed components, never model HTML. */
(function(global){
'use strict';
const $=s=>document.querySelector(s),palette=['#365acb','#8ba8d8','#70aaa7','#c9a76a'];
let context=null,following=true,sequence=0,securities=[],period='3m',focusSymbol='',loadedKey='';
const cache=new Map();
const labels={security:'Security research',comparison:'Security comparison',options:'Options research',hedge:'Risk hedge',allocation:'asset allocation',risk:'Risk analysis',macro:'Macro observations',execution:'execution plan',research:'Thesis research'};
const numeric=(x,d=2)=>x==null||!Number.isFinite(Number(x))?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:d}).format(Number(x));
function large(x){if(x==null)return '—';const a=Math.abs(x);return a>=1e12?numeric(x/1e12)+' trillion':a>=1e8?numeric(x/1e8)+' hundred million':a>=1e4?numeric(x/1e4)+' ten thousand':numeric(x)}
const pct=x=>x==null?'—':numeric(x*100)+'%';
const key=c=>(c?.symbols||[]).join(',');
const securityKind=c=>!!c?.symbols?.length&&c.kind!=='macro';
function block(title,body,extra=''){return `<section class="research-block ${extra}"><div class="research-heading"><h4>${title}</h4></div>${body}</section>`}
function metricCards(entries){return '<div class="research-metrics">'+entries.map(([label,value,note])=>`<div><span>${label}</span><strong>${value}</strong>${note?`<small>${note}</small>`:''}</div>`).join('')+'</div>'}
function moduleOrder(){
 const q=context.query||'';
 if(context.kind==='comparison')return ['comparison','price','risk','payoff'];
 if(['options','hedge'].includes(context.kind))return ['price','risk','payoff','options'];
 if(context.kind==='futures')return ['price','risk','payoff'];
 const extra=/financials|Revenue|Profit|Revenue|Earnings/.test(q)?['financials']:/valuation|P\/E|PE|cheap|is it expensive/i.test(q)?['valuation']:[];
 return ['price','risk',...extra,'payoff'];
}
function activate(){
 const p=$('#portfolio');if(!context)return;
 $('#showcase').hidden=true;p.hidden=false;$('#save').hidden=!state.portfolio;
 $('#conversation-toolbar').hidden=true;$('#conversation-focus').textContent=`This turn · ${labels[context.kind]||'Investment research'}`;
 $('#conversation-tools').textContent=following?'view account portfolio':'Back to current research';
 p.dataset.following=String(following);
 const canvasMode=true;
 p.dataset.adaptive=String(canvasMode);$('#conversation-canvas').hidden=!canvasMode;
 if(!following)return;
 $('#portfolio-name').textContent=context.title;
 $('.draft').textContent=securityKind(context)?'Security research':'Follow conversation';
 $('#portfolio-thesis').textContent=context.summary||({security:'Prices, valuation, and financials follow the current security.',comparison:'Compare the current securities using consistent conventions.',options:context.symbols.length?'Explore actual expiries, strikes, and quotes from the current option chain.':'Choose options around account exposure and compare protection costs and expiry payoffs.',hedge:'Compare protection structures and available contracts for the current underlying.',risk:'Review historical volatility and modeled returns for the current security.',research:'Break the thesis into verifiable questions before selecting investment tools.',macro:'Connect macro questions with dated official observations.'}[context.kind]||'Analysis follows the current question.');
 if(canvasMode){$('#portfolio-caption').textContent=context.symbols?.length?context.symbols.join(' / '):'Research background';$('.portfolio-budget>span').textContent=securityKind(context)?'Current discussion':'Known information';$('#portfolio-budget').textContent=key(context)||'Keep refining'}
 else {window.FolioWorkspace.selectTab(context.kind==='risk'?'risk':['options','hedge'].includes(context.kind)?'strategy':'overview');}
}
function setContext(next){
 const fresh=!context||next.version!==context.version;
 context=next;if(fresh){following=true;window.FolioStrategyCard?.pending(next)};
 activate();
 if(!following)return;
 if(securityKind(context)){
  const k=key(context);
  if(k!==loadedKey){loadedKey=k;focusSymbol=context.symbols[0];securities=[];period='3m';loadSecurities(k)}
  else if(securities.length)paint();
 }else if(context.kind==='macro')paintMacro();else paintResearch();
}
async function loadSecurities(k){
 const id=++sequence;$('#conversation-canvas').innerHTML=block('Read security data',`<p class="research-loading" role="status">Reading ${esc(k)}  quotes, financials, and historical data…</p>`);
 const hit=cache.get(k);
 if(hit&&Date.now()-hit.time<300000){securities=hit.data;paint();return}
 try{const d=await(await request('/api/research?symbols='+encodeURIComponent(k))).json();if(id!==sequence||key(context)!==k)return;acceptData({workspace:context,securities:d.securities})}
 catch(e){if(id!==sequence)return;$('#conversation-canvas').innerHTML=block('Data temporarily unavailable',`<p>${esc(e.message)}</p><button class="chip" id="retry-security">Retry</button>`);$('#retry-security').onclick=()=>loadSecurities(k)}
}
function acceptData(payload){if(!context||key(payload.workspace)!==key(context)||payload.workspace.version!==context.version)return;securities=payload.securities;cache.set(key(context),{time:Date.now(),data:securities});if(following)paint()}
function current(){return securities.find(d=>d.symbol===focusSymbol&&!d.error)||securities.find(d=>!d.error)}
function quoteHeader(d){
 if(context.kind==='comparison'){
  $('#portfolio-name').textContent=context.symbols.join(' / ')+' · compare';$('.portfolio-budget>span').textContent='Comparison securities';$('#portfolio-budget').textContent=context.symbols.length+' securities';
  $('#portfolio-caption').textContent='Same observation period · Indexed price comparison';return;
 }
 $('#portfolio-name').textContent=d.symbol+' · '+d.name;$('#portfolio-name').title=d.name;
 $('#portfolio-caption').textContent=[d.exchange,d.currency,d.as_of?new Date(d.as_of).toLocaleString('en-US'):null].filter(Boolean).join(' · ');
 $('.portfolio-budget>span').textContent='Latest price';$('#portfolio-budget').textContent=numeric(d.price)+' '+d.currency;
}
function tabs(){return securities.length>1?`<div class="security-switch">${securities.map(d=>`<button data-security="${esc(d.symbol)}" aria-pressed="${d.symbol===focusSymbol}">${esc(d.symbol)}</button>`).join('')}</div>`:''}
function paint(){
 if(!following||!context||!securityKind(context))return;activate();
 const d=current();
 if(!d){$('#conversation-canvas').innerHTML=block('Security data unavailable',securities.map(s=>`<p>${esc(s.symbol)}: ${esc(s.error||'No data')}</p>`).join(''));return}
 quoteHeader(d);
 if(context.kind==='comparison'){
  const all=securities.filter(s=>!s.error);
  $('#conversation-canvas').innerHTML='<div class="analysis-grid"><section class="analysis-cell" data-quadrant="price">'+priceBlock(d)+'</section><section class="analysis-cell" data-quadrant="risk">'+FolioComparison.risk(all)+'</section><section class="analysis-cell" data-quadrant="payoff">'+FolioComparison.forecast(all)+'</section><section class="analysis-cell" data-quadrant="valuation">'+FolioComparison.valuation(all)+'</section></div>'+comparisonBlock()+securities.filter(s=>s.error).map(s=>'<p class="forecast-empty">'+esc(s.symbol)+': '+esc(s.error)+'</p>').join('');
  wire();drawPrice();FolioComparison.draw(all);return;
 }
 const derivativeMode=['options','hedge','futures'].includes(context.kind);
 const stockCurve=derivativeMode?'<div class="forecast-empty">Generating strategy payoff curves…</div>':FolioForecast.chart(d);
 const grid=`<div class="analysis-grid"><section class="analysis-cell" data-quadrant="price">${priceBlock(d)}</section><section class="analysis-cell" data-quadrant="risk">${riskBlock(d)||block('Security risk','<p class="forecast-empty">Insufficient historical data for calculation.</p>')}</section><section class="analysis-cell" data-quadrant="payoff"><div id="stock-forecast"${derivativeMode?' data-derivative="true"':''}><div class="research-heading"><h4>${derivativeMode?'Strategy payoff curve':'Stock forecast return curve'}</h4></div>${stockCurve}</div><div id="strategy-analysis" data-symbol="${esc(d.symbol)}"></div></section><section class="analysis-cell" data-quadrant="valuation"><div class="research-heading"><h4>Future valuation scenarios</h4></div>${FolioForecast.valuation(d)}</section></div>`;
 const extra=/financials|Revenue|Profit|Revenue|Earnings/.test(context.query||'')?financialBlock(d):'';
 $('#conversation-canvas').innerHTML=`${tabs()}<div class="security-snapshot"><span class="price-change ${d.change_pct>=0?'positive':'negative'}">${d.change_pct==null?'No price-change data':(d.change_pct>=0?'+':'')+numeric(d.change_pct)+'%'}</span><span>Latest trading day</span><a href="${esc(d.source)}" target="_blank" rel="noopener noreferrer">Yahoo Finance ↗</a></div>`+grid+(context.kind==='comparison'?comparisonBlock():'')+extra+(['options','hedge'].includes(context.kind)?optionsBlock(d):'');
 wire();drawPrice();FolioForecast.draw(d);global.FolioStrategyCard?.renderAnalysis();
 if(['options','hedge'].includes(context.kind))loadChain(d.symbol);
}
function priceBlock(d){return block(context.kind==='comparison'?'Price history comparison':esc(d?.name||current()?.name||'Underlying')+' · Stock price',`<div class="research-chart-toolbar"><span id="chart-readout">${context.kind==='comparison'?' common trading dates, normalized to  100':'Daily close excluding dividends'}</span><div>${['1m','3m','1y'].map(p=>`<button data-period="${p}" aria-pressed="${period===p}">${{ '1m':'1 month','3m':'3 months','1y':'1 year'}[p]}</button>`).join('')}</div></div><div id="security-price-chart"></div>`)}
function valuationBlock(d){
 const m=d.metrics||{},values=[['Market capitalization',large(m.marketCap),m.marketCap],['P/E · TTM',numeric(m.trailingPE),m.trailingPE],['Forward P/E',numeric(m.forwardPE),m.forwardPE],['P/B',numeric(m.priceToBook),m.priceToBook],['Beta',numeric(m.beta),m.beta],['52-week range',numeric(m.fiftyTwoWeekLow)+' – '+numeric(m.fiftyTwoWeekHigh),m.fiftyTwoWeekHigh],['EPS · TTM',numeric(m.trailingEps),m.trailingEps],['Dividend yield',pct(m.dividendYield),m.dividendYield]].filter(v=>v[2]!=null);
 return values.length?block('Valuation and market metrics',metricCards(values.map(v=>v.slice(0,2)))+`<p class="research-note">${esc(d.currency)} · Yahoo Latest available metrics; forward P/E uses the data source's estimates.</p>`):'';
}
function financialBlock(d){
 const m=d.metrics||{},values=[['Revenue · TTM',large(m.totalRevenue),m.totalRevenue],['Revenue growth',pct(m.revenueGrowth),m.revenueGrowth],['Net margin',pct(m.profitMargins),m.profitMargins],['Free cash flow',large(m.freeCashflow),m.freeCashflow],['Cash',large(m.totalCash),m.totalCash],['Total debt',large(m.totalDebt),m.totalDebt],['ROE',pct(m.returnOnEquity),m.returnOnEquity]].filter(v=>v[2]!=null);
 const rows=d.financials||[];
 if(!rows.length&&!values.length)return '';
 let bars='';if(rows.some(r=>r.revenue!=null)){
  const max=Math.max(...rows.map(r=>Math.abs(r.revenue||0)),1);
  bars='<div class="financial-bars">'+rows.map(r=>`<div><span>${esc(r.period)}</span><div><i style="width:${Math.max(0,(r.revenue||0)/max*100)}%"></i></div><strong>${large(r.revenue)}</strong><small>Net income ${large(r.net_income)}</small></div>`).join('')+'</div>';
 }
 return block('Financial performance',bars+metricCards(values.map(v=>v.slice(0,2)))+`<p class="research-note">Financial currency: ${esc(d.financial_currency)}. Quarterly bars show revenue; growth and margins use  Yahoo  conventions.</p>`);
}
function newsBlock(d){if(!d.news?.length)return '';return block('Recent news',`<div class="security-news">${d.news.map(n=>`<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer"><strong>${esc(n.title)}</strong><small>${esc(n.publisher||'Yahoo Finance')} ${esc(n.date?.slice(0,10)||'')}</small></a>`).join('')}</div>`)}
function companyBlock(d){const c=d.company||{};if(!c.description&&!c.sector)return '';return `<details class="research-block company-details"><summary>Company and business profile <span>${esc(c.sector||d.quote_type||'')}</span></summary><p>${esc([c.industry,c.country].filter(Boolean).join(' · '))}</p><p>${esc(c.description||'No business description')}</p></details>`}
function questionsBlock(){const groups=[['Needs verification',context.questions],['Research direction',context.drivers],['Counterevidence',context.risks]].filter(([,v])=>v?.length);if(!groups.length)return '';return block('Research focus',groups.map(([title,items])=>`<div class="research-question-group"><strong>${title}</strong><ul>${items.map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div>`).join(''))}
function comparisonBlock(){
 const good=securities.filter(d=>!d.error),fields=[['Recent price',d=>numeric(d.price)+' '+d.currency],['Latest trading-day change',d=>d.change_pct==null?'—':numeric(d.change_pct)+'%'],['Recent 3-month price change',d=>d.performance?.['3m']==null?'—':numeric(d.performance['3m'])+'%'],['Market capitalization',d=>large(d.metrics?.marketCap)],['P/E · TTM',d=>numeric(d.metrics?.trailingPE)],['Forward P/E',d=>numeric(d.metrics?.forwardPE)],['Revenue growth',d=>pct(d.metrics?.revenueGrowth)],['Net margin',d=>pct(d.metrics?.profitMargins)],['Beta',d=>numeric(d.metrics?.beta)],['Historical annual volatility',d=>d.security_risk?numeric(d.security_risk.annual_vol)+'%':'—']];
 return block('Comparable metrics',`<div class="research-table-scroll"><table><thead><tr><th>Metric</th>${good.map(d=>`<th>${esc(d.symbol)}<small>${esc(d.name)}</small></th>`).join('')}</tr></thead><tbody>${fields.map(([label,value])=>`<tr><td>${label}</td>${good.map(d=>`<td>${value(d)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="research-note">Prices retain their own currencies; forecasts and  TTM  are listed separately; missing metrics are not fabricated.</p>`);
}
function riskBlock(d){const r=d.security_risk;if(!r)return '';const h=r.histogram,max=Math.max(...h.map(b=>b.probability),1);return block('Security risk',metricCards([['Historical annual volatility',numeric(r.annual_vol)+'%'],['Historical maximum drawdown',numeric(r.historical_max_drawdown)+'%'],['3-month VaR95',numeric(r.var95)+'%'],['3-month CVaR95',numeric(r.cvar95)+'%']])+`<svg class="security-distribution" viewBox="0 0 600 180" role="img" aria-label="${esc(d.symbol)} three-month modeled return distribution">${h.map((b,i)=>`<rect x="${35+i*18}" y="${145-b.probability/max*125}" width="16" height="${b.probability/max*125}" fill="#6a8bd3"><title>${numeric(b.low)}%  to  ${numeric(b.high)}%</title></rect>`).join('')}<text x="35" y="165">${numeric(h[0].low)}%</text><text x="575" y="165" text-anchor="end">${numeric(h.at(-1).high)}%</text></svg><div class="research-range"><span>5% Percentile <b>${numeric(r.p05)}%</b></span><span>Median <b>${numeric(r.median)}%</b></span><span>95% Percentile <b>${numeric(r.p95)}%</b></span></div><details class="method-details"><summary>Methodology</summary><p>${esc(r.method)} Samples ${r.samples}  trading days. These metrics describe the underlying; see the payoff curve for strategy risk.</p></details>`)}
function optionsBlock(d){return '<details class="contract-details"><summary>View option contracts</summary>'+block(d.symbol+' · Option chain',`<p class="research-note">Actual contracts for the current underlying, Bid / Ask, IV  and open interest. Select a contract for detailed quotes.</p><div id="security-options" role="status">Fetching ${esc(d.symbol)} Option chain…</div>`)+'</details>'}
async function loadChain(symbol,expiry=''){
 const el=$('#security-options');if(!el)return;const savedContext=context;
 try{const d=await(await request('/api/options?symbol='+encodeURIComponent(symbol)+(expiry?'&expiry='+encodeURIComponent(expiry):''))).json();if(context!==savedContext||!$('#security-options'))return;
  $('#security-options').innerHTML=d.error?`<p>${esc(d.error)}</p>`:`<div class="option-context-controls"><label>expiry<select id="context-option-expiry">${d.expiries.map(e=>`<option ${e===d.expiry?'selected':''}>${e}</option>`).join('')}</select></label><span>Underlying reference ${numeric(d.spot)}</span></div><div class="research-table-scroll option-chain-scroll"><table><thead><tr><th>Direction / Strike</th><th>Bid / Ask</th><th>IV</th><th>Open interest</th></tr></thead><tbody>${d.contracts.map((c,i)=>`<tr tabindex="0" data-option-detail="${i}"><td>${c.type==='call'?'bullish':'bearish'} ${numeric(c.strike)}</td><td>${numeric(c.bid)} / ${numeric(c.ask)}</td><td>${pct(c.iv)}</td><td>${numeric(c.open_interest,0)}</td></tr>`).join('')}</tbody></table></div><div id="selected-option-detail"></div>`;
  if($('#context-option-expiry'))$('#context-option-expiry').onchange=e=>{el.textContent='Reading contracts…';loadChain(symbol,e.target.value)};
  el.querySelectorAll('[data-option-detail]').forEach(row=>{const show=()=>{const c=d.contracts[+row.dataset.optionDetail];$('#selected-option-detail').innerHTML=`<div class="selected-contract"><strong>${esc(c.symbol)}</strong>${metricCards([['Strike',numeric(c.strike)],['Bid / Ask',numeric(c.bid)+' / '+numeric(c.ask)],['Implied volatility',pct(c.iv)],['Latest trade',numeric(c.last)]])}<p class="research-note">Trade time: ${esc(c.last_trade||'Unknown')} · expiry ${d.expiry}</p></div>`};row.onclick=show;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show()}}});
 }catch(e){if($('#security-options'))$('#security-options').textContent=e.message}
}
function drawPrice(){
 const el=$('#security-price-chart');if(!el)return;
 const selected=context.kind==='comparison'?securities.filter(d=>!d.error):[current()].filter(Boolean),days={ '1m':21,'3m':63,'1y':252}[period];
 let series=selected.map(d=>({symbol:d.symbol,points:(d.history||[]).slice(-days)}));
 if(context.kind==='comparison'&&series.length>1){const common=series[0].points.map(p=>p.date).filter(date=>series.every(s=>s.points.some(p=>p.date===date)));series=series.map(s=>({symbol:s.symbol,points:s.points.filter(p=>common.includes(p.date))}));}
 if(!series.length||series.some(s=>s.points.length<2)){el.innerHTML='<p class="research-note">Insufficient price history for the observation period.</p>';return}
 const indexed=context.kind==='comparison';series=series.map(s=>({...s,values:s.points.map(p=>indexed?p.close/s.points[0].close*100:p.close)}));
 const values=series.flatMap(s=>s.values),low=Math.min(...values),high=Math.max(...values),pad=(high-low)*.15||1,min=low-pad,max=high+pad;
 const x=(i,n)=>45+i/(n-1)*510,y=v=>175-(v-min)/(max-min)*150;
 const paths=series.map((s,j)=>`<polyline points="${s.values.map((v,i)=>`${x(i,s.values.length).toFixed(2)},${y(v).toFixed(2)}`).join(' ')}" stroke="${palette[j]}" stroke-width="2.2" fill="none"/>`).join('');
 el.innerHTML=`<div class="chart-series-key">${series.map((s,j)=>`<span><i style="background:${palette[j]}"></i>${esc(s.symbol)}</span>`).join('')}</div><svg id="context-price-svg" tabindex="0" viewBox="0 0 600 215" role="img" aria-label="${esc(series.map(s=>s.symbol).join(' and '))} ${period} ${indexed?'Indexed':'Close'}Price history">${[0,1,2].map(i=>{const v=min+(max-min)*i/2;return `<line x1="45" x2="555" y1="${y(v)}" y2="${y(v)}" stroke="#e5ebf4"/><text x="5" y="${y(v)+4}">${numeric(v,1)}</text>`}).join('')}${paths}<line id="price-crosshair" x1="555" x2="555" y1="18" y2="175" stroke="#a4b8d9" stroke-dasharray="3 4"/><text x="45" y="200">${series[0].points[0].date}</text><text x="555" y="200" text-anchor="end">${series[0].points.at(-1).date}</text></svg>`;
 const svg=$('#context-price-svg');let index=series[0].points.length-1;
 function inspect(i){index=Math.max(0,Math.min(series[0].points.length-1,i));$('#chart-readout').textContent=series[0].points[index].date+' · '+series.map(s=>`${s.symbol} ${numeric(s.values[index])}${indexed?' (base100)':''}`).join(' / ');const line=$('#price-crosshair');line.setAttribute('x1',x(index,series[0].points.length));line.setAttribute('x2',x(index,series[0].points.length));}
 svg.onpointermove=e=>{const r=svg.getBoundingClientRect();inspect(Math.round(((e.clientX-r.left)/r.width*600-45)/510*(series[0].points.length-1)))};
 svg.onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();inspect(index+(e.key==='ArrowLeft'?-1:1))}};
}
function wire(){
 document.querySelectorAll('[data-security]').forEach(b=>b.onclick=()=>{focusSymbol=b.dataset.security;paint()});
 document.querySelectorAll('[data-period]').forEach(b=>b.onclick=()=>{period=b.dataset.period;document.querySelectorAll('[data-period]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.period===period)));drawPrice()});
}
function paintResearch(){
 const profile=state.profile||state.portfolio?.profile||{};
 $('#conversation-canvas').innerHTML=questionsBlock()+block('Turn a view into research',`<p class="research-lead">${esc(context.summary||'Enter a symbol and your view to see recommendations, prices, and risk.')}</p><div class="research-suggestions"><button data-context-prompt="analyze NVIDIA">For example: research NVIDIA</button><button data-context-prompt="compare NVDA  and  AMD">For example: NVDA / AMD</button><button data-context-prompt="I expect huge moves in NVIDIA; which options strategy fits?">Research options strategies</button></div>`)+((profile.risk||profile.theme)?block('Recorded background',metricCards([profile.risk?['risk tolerance',esc(profile.risk)]:null,profile.theme?['Focus',esc(profile.theme)]:null].filter(Boolean))):'');
 document.querySelectorAll('[data-context-prompt]').forEach(b=>b.onclick=()=>send(b.dataset.contextPrompt));
}
async function paintMacro(){
 const id=++sequence;$('#conversation-canvas').innerHTML=block('Macro data',`<p class="research-loading">Reading FRED Official observations…</p>`);
 try{const d=await(await request('/api/macro')).json();if(id!==sequence||context.kind!=='macro')return;
 $('#conversation-canvas').innerHTML=block('Rates and macro observations',d.configured?`<div class="macro-observations">${d.series.map(s=>`<a href="${esc(s.source||'#')}" target="_blank" rel="noopener noreferrer"><span>${esc(s.label)}</span><strong>${esc(s.observation?.value||'—')}</strong><small>${esc(s.observation?.date||s.error||'No observations')}</small></a>`).join('')}</div>`:'<p>FRED Not configured.</p>')+questionsBlock();
 }catch(e){if(id===sequence)$('#conversation-canvas').textContent=e.message}
}
document.querySelector('.workspace-tabs').addEventListener('click',e=>{if(following&&e.target.closest('[data-worktab]'))$('#conversation-tools').click()},true);
$('#conversation-tools').onclick=()=>{following=!following;if(!following){$('#portfolio').dataset.adaptive='false';$('#portfolio').dataset.following='false';$('#conversation-canvas').hidden=true;if(state.portfolio)FolioWorkspace.render(state.portfolio);$('.portfolio-budget>span').textContent='Planned investment amount';$('#conversation-tools').textContent='Back to current research';if(window.loadRisk)window.loadRisk()}else{activate();if(securityKind(context))paint();else if(context.kind==='macro')paintMacro();else if(context.kind==='research')paintResearch()}};
global.ConversationCanvas=Object.freeze({setContext,acceptData,restore(){activate();if(following&&current()&&securityKind(context))quoteHeader(current())},isSecurity(){return following&&securityKind(context)},reset(){window.FolioStrategyCard?.reset();context=null;securities=[];loadedKey='';following=true;sequence++;$('#conversation-toolbar').hidden=true;$('#conversation-canvas').hidden=true;$('#portfolio').removeAttribute('data-adaptive');$('#portfolio').removeAttribute('data-following');$('.portfolio-budget>span').textContent='Planned investment amount'}});
})(window);
