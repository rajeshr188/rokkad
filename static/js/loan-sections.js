// Keep section links and old bookmarks usable when their content is folded.
(() => {
  function reveal(hash) {
    if (!hash || hash === '#') return;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.matches('details[data-loan-section]')) parent.open = true;
    }
    target.scrollIntoView({block: 'start'});
    if (target.hasAttribute('tabindex')) target.focus({preventScroll: true});
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (link) reveal(link.hash);
  });
  window.addEventListener('hashchange', () => reveal(location.hash));
  reveal(location.hash);
})();
