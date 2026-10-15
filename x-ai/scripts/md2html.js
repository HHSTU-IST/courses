/* md2html 页面脚本：由 scripts/md2html.py 读取，内联或外链到生成的 HTML 中。
 *
 * 代码块右上角的「复制」按钮：样式见 styles/md2html.css 中 .copy-btn，
 * 结构由 md2html.py 生成的 <figure class="code-block"> + <pre class="highlight">
 * 决定，改动这里时请一并确认选择器。
 */
(function () {
  var COPY_SVG = '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"/></svg>';
  var CHECK_SVG = '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"/></svg>';

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } finally { document.body.removeChild(ta); }
    return Promise.resolve();
  }

  document.querySelectorAll('.markdown-body figure.code-block').forEach(function (fig) {
    var pre = fig.querySelector('pre.highlight');
    if (!pre) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy-btn';
    btn.title = '复制代码';
    btn.setAttribute('aria-label', '复制代码');
    btn.innerHTML = COPY_SVG;
    btn.addEventListener('click', function () {
      var code = pre.querySelector('code');
      copyText((code || pre).innerText).then(function () {
        btn.classList.add('copied');
        btn.innerHTML = CHECK_SVG;
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.innerHTML = COPY_SVG;
        }, 1200);
      });
    });
    fig.appendChild(btn);
  });
})();
