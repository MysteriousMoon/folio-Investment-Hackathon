/* Markdown is sanitized before KaTeX replaces math placeholders. No remote assets. */
(function (global) {
  'use strict';
  const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function renderInto(element, source) {
    const text = String(source ?? '');
    element.classList.add('rich-text');
    if (!global.marked || !global.DOMPurify || !global.katex) {
      element.textContent = text;
      element.classList.add('rich-text-fallback');
      return;
    }
    element.classList.remove('rich-text-fallback');
    const formulas = [];
    function mathHTML(token) {
      if (token.incomplete) return escapeHTML(token.raw);
      const id = formulas.push({tex: token.tex, display: token.display}) - 1;
      const tag = token.display && token.block ? 'div' : 'span';
      return `<${tag} class="math-slot" data-math-id="${id}"></${tag}>`;
    }
    const parser = new global.marked.Marked({gfm: true, breaks: true, async: false});
    parser.use({extensions: [
      {
        name: 'folioBlockMath', level: 'block',
        start(src) { const m = /(?:^|\n) {0,3}(?:\$\$|\\\[)/.exec(src); return m?.index; },
        tokenizer(src) {
          const match = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])(?:[ \t]*\n|[ \t]*$)/.exec(src);
          if (match) return {type:'folioBlockMath', raw:match[0], tex:match[1] ?? match[2], display:true, block:true};
          const opening = /^ {0,3}(\$\$|\\\[)/.exec(src);
          if (opening && !src.slice(opening[0].length).includes(opening[1] === '$$' ? '$$' : '\\]')) {
            return {type:'folioBlockMath', raw:src, incomplete:true};
          }
        }, renderer: mathHTML
      },
      {
        name: 'folioInlineMath', level: 'inline',
        start(src) { const n = src.search(/\$|\\[([]/); return n < 0 ? undefined : n; },
        tokenizer(src) {
          for (const [pattern, display] of [
            [/^\\\(([\s\S]+?)\\\)/,false],
            [/^\\\[([\s\S]+?)\\\]/,true],
            [/^\$\$([\s\S]+?)\$\$/,true],
            [/^\$(?!\s)([^\n$]*?[^\s$])\$(?!\d)/,false]
          ]) {
            const m=pattern.exec(src);
            if(m) return {type:'folioInlineMath',raw:m[0],tex:m[1],display};
          }
          const opening=/^(\\\(|\\\[|\$\$)/.exec(src);
          if(opening) return {type:'folioInlineMath',raw:src,incomplete:true};
        }, renderer: mathHTML
      }
    ]});
    try {
      const html = parser.parse(text);
      element.innerHTML = global.DOMPurify.sanitize(html, {
        USE_PROFILES: {html:true},
        FORBID_TAGS: ['style','iframe','img','video','audio','form','input','button','textarea','select'],
        FORBID_ATTR: ['style'],
        ALLOW_DATA_ATTR: true
      });
      element.querySelectorAll('.math-slot').forEach(slot => {
        const formula = formulas[Number(slot.dataset.mathId)];
        if (!formula) { slot.remove(); return; }
        global.katex.render(formula.tex, slot, {
          displayMode: formula.display, throwOnError: false, trust: false,
          strict: 'ignore', maxExpand: 1000, maxSize: 20,
          output: 'htmlAndMathml', macros: {}
        });
      });
      element.querySelectorAll('a').forEach(link => {
        const href=link.getAttribute('href') || '';
        if (!/^(https?:\/\/|mailto:|#|\/(?!\/))/i.test(href)) link.removeAttribute('href');
        if (/^https?:\/\//i.test(href)) {
          link.target='_blank'; link.rel='noopener noreferrer';
        }
      });
      element.querySelectorAll('table').forEach(table => {
        const wrap=document.createElement('div');wrap.className='rich-table-scroll';
        table.replaceWith(wrap);wrap.append(table);
      });
    } catch (_) {
      element.textContent = text;
      element.classList.add('rich-text-fallback');
    }
  }
  global.FolioRichText = Object.freeze({renderInto});
})(window);
