function initPawnCollateralEditor() {
  const container = document.getElementById("collateral-formset");
  const addButton = document.getElementById("add-collateral");
  const template = document.getElementById("empty-collateral-form");
  const totalForms = document.getElementById("id_collateral-TOTAL_FORMS");
  if (!container || !addButton || !template || !totalForms || container.closest("form").hasAttribute("data-paper-entry")) return;

  container.querySelectorAll("[data-collateral-form]").forEach(function (row) {
    const deleteInput = row.querySelector("input[name$='-DELETE']");
    if (deleteInput && deleteInput.checked) row.hidden = true;
  });

  addButton.addEventListener("click", function () {
    const index = Number.parseInt(totalForms.value, 10);
    container.insertAdjacentHTML(
      "beforeend",
      template.innerHTML.replace(/__prefix__/g, String(index))
    );
    totalForms.value = String(index + 1);
    const row = container.lastElementChild;
    const firstInput = row && row.querySelector("input:not([type='hidden']), select");
    if (firstInput) firstInput.focus();
  });

  container.addEventListener("click", function (event) {
    const removeButton = event.target.closest("[data-remove-collateral]");
    if (!removeButton) return;
    const row = removeButton.closest("[data-collateral-form]");
    const deleteInput = row && row.querySelector("input[name$='-DELETE']");
    if (!row || !deleteInput) return;
    deleteInput.checked = true;
    row.hidden = true;
  });
}
document.addEventListener("DOMContentLoaded", initPawnCollateralEditor);
document.addEventListener("loan-entry:ready", initPawnCollateralEditor);
