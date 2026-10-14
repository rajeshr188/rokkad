(() => {
  const queues = document.getElementById('dashboard-queues');
  const overview = document.getElementById('dashboard-overview');
  if (!queues || !overview || !window.htmx) return;
  let queuesSettled = false;
  let overviewVisible = false;
  let overviewRequested = false;
  const sectionFor = event => [queues, overview].includes(event.detail.target) ? event.detail.target : null;
  const errorFor = section => document.getElementById(section.id + '-error');
  const loadOverview = () => {
    if (!queuesSettled || !overviewVisible || overviewRequested) return;
    const bounds = overview.getBoundingClientRect();
    if (bounds.top >= window.innerHeight || bounds.bottom <= 0) return;
    overviewRequested = true;
    window.htmx.trigger(overview, 'dashboard-overview-load');
  };
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      overviewVisible = entries.some(entry => entry.isIntersecting);
      loadOverview();
      if (overviewRequested) observer.disconnect();
    });
    observer.observe(overview);
  } else {
    overviewVisible = true;
  }
  document.addEventListener('htmx:beforeRequest', event => {
    const section = sectionFor(event);
    if (!section) return;
    errorFor(section).hidden = true;
    section.setAttribute('aria-busy', 'true');
  });
  document.addEventListener('htmx:beforeSwap', event => {
    const section = sectionFor(event);
    if (!section) return;
    const xhr = event.detail.xhr;
    if (xhr.status >= 200 && xhr.status < 300 && xhr.getResponseHeader('X-Rokkad-Fragment') !== section.id) {
      event.detail.shouldSwap = false;
      const destination = new URL(xhr.responseURL, window.location.href);
      if (destination.origin === window.location.origin && destination.pathname !== window.location.pathname) {
        // Repeat ordinary navigation so login/billing return to the whole dashboard.
        window.location.reload();
      }
    }
  });
  document.addEventListener('htmx:afterRequest', event => {
    const section = sectionFor(event);
    if (!section) return;
    section.setAttribute('aria-busy', 'false');
    errorFor(section).hidden = !event.detail.failed &&
      event.detail.xhr.getResponseHeader('X-Rokkad-Fragment') === section.id;
    if (section === queues) {
      queuesSettled = true;
      loadOverview();
    }
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-dashboard-retry]');
    if (!button) return;
    const section = document.getElementById(button.dataset.dashboardRetry);
    if (![queues, overview].includes(section) || section.getAttribute('aria-busy') === 'true') return;
    window.htmx.ajax('GET', section.getAttribute('hx-get'), {
      source: section, target: section, swap: 'innerHTML',
    }).catch(() => {}); // The request events retain the visible retry message.
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
})();
