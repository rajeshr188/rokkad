function initPawnCollateralEditor() {
  const container = document.getElementById("collateral-formset");
  const addButton = document.getElementById("add-collateral");
  const template = document.getElementById("empty-collateral-form");
  const totalForms = document.getElementById("id_collateral-TOTAL_FORMS");
  if (!container || !addButton || !template || !totalForms || container.dataset.editorReady) return;
  container.dataset.editorReady = 'true';
  const changed = () => container.closest('form').dispatchEvent(new Event('loan-collateral:changed'));

  container.querySelectorAll("[data-collateral-form]").forEach(function (row) {
    const deleteInput = row.querySelector("input[name$='-DELETE']");
    if (deleteInput && deleteInput.checked) row.hidden = true;
  });

  addButton.addEventListener("click", function () {
    const index = Number.parseInt(totalForms.value, 10);
    if (index >= 100) return;
    container.insertAdjacentHTML(
      "beforeend",
      template.innerHTML.replace(/__prefix__/g, String(index))
    );
    totalForms.value = String(index + 1);
    const row = container.lastElementChild;
    const firstInput = row && row.querySelector("input:not([type='hidden']), select");
    if (firstInput) firstInput.focus();
    changed();
  });

  container.addEventListener("click", function (event) {
    const removeButton = event.target.closest("[data-remove-collateral]");
    if (!removeButton) return;
    const row = removeButton.closest("[data-collateral-form]");
    const deleteInput = row && row.querySelector("input[name$='-DELETE']");
    if (!row || !deleteInput) return;
    deleteInput.checked = true;
    row.hidden = true;
    changed();
  });
}
document.addEventListener("DOMContentLoaded", initPawnCollateralEditor);
document.addEventListener("loan-entry:ready", initPawnCollateralEditor);
