/* Charts only format server-calculated report figures; the table is authoritative. */
(() => {
  const source = document.getElementById('portfolio-charts');
  if (!source || !window.Chart) return;
  const number = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 4 });
  const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
  const compactMoney = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', notation: 'compact', maximumFractionDigits: 1 });
  JSON.parse(source.textContent).forEach((report, index) => {
    const canvas = document.getElementById(`portfolio-chart-${index}`);
    if (!canvas) return;
    const format = value => report.unit === 'INR' ? money.format(value) : `${number.format(value)} ${report.unit}`;
    new Chart(canvas, {
      type: 'bar',
      data: { labels: report.labels, datasets: [{ label: report.title, data: report.values.map(Number), backgroundColor: '#2563eb' }] },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => format(context.parsed.x) } } },
        scales: {
          x: { beginAtZero: true, ticks: { maxRotation: 0, callback: value => report.unit === 'INR' ? compactMoney.format(value) : number.format(value) } },
          y: { ticks: { autoSkip: false, callback: function(value) { const label = this.getLabelForValue(value); return label.length > 18 ? label.slice(0, 17) + '\u2026' : label; } } }
        }
      }
    });
  });
})();
