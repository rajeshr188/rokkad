// Move the canonical loan controls; never duplicate forms, IDs or financial data.
(() => {
  if (window.rokkadLoanLayouts) {
    window.rokkadLoanLayouts.init(document);
    return;
  }
  const controllers = new WeakMap();
  function setup(root) {
    if (controllers.has(root)) return;
    const selector = root.querySelector('#loan-detail-layout');
    const template = root.querySelector('[data-loan-layout-template]');
    if (!selector || !template) return;
    const slots = Array.from(root.querySelectorAll('[data-loan-block]'), node => {
      const marker = document.createComment('loan-layout-position');
      node.before(marker);
      return {node, marker, region: node.dataset.loanBlock};
    });
    // Explanations remain in Documents while print buttons stay prominent.
    for (const block of root.querySelectorAll('[data-loan-block="print"]')) {
      const node = block.firstElementChild;
      if (node?.tagName === 'DIV') {
        const marker = document.createComment('loan-print-explanation');
        node.before(marker);
        slots.push({node, marker, region: 'documents'});
      }
    }
    const folded = Array.from(root.querySelectorAll('details[data-loan-section]'), node => ({node, open: node.open}));
    let shell = null;
    let active = 'overview';
    const key = root.dataset.layoutKey;
    const message = root.querySelector('[data-layout-message]');
    function restore() {
      for (const {node, marker} of slots) marker.after(node);
      for (const saved of folded) saved.node.open = saved.open;
      shell?.remove();
      shell = null;
      root.dataset.loanLayout = 'classic';
    }
    function select(section, focus = false) {
      if (!shell) return;
      active = section;
      for (const panel of shell.querySelectorAll('[data-loan-panel]')) {
        const chosen = panel.dataset.loanPanel === section;
        if (root.dataset.loanLayout === 'sections') {
          panel.hidden = false;
          if (chosen) panel.parentElement.open = true;
        } else panel.hidden = !chosen;
      }
      for (const tab of shell.querySelectorAll('[data-loan-tab]')) {
        const chosen = tab.dataset.loanTab === section;
        tab.classList.toggle('active', chosen);
        tab.setAttribute('aria-selected', String(chosen));
        tab.tabIndex = chosen ? 0 : -1;
        if (focus && chosen) tab.focus();
      }
    }
    function apply(layout, persist = false) {
      if (!['tabs', 'desk', 'sections', 'classic'].includes(layout)) layout = 'tabs';
      if (root.dataset.loanLayout === 'classic') {
        for (const saved of folded) saved.open = saved.node.open;
      }
      restore();
      if (layout !== 'classic') {
        shell = template.content.firstElementChild.cloneNode(true);
        root.append(shell);
        for (const {node, region} of slots) shell.querySelector(`[data-loan-region="${region}"]`).append(node);
        for (const saved of folded) saved.node.open = true;
        root.dataset.loanLayout = layout;
        const nav = shell.querySelector('[role="tablist"]');
        if (layout === 'desk') {
          shell.querySelector('.loan-desk-actions').append(shell.querySelector('.loan-action-bar'));
          nav.classList.replace('nav-tabs', 'nav-pills');
          nav.setAttribute('aria-orientation', 'vertical');
        } else if (layout === 'sections') {
          nav.hidden = true;
          for (const panel of shell.querySelectorAll('[data-loan-panel]')) {
            const section = panel.dataset.loanPanel;
            const fold = document.createElement('details');
            fold.className = 'accordion-item loan-section-fold';
            fold.open = section === active;
            const summary = document.createElement('summary');
            summary.id = `loan-section-${section}`;
            summary.textContent = shell.querySelector(`[data-loan-tab="${section}"]`).textContent;
            panel.before(fold);
            fold.append(summary, panel);
            panel.className = 'accordion-body';
            panel.removeAttribute('role');
            panel.removeAttribute('tabindex');
            panel.setAttribute('aria-labelledby', summary.id);
            fold.addEventListener('toggle', () => { if (fold.isConnected && fold.open) active = section; });
          }
        }
        select(active);
      }
      selector.value = layout;
      if (persist) {
        try { localStorage.setItem(key, layout); message.textContent = message.dataset.saved; }
        catch { message.textContent = message.dataset.unsaved; }
      }
    }
    function revealTarget(target) {
      if (!root.contains(target)) return;
      if (shell && target.id === 'loan-overview') target = shell.querySelector('#loan-panel-overview');
      const panel = target.closest('[data-loan-panel]');
      if (panel) select(panel.dataset.loanPanel);
      for (let parent = target.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
      }
      target.scrollIntoView({block: 'start'});
      if (target.hasAttribute('tabindex')) target.focus({preventScroll: true});
    }
    controllers.set(root, {reveal: revealTarget});
    selector.addEventListener('change', () => apply(selector.value, true));
    root.addEventListener('click', event => {
      const tab = event.target.closest('[data-loan-tab]');
      if (tab) {
        select(tab.dataset.loanTab);
        history.replaceState(history.state, '', '#loan-panel-' + active);
      }
    });
    root.addEventListener('keydown', event => {
      const tab = event.target.closest('[data-loan-tab]');
      if (!tab || !['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const tabs = Array.from(shell.querySelectorAll('[data-loan-tab]'));
      let index = tabs.indexOf(tab);
      if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = tabs.length - 1;
      else index = (index + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length;
      select(tabs[index].dataset.loanTab, true);
    });
    let preferred = 'tabs';
    try { preferred = localStorage.getItem(key) || preferred; }
    catch { message.textContent = message.dataset.unsaved; }
    try { apply(preferred); }
    catch { restore(); selector.value = 'classic'; }
    root.querySelector('[data-loan-layout-controls]').hidden = false;
  }
  function reveal(hash) {
    if (!hash || hash === '#') return;
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    const root = target.closest('[data-loan-detail]');
    if (root) controllers.get(root)?.reveal(target);
  }
  function init(container) {
    if (container?.matches?.('[data-loan-detail]')) setup(container);
    else container?.querySelectorAll?.('[data-loan-detail]').forEach(setup);
    reveal(location.hash);
  }
  window.rokkadLoanLayouts = {init};
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (link) reveal(link.hash);
  });
  window.addEventListener('hashchange', () => reveal(location.hash));
  document.addEventListener('htmx:load', event => init(event.detail.elt));
  init(document);
})();
