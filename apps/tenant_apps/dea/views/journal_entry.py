from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django_tables2 import RequestConfig

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import JournalEntryFilter
from ..forms import JournalEntryForm
from ..models import JournalEntry
from ..tables import JournalEntriesTable


def journal_entry_list(request):
    # Get all journal entries
    context = {}
    f = JournalEntryFilter(
        request.GET,
        queryset=JournalEntry.objects.select_related("content_type").order_by(
            "-created"
        ),
    )
    table = JournalEntriesTable(f.qs)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)
    context["table"] = table
    context["filter"] = f
    return render(request, "dea/journal_entry_list.html", context)


@for_htmx(use_block="content")
def journal_entry_detail(request, pk):
    # Get the journal entry with the given ID
    journal_entry = JournalEntry.objects.get(id=pk)
    context = {"object": journal_entry}
    return TemplateResponse(request, "dea/journalentry_detail.html", context)


def journal_entry_delete(request, pk):
    # Get the journal entry with the given ID
    journal_entry = get_object_or_404(JournalEntry, id=pk)

    if request.method == "POST":
        # Delete the journal entry
        journal_entry.delete()
        # Redirect to the journal entry list page
        return redirect("dea_journal_entries_list")

    context = {"journal_entry": journal_entry}
    return render(request, "dea/journalentry_confirm_delete.html", context)


def create_journal_entry(request):
    # Create a new journal entry
    if request.method == "POST":
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            je = form.save()
            return redirect(je)
    else:
        form = JournalEntryForm()
    return render(request, "dea/journal_entry_form.html", {"form": form})
