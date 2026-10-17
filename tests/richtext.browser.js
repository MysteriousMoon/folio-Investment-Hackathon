(function(){
'use strict';
const results=[];
const assert=(value,message)=>{if(!value)throw Error(message)};
const host=document.querySelector('#fixture');
function render(source){FolioRichText.renderInto(host,source);assert(!host.classList.contains('rich-text-fallback'),'renderer unexpectedly fell back');return host}
function test(name,fn){try{fn();results.push({name,ok:true})}catch(e){results.push({name,ok:false,error:e.message})}}
test('Markdown headings, emphasis, lists and GFM tables',()=>{
 render('## Risk report\n\n**Important** and *Notes*\n\n- Equities\n- Treasuries\n\n| Asset | Weight |\n| --- | --- |\n| Equities | 60% |');
 assert(host.querySelector('h2')&&host.querySelector('strong')&&host.querySelectorAll('li').length===2,'Markdown structure missing');
 assert(host.querySelector('.rich-table-scroll table'),'table wrapper missing');
});
test('All four TeX delimiters',()=>{
 render(String.raw`Inline $x^2$  and  \(\sigma_p\).

$$
\sigma_p=\sqrt{w^T\Sigma w}
$$

\[
E[R_p]=\sum_i w_i\mu_i
\]`);
 assert(host.querySelectorAll('.katex').length===4,'expected four formulae');
 assert(host.querySelectorAll('.katex-display').length===2,'expected two display equations');
 assert(!host.querySelector('.katex-error'),'formula failed');
});
test('Markdown cannot consume TeX underscores, escapes or matrix rows',()=>{
 render(String.raw`\[\begin{bmatrix}a_1 & b_2\\c_3 & d_4\end{bmatrix}\]`);
 assert(host.querySelector('.katex')&&!host.querySelector('.katex-error'),'matrix failed');
});
test('Inline and fenced code remain literal',()=>{
 render('`$x$`\n\n```tex\n\\[x^2\\]\n```');
 assert(host.querySelectorAll('code').length===2,'code nodes missing');
 assert(!host.querySelector('.katex'),'code was rendered as math');
});
test('Ordinary dollar amounts remain literal',()=>{
 const source='Budget $100, adjust to  $200.Cash $50.';render(source);
 assert(!host.querySelector('.katex'),'currency misidentified as formula');
 assert(host.textContent.trim()===source,'currency text changed');
});
test('Every streamed prefix is safe and final output matches completed rendering',()=>{
 const source=String.raw`**Portfolio risk**: \(\sigma_p = \sqrt{w^T\Sigma w}\).`;
 for(let i=0;i<=source.length;i++)render(source.slice(0,i));
 const html=host.innerHTML;render(source);assert(host.innerHTML===html,'stream and final differ');
 assert(host.querySelector('.katex'),'completed streamed formula missing');
});
test('Unclosed and invalid TeX do not interrupt messages',()=>{
 render(String.raw`Unclosed  \(\frac{1`);assert(host.textContent.includes('\\('),'incomplete delimiter lost');
 render(String.raw`$\frac{1}$`);assert(host.textContent.length>0,'invalid math removed message');
});
test('HTML events, javascript URLs and remote images are removed',()=>{
 render('<img src="https://example.com/track" onerror="alert(1)"><svg onload="alert(1)"></svg><a href="javascript:alert(1)">Dangerous</a><p style="position:fixed">Text</p>');
 assert(!host.querySelector('img,svg,script,[onerror],[onload],[style]'),'unsafe HTML survived');
 assert(![...host.querySelectorAll('a')].some(a=>a.getAttribute('href')?.startsWith('javascript:')),'unsafe link survived');
});
test('Untrusted TeX cannot introduce links or HTML',()=>{
 render(String.raw`$\href{javascript:alert(1)}{x}$ $\htmlStyle{position:fixed}{x}$`);
 assert(!host.querySelector('a,[style*="fixed"]'),'trusted TeX feature enabled');
});
test('External links have safe target attributes',()=>{
 render('[FRED](https://fred.stlouisfed.org/)');const a=host.querySelector('a');
 assert(a.target==='_blank'&&a.rel.includes('noopener'),'unsafe target');
});
test('Math inside table cells and inline display syntax',()=>{
 render(String.raw`| Metric | Formula |
| --- | --- |
| volatility | $\sigma_p$ |

Formula: $$x^2$$.`);
 assert(host.querySelector('td .katex'),'table formula missing');
 assert(host.querySelectorAll('.katex').length===2,'inline display formula missing');
});
test('Macro definitions do not leak between messages',()=>{
 render(String.raw`$\gdef\abc{123}\abc$`);render(String.raw`$\abc$`);
 assert(!host.textContent.includes('123'),'macros leaked');
});
render(String.raw`## Portfolio risk

**Portfolio return** and risk should be considered together:

\[
\sigma_p=\sqrt{\mathbf{w}^{T}\Sigma\mathbf{w}}
\]

| Metric | Meaning |
| --- | --- |
| $\Delta$ | Directional sensitivity |
| $\mathrm{CVaR}_{95\%}$ | Worst 5%  scenario average loss |

- **Equities**: Growth exposure
- **options**: Protection and nonlinear returns

Code example:

\`\`\`python
portfolio_return = weights @ returns
\`\`\`
` .replaceAll('\\`','`'));
const failures=results.filter(r=>!r.ok);const status=document.querySelector('#results');
status.textContent=JSON.stringify({passed:results.length-failures.length,total:results.length,failures},null,2);
status.dataset.passed=String(!failures.length);
document.title=failures.length?'Rendering checks FAILED':'Rendering checks PASSED';
})();
