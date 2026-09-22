/* Section links reveal native disclosures; forms still work without JavaScript. */
document.addEventListener('DOMContentLoaded', () => {
  const reveal = () => {
    const section = document.getElementById(window.location.hash.slice(1));
    if (section?.matches('details[data-policy-section]')) {
      section.open = true;
      section.scrollIntoView({ block: 'start' });
    }
  };
  window.addEventListener('hashchange', reveal);
  document.querySelectorAll('[data-policy-navigation] a').forEach(link => {
    link.addEventListener('click', () => {
      const section = document.getElementById(link.hash.slice(1));
      if (section?.matches('details[data-policy-section]')) section.open = true;
    });
  });
  reveal();
});
