/* Resolve saved fragment-only item links that now fall outside the custody page. */
(() => {
  "use strict";
  const tabs = document.getElementById("khata-tabs");
  const active = tabs && tabs.querySelector('[aria-current="page"]');
  if (active && tabs.scrollWidth > tabs.clientWidth) {
    const tabBounds = active.getBoundingClientRect();
    const listBounds = tabs.getBoundingClientRect();
    tabs.scrollLeft += tabBounds.left - listBounds.left - (tabs.clientWidth - tabBounds.width) / 2;
  }
  const chooser = document.getElementById("khata-section-picker");
  if (chooser) chooser.addEventListener("change", () => {
    const url = new URL(location.href);
    url.search = "";
    url.searchParams.set("tab", chooser.value);
    url.hash = "";
    location.assign(url.href);
  });
  const match = /^#collateral-item-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(location.hash);
  if (!match || document.getElementById(location.hash.slice(1))) return;
  const url = new URL(location.href);
  if (url.searchParams.has("item")) return;
  url.searchParams.set("section", "collateral");
  url.searchParams.set("item", match[1]);
  url.hash = "collateral-item-" + match[1].toLowerCase();
  url.searchParams.delete("collateral-page");
  location.replace(url.href);
})();
