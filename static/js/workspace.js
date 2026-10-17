(function(global){
 'use strict';
 const $=selector=>document.querySelector(selector);
 let snapshot=null,activeTab='overview';
 const roles=['Growth engine','Diversified allocation','Defensive allocation','Multiple assets','Liquidity'];
 const shortNames=['Theme equities','Broad equities','Treasuries','gold','Cash'];
 const strategyLabels={protective_put:'Protective put',call_spread:'call spread',put_spread:'put spread',covered_call:'covered call',collar:'collar protection',straddle:'Straddle',butterfly:'Butterfly spread',iron_condor:'Iron condor',futures_hedge:'Short futures hedge',futures_long:'long futures'};
 function selectTab(name,focus=false){
  if(!['overview','risk','strategy'].includes(name))return;
  activeTab=name;
  document.querySelectorAll('[data-worktab]').forEach(b=>{const on=b.dataset.worktab===name;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;if(on&&focus)b.focus()});
  document.querySelectorAll('[data-work-panel]').forEach(p=>p.hidden=p.dataset.workPanel!==name);
 }
 function draftPrompt(text){const input=document.querySelector('#prompt');input.value=text;if(innerWidth<=760)mobile('chat');input.focus();input.setSelectionRange(text.length,text.length)}
 function render(p){
  const a=p.profile,previous=snapshot;
  $('#portfolio-name').textContent=p.title;
  $('.draft').textContent=p.missing.length?'More information needed':'Allocation generated';
  $('#portfolio-caption').textContent=[a.risk||'Risk to be confirmed',a.horizon?`${Number(a.horizon.toFixed(1))} -year investment horizon`:'Horizon to be confirmed',a.market||'Market to be confirmed'].join(' · ');
  $('#portfolio-budget').textContent=a.amount?money(a.amount):'Incomplete';
  const thesis=a.theme?`Build ${a.theme} growth exposure, balanced with broad equities, Treasuries, and liquid assets.`:'Build a portfolio of growth and defensive assets around your financial goals.';
  const overlays=(a.strategies||[]).slice(0,2).map(k=>strategyLabels[k]||k);
  $('#portfolio-thesis').textContent=thesis+(overlays.length?` Use ${overlays.join(' and ')} to adjust the return structure.`:'');
  const changes=[];
  if(previous&&previous.version!==p.version){
   p.rows.forEach((r,i)=>{if(previous.rows[i]?.weight!==r.weight)changes.push(`${shortNames[i]} ${previous.rows[i]?.weight??0}% → ${r.weight}%`)});
   const added=(a.strategies||[]).filter(k=>!(previous.profile.strategies||[]).includes(k));
   const removed=(previous.profile.strategies||[]).filter(k=>!(a.strategies||[]).includes(k));
   if(added.length)changes.unshift('Added '+added.map(k=>strategyLabels[k]||k).join(', '));
   if(removed.length)changes.unshift('remove '+removed.map(k=>strategyLabels[k]||k).join(', '));
   if(a.amount!==previous.profile.amount)changes.push('Investment amount updated to '+money(a.amount));
  }
  $('#workspace-change').textContent=changes.length?changes.slice(0,3).join('; '):'The portfolio develops through chat. Select holdings to inspect allocation rationale.';
  $('#workspace-change').classList.toggle('has-change',changes.length>0);
  $('#portfolio-visual').innerHTML=`<div class="allocation-band" role="img" aria-label="${esc(p.rows.map(r=>`${r.name} ${r.weight}%`).join(', '))}">${p.rows.map((r,i)=>`<span style="width:${r.weight}%;background:${colors[i]}" title="${esc(r.name)} ${r.weight}%"></span>`).join('')}</div><div class="allocation-key">${p.rows.map((r,i)=>`<span><i style="background:${colors[i]}"></i>${shortNames[i]} <b>${r.weight}%</b></span>`).join('')}</div>`;
  $('#allocation-list').innerHTML=p.rows.map((r,i)=>{
   const changed=previous&&previous.version!==p.version&&(previous.rows[i]?.weight!==r.weight||previous.rows[i]?.amount!==r.amount);
   return `<details class="allocation-position${changed?' position-changed':''}"><summary><span class="asset-swatch" style="--asset-color:${colors[i]}"></span><span class="asset-identity"><strong>${esc(r.name)}</strong><small>${esc(r.example)} <span>${roles[i]}</span></small></span><span class="asset-share">${r.weight}%</span><span class="asset-value">${r.amount==null?'—':esc(money(r.amount))}</span><span class="position-chevron" aria-hidden="true">⌄</span></summary><div class="asset-explanation"><p>${esc(r.reason)}</p><small>${esc(r.detail)}</small><button class="text-action" data-adjust-asset="${i}">Discuss this allocation with the assistant</button></div></details>`;
  }).join('');
  $('#portfolio-note').textContent=`Version ${p.version} · Autosaved`;
  renderDerivatives(p,null);

  snapshot=JSON.parse(JSON.stringify(p));
  selectTab(activeTab);
  if(global.ConversationCanvas)global.ConversationCanvas.restore();
 }
 function renderDerivatives(p,data){
  const target=$('#derivative-overview');if(!target)return;
  if(data?.positions?.length){
   target.innerHTML=data.positions.map(d=>`<div class="overlay-row"><div><strong>${esc(d.name)}</strong><small>${d.legs.length?'Option structure':'Futures exposure'} · Overlay</small></div><div><span>Notional exposure</span><b>${d.notional_pct}%</b></div><div><span>${d.legs.length?'Net premium':'Margin'}</span><b>${d.legs.length?d.premium_pct:d.margin_pct}%</b></div></div>`).join('');
  }else if((p.profile.strategies||[]).length){
   target.innerHTML=`<div class="overlay-pending">${p.profile.strategies.map(k=>`<span>${esc(strategyLabels[k]||k)}</span>`).join('')}<small>Calculating exposure and capital requirements…</small></div>`;
  }else target.innerHTML='<div class="overlay-empty"><p>Using the spot allocation.</p><span>Options or futures can adjust protection and return structure.</span><button class="text-action" data-go-tab="strategy">Explore protection strategies</button></div>';
 }
 document.addEventListener('click',e=>{
  const tab=e.target.closest('[data-worktab],[data-go-tab]');if(tab){selectTab(tab.dataset.worktab||tab.dataset.goTab);return}
  const adjust=e.target.closest('[data-adjust-asset]');if(adjust&&snapshot){draftPrompt(`I want to adjust ${snapshot.rows[Number(adjust.dataset.adjustAsset)].name} allocation, `)}
 });
 document.querySelector('.workspace-tabs').addEventListener('keydown',e=>{
  if(!e.target.matches('[data-worktab]'))return;const tabs=['overview','risk','strategy'];let next;
  if(e.key==='ArrowRight')next=(tabs.indexOf(activeTab)+1)%3;if(e.key==='ArrowLeft')next=(tabs.indexOf(activeTab)+2)%3;if(e.key==='Home')next=0;if(e.key==='End')next=2;
  if(next!=null){e.preventDefault();selectTab(tabs[next],true)}
 });
 $('#market-context').addEventListener('toggle',()=>{if($('#market-context').open)loadData()});
 $('#discuss-plan').onclick=()=>draftPrompt('Use my current holdings to plan staged entries and hedge execution for this portfolio.');
 global.FolioWorkspace=Object.freeze({render,renderDerivatives,selectTab,reset(){snapshot=null;selectTab('overview')}});
})(window);
