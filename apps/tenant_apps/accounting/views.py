"""Read-only K8 visual workspace over canonical accounting selectors."""

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orgs.permissions import get_effective_permissions

from .access import accounting_workspace_required
from . import facade
from .evidence import accountant_evidence_pack
from .feature_flags import (
    get_accounting_activation_state,
    get_accounting_workflow_mode,
    set_accounting_successor_enabled,
    set_accounting_workflow_mode,
)
from .forms import (
    AccountingActivationForm,
    AccountingBootstrapForm,
    AccountingReversalForm,
    AccountingTransactionForm,
    ReceiptAllocationForm,
)
from .models import AccountingBook, Ledger, LedgerSide, PersistedVoucherState, Voucher
from .selectors import posted_journal_lines


def _primary_book():
    return AccountingBook.objects.select_related("organization").filter(book_key="PRIMARY").first()


def _require_enabled(workspace):
    state = get_accounting_activation_state(workspace)
    if not state.enabled:
        raise PermissionDenied("Standalone accounting writes are disabled for this workspace.")


def _permissions(request):
    return get_effective_permissions(request.user, request.accounting_workspace)


@accounting_workspace_required
def dashboard(request):
    book = _primary_book()
    activation = get_accounting_activation_state(request.accounting_workspace)
    if book is None:
        return render(request, "accounting/dashboard.html", {
            "book": None, "activation": activation, "evidence": None,
            "permissions": _permissions(request),
        })
    evidence = accountant_evidence_pack(book=book)
    return render(request, "accounting/dashboard.html", {
        "book": book,
        "activation": activation,
        "evidence": evidence,
        "recent_vouchers": book.vouchers.filter(
            state=PersistedVoucherState.POSTED
        ).order_by("-effective_date", "-voucher_number")[:8],
        "pending_vouchers": book.vouchers.exclude(
            state=PersistedVoucherState.POSTED
        ).order_by("effective_date", "voucher_number")[:20],
        "permissions": _permissions(request),
        "workflow_mode": get_accounting_workflow_mode(request.accounting_workspace),
    })


@accounting_workspace_required
def reports(request):
    book = get_object_or_404(AccountingBook, book_key="PRIMARY")
    return render(request, "accounting/reports.html", {
        "book": book,
        "activation": get_accounting_activation_state(request.accounting_workspace),
        "evidence": accountant_evidence_pack(book=book),
    })


@accounting_workspace_required
def setup(request):
    if "accounting_period_manage" not in _permissions(request):
        raise PermissionDenied("Only an accounting administrator may initialize the book.")
    form = AccountingBootstrapForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        facade.bootstrap(
            actor=request.user,
            workspace=request.accounting_workspace,
            period_key=data["period_key"],
            start_date=data["start_date"],
            end_date=data["end_date"],
        )
        messages.success(
            request,
            "Primary INR book, period, and MVP ledgers are ready. Activation remains off.",
        )
        return redirect("accounting:dashboard")
    return render(request, "accounting/setup.html", {"form": form})


@accounting_workspace_required
def activation(request):
    if "accounting_period_manage" not in _permissions(request):
        raise PermissionDenied("Only an accounting administrator may change activation.")
    state = get_accounting_activation_state(request.accounting_workspace)
    form = AccountingActivationForm(
        request.POST or None,
        initial={
            "enabled": state.enabled,
            "workflow_mode": get_accounting_workflow_mode(request.accounting_workspace),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            state = set_accounting_successor_enabled(
                request.accounting_workspace,
                enabled=form.cleaned_data["enabled"],
                actor=request.user,
            )
            set_accounting_workflow_mode(
                request.accounting_workspace,
                mode=form.cleaned_data["workflow_mode"],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, "accounting/activation.html", {
                "form": form, "activation": state,
            })
        messages.success(
            request,
            "Standalone accounting writes are now enabled for this workspace."
            if state.enabled else
            "Standalone accounting writes are disabled for this workspace.",
        )
        return redirect("accounting:dashboard")
    return render(request, "accounting/activation.html", {
        "form": form,
        "activation": state,
    })


@accounting_workspace_required
def voucher_detail(request, pk):
    voucher = get_object_or_404(
        Voucher.objects.select_related("posting_batch"),
        pk=pk,
        book__book_key="PRIMARY",
    )
    lines = [] if voucher.state != PersistedVoucherState.POSTED else [
        row for row in posted_journal_lines(book=voucher.book) if row.batch_key == voucher.voucher_key
    ]
    account_transaction = None
    if voucher.transactions.exists() and hasattr(voucher.transactions.first(), "account_detail"):
        account_transaction = voucher.transactions.first().account_detail
    return render(request, "accounting/voucher_detail.html", {
        "voucher": voucher,
        "journal_lines": lines,
        "activation": get_accounting_activation_state(request.accounting_workspace),
        "permissions": _permissions(request),
        "account_transaction": account_transaction,
        "allocation_form": (
            ReceiptAllocationForm(
                book=voucher.book, external_account=account_transaction.external_account
            ) if account_transaction and voucher.source_type == "CUSTOMER_RECEIPT"
            and voucher.state == PersistedVoucherState.POSTED else None
        ),
        "reversal_batch": (
            voucher.posting_batch.reversal_batches.select_related("voucher").first()
            if voucher.state == PersistedVoucherState.POSTED else None
        ),
        "is_reversal": (
            voucher.posting_batch.reversal_of_id is not None
            if voucher.state == PersistedVoucherState.POSTED else False
        ),
        "workflow_mode": get_accounting_workflow_mode(request.accounting_workspace),
        "is_owner": request.user.pk == request.accounting_workspace.owner_id,
    })


@accounting_workspace_required
def transaction_create(request):
    _require_enabled(request.accounting_workspace)
    book = get_object_or_404(AccountingBook, book_key="PRIMARY")
    form = AccountingTransactionForm(request.POST or None, book=book)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        kind = data["transaction_type"]
        if kind != AccountingTransactionForm.CASH_SALE:
            data["customer_account"] = facade.create_customer_receivable_account(
                actor=request.user,
                workspace=request.accounting_workspace,
                book=book,
                party=data["party"],
                new_party_name=data["new_party_name"],
                effective_from=data["effective_date"],
            )
        voucher = facade.create_draft(
            actor=request.user, workspace=request.accounting_workspace, book=book,
            voucher_key=f"UI-{kind}-{data['source_id']}",
            idempotency_key=f"ui:{kind}:{data['source_id']}",
            effective_date=data["effective_date"], source_system="ACCOUNTING_UI",
            source_type=kind, source_id=data["source_id"], source_version="1",
            rule_key=f"MVP_{kind}", rule_version="1", narration=data["narration"],
        )
        money = dict(
            sequence=1, amount=data["amount"], currency="INR",
            base_amount=data["amount"], base_currency="INR",
            exchange_rate=Decimal("1"), rate_source="BOOK_BASE_CURRENCY",
            narration=data["narration"],
        )
        if voucher.transactions.exists():
            messages.info(request, "This draft already exists; no duplicate line was created.")
            return redirect("accounting:voucher_detail", pk=voucher.pk)
        if kind == AccountingTransactionForm.CASH_SALE:
            facade.add_ledger_line(
                actor=request.user, workspace=request.accounting_workspace, voucher=voucher,
                debit_ledger=Ledger.objects.get(book=book, ledger_key="CASH"),
                credit_ledger=Ledger.objects.get(book=book, ledger_key="SALES"), **money,
            )
        else:
            facade.add_account_line(
                actor=request.user, workspace=request.accounting_workspace, voucher=voucher,
                ledger=Ledger.objects.get(
                    book=book, ledger_key=("SALES" if kind == AccountingTransactionForm.CREDIT_SALE else "CASH")
                ), external_account=data["customer_account"],
                ledger_side=(LedgerSide.CREDIT if kind == AccountingTransactionForm.CREDIT_SALE else LedgerSide.DEBIT),
                **money,
            )
        workflow_mode = get_accounting_workflow_mode(request.accounting_workspace)
        if workflow_mode == "OWNER" and request.user.pk == request.accounting_workspace.owner_id:
            facade.owner_confirm(
                actor=request.user,
                workspace=request.accounting_workspace,
                voucher=voucher,
                open_item_key=(voucher.source_id if kind == AccountingTransactionForm.CREDIT_SALE else ""),
            )
            messages.success(request, "Transaction confirmed and posted.")
        else:
            messages.success(request, "Draft created. A different authorized user must approve it.")
        return redirect("accounting:voucher_detail", pk=voucher.pk)
    return render(request, "accounting/transaction_form.html", {
        "form": form,
        "workflow_mode": get_accounting_workflow_mode(request.accounting_workspace),
        "is_owner": request.user.pk == request.accounting_workspace.owner_id,
    })


@accounting_workspace_required
@require_POST
def voucher_authorize(request, pk):
    _require_enabled(request.accounting_workspace)
    voucher = get_object_or_404(Voucher, pk=pk, book__book_key="PRIMARY")
    if voucher.created_by_id == request.user.pk:
        raise PermissionDenied("The voucher maker cannot authorize the same voucher.")
    facade.authorize(actor=request.user, workspace=request.accounting_workspace, voucher=voucher)
    messages.success(request, "Voucher authorized. A different user must post it.")
    return redirect("accounting:voucher_detail", pk=pk)


@accounting_workspace_required
@require_POST
def voucher_post(request, pk):
    _require_enabled(request.accounting_workspace)
    voucher = get_object_or_404(Voucher, pk=pk, book__book_key="PRIMARY")
    if voucher.source_type == AccountingTransactionForm.CREDIT_SALE:
        facade.post_receivable(
            actor=request.user, workspace=request.accounting_workspace, voucher=voucher,
            open_item_key=voucher.source_id,
        )
    else:
        facade.post(actor=request.user, workspace=request.accounting_workspace, voucher=voucher)
    messages.success(request, "Voucher posted to the immutable journal.")
    return redirect("accounting:voucher_detail", pk=pk)


@accounting_workspace_required
@require_POST
def receipt_allocate(request, pk):
    _require_enabled(request.accounting_workspace)
    voucher = get_object_or_404(
        Voucher, pk=pk, book__book_key="PRIMARY", state=PersistedVoucherState.POSTED,
        source_type=AccountingTransactionForm.CUSTOMER_RECEIPT,
    )
    settlement = voucher.transactions.get(sequence=1).account_detail
    form = ReceiptAllocationForm(
        request.POST, book=voucher.book, external_account=settlement.external_account
    )
    if form.is_valid():
        facade.allocate_receipt(
            actor=request.user, workspace=request.accounting_workspace,
            settlement_transaction=settlement, open_item=form.cleaned_data["open_item"],
            amount=form.cleaned_data["amount"],
        )
        messages.success(request, "Receipt allocation recorded without creating another posting.")
    else:
        messages.error(request, "Receipt allocation could not be recorded.")
    return redirect("accounting:voucher_detail", pk=pk)


@accounting_workspace_required
def voucher_reverse(request, pk):
    _require_enabled(request.accounting_workspace)
    voucher = get_object_or_404(
        Voucher.objects.select_related("posting_batch"),
        pk=pk, book__book_key="PRIMARY", state=PersistedVoucherState.POSTED,
    )
    if voucher.posting_batch.reversal_of_id is not None:
        raise ValidationError("A reversal voucher cannot itself be reversed.")
    if voucher.posting_batch.reversal_batches.exists():
        return redirect("accounting:voucher_detail", pk=pk)
    form = AccountingReversalForm(
        request.POST or None, initial={"reversal_date": voucher.effective_date}
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if get_accounting_workflow_mode(request.accounting_workspace) == "OWNER":
            facade.owner_reverse(
                actor=request.user, workspace=request.accounting_workspace,
                original=voucher.posting_batch,
                reversal_date=data["reversal_date"], reason=data["reason"],
            )
        else:
            facade.reverse(
                actor=request.user, workspace=request.accounting_workspace,
                original=voucher.posting_batch,
                voucher_key=f"UI-REV-{voucher.posting_batch.pk}",
                idempotency_key=f"ui:reversal:{voucher.posting_batch.pk}",
                reversal_date=data["reversal_date"], reason=data["reason"],
            )
        messages.success(request, "Reversal posted. The original voucher remains immutable.")
        return redirect("accounting:voucher_detail", pk=pk)
    return render(request, "accounting/reversal_form.html", {
        "voucher": voucher, "form": form,
    })
