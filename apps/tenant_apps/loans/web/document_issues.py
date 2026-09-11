"""Document issues; existing services own business rules."""

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import (
    get_object_or_404,
    render,
)
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.filters import LoanDocumentIssueFilter
from apps.tenant_apps.loans.models import LoanDocumentIssue


@loans_setup_required
def document_issue_list(request):
    issues = LoanDocumentIssue.objects.filter(
        workspace=request.loans_workspace
    ).select_related(
        "revision__layout", "print_profile_revision__profile", "issued_by"
    ).order_by("-issued_at", "-pk")
    issue_filter = LoanDocumentIssueFilter(request.GET, queryset=issues)
    page_obj = Paginator(issue_filter.qs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "loans/setup/documents/issues.html",
        {
            "issue_filter": issue_filter,
            "issues": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


def _document_issue(request, issue_pk):
    return get_object_or_404(
        LoanDocumentIssue.objects.select_related(
            "revision__layout", "print_profile_revision__profile",
            "prior_issue", "issued_by",
        ),
        pk=issue_pk,
        workspace=request.loans_workspace,
    )


@loans_setup_required
def document_issue_detail(request, issue_pk):
    return render(
        request,
        "loans/setup/documents/issue_detail.html",
        {"issue": _document_issue(request, issue_pk)},
    )


@loans_setup_required
@never_cache
def document_issue_artifact(request, issue_pk):
    issue = _document_issue(request, issue_pk)
    issue.artifact.open("rb")
    content = issue.artifact.read()
    issue.artifact.close()
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="loan-document-issue-{issue.pk}.pdf"'
    )
    response["X-Rokkad-Document-Issue"] = str(issue.pk)
    response["X-Rokkad-PDF-Hash"] = issue.pdf_hash
    return response
