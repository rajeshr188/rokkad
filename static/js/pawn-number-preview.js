(() => {
  const series = document.getElementById('id_series');
  const output = document.getElementById('expected-loan-number');
  const data = document.getElementById('loan-number-previews');
  if (!series || !output || !data) return;
  const previews = JSON.parse(data.textContent);
  function update() {
    const preview = Object.prototype.hasOwnProperty.call(previews, series.value)
      ? previews[series.value] : null;
    output.textContent = preview
      ? (preview.value || preview.error || output.dataset.unavailableMessage)
      : output.dataset.selectMessage;
    output.classList.toggle('text-danger', Boolean(preview && !preview.value));
    output.classList.toggle('font-monospace', Boolean(preview && preview.value));
  }
  series.addEventListener('change', update);
  // Select2 emits its selection changes through jQuery on enhanced selects.
  if (window.jQuery) window.jQuery(series).on('change', update);
  window.addEventListener('pageshow', update);
  update();
})();
