/* Server submission identity is authoritative; this makes the pending save clear. */
function initPawnDraftSubmit() {
  const form = document.querySelector('[data-draft-save-form]');
  if (!form) return;
  const status = form.querySelector('[data-draft-save-status]');
  const buttons = [...form.querySelectorAll('button[type="submit"], input[type="submit"]')];
  const original = buttons.map(button => ({button, disabled: button.disabled, text: button.textContent}));
  let actionInput = null;

  function reset() {
    delete form.dataset.draftSubmitting;
    form.removeAttribute('aria-busy');
    original.forEach(({button, disabled, text}) => {
      button.disabled = disabled;
      button.textContent = text;
    });
    if (actionInput) { actionInput.remove(); actionInput = null; }
    status.hidden = true;
    status.textContent = '';
  }

  // Registered after price preflight. Its first event is prevented; only the
  // validated, resumed submit locks controls. Preserve the clicked button's
  // action in a hidden field because disabled buttons are not submitted.
  form.addEventListener('submit', event => {
    if (form.dataset.draftSubmitting === 'true') { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    const action = event.submitter?.value === 'preview' ? 'preview' : 'save';
    actionInput = document.createElement('input');
    actionInput.type = 'hidden'; actionInput.name = 'action'; actionInput.value = action;
    form.append(actionInput);
    form.dataset.draftSubmitting = 'true';
    form.setAttribute('aria-busy', 'true');
    buttons.forEach(button => { button.disabled = true; });
    const submitter = event.submitter || buttons.find(button => button.value === 'save');
    if (submitter) submitter.textContent = action === 'preview' ? 'Preparing preview…' : 'Saving…';
    status.textContent = action === 'preview'
      ? 'Please wait while the amounts are checked. No loan is created by a preview.'
      : 'Please wait while your draft is saved. Repeated submission of this form will not create another loan.';
    status.hidden = false;
  });

  // Returning from a network error or Back/Forward cache must permit a retry
  // with the same hidden submission token, never issue a new form identity.
  window.addEventListener('pageshow', reset);
}
document.addEventListener("DOMContentLoaded", initPawnDraftSubmit);
document.addEventListener("loan-entry:ready", initPawnDraftSubmit);
