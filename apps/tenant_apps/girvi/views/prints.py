import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BalancedColumns,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
)

from apps.tenant_apps.girvi.documents.loan_ticket import (
    get_custom_jcl,
    grid_template,
    print_labels_pdf,
)
from apps.tenant_apps.girvi.filters import LoanFilter
from apps.tenant_apps.girvi.models.template import LoanTemplate
from apps.tenant_apps.girvi.service_modules.printing import LoanPrintService
from apps.tenant_apps.notify.models import Notification
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
    create_bulk_loan_reminder_group,
)
from apps.tenant_apps.notify_v2.models import NotificationJob
from apps.tenant_apps.notify_v2.services import create_girvi_reminder_batch

from ..forms import LoanSelectionForm
from ..models import GivenLoan


logger = logging.getLogger(__name__)

_NOTIFY_V2_EVENT_MAP = {
    "LOAN_FIRST_REMINDER": "loan.first_reminder_due",
    "LOAN_SECOND_REMINDER": "loan.second_reminder_due",
    "LOAN_FINAL_NOTICE": "loan.final_notice_due",
    "LOAN_AUCTION_NOTICE": "loan.auction_notice_due",
}

_NOTIFY_V2_CHANNEL_MAP = {
    Notification.MediumType.Email: NotificationJob.Channel.EMAIL,
    Notification.MediumType.Letter: NotificationJob.Channel.LETTER,
    Notification.MediumType.Post: NotificationJob.Channel.POST,
    Notification.MediumType.SMS: NotificationJob.Channel.SMS,
    Notification.MediumType.Whatsapp: NotificationJob.Channel.WHATSAPP,
}


def _parse_selected_ids(raw_ids):
    cleaned = []
    invalid_count = 0
    for raw_id in raw_ids:
        try:
            parsed = int(raw_id)
            if parsed > 0:
                cleaned.append(parsed)
            else:
                invalid_count += 1
        except (TypeError, ValueError):
            invalid_count += 1
    return list(dict.fromkeys(cleaned)), invalid_count


def print_labels(request):
    loan_kind = request.POST.get("loan_kind", "given")
    if loan_kind != "given":
        return HttpResponse(status=400, content="Print labels is available only for Given loans.")

    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        filter = LoanFilter(
            request.GET,
            queryset=GivenLoan.objects.filter(release__isnull=True)
            .select_related("borrower")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("borrower")
    else:
        selection, invalid_count = _parse_selected_ids(request.POST.getlist("selection"))
        if invalid_count:
            logger.warning("print_labels rejected invalid IDs: %s", request.POST.getlist("selection"))
            return HttpResponse(status=400, content="Invalid loan selection.")
        if not selection:
            return HttpResponse(status=400, content="Please select at least one unreleased given loan.")

        selected_loans = (
            GivenLoan.objects.filter(release__isnull=True)
            .filter(id__in=selection)
            .order_by("borrower")
        )

        if selected_loans.count() != len(selection):
            return HttpResponse(status=400, content="Some selected loans are not eligible for printing.")

    if selected_loans:
        form = LoanSelectionForm(initial={"loans": selected_loans})
        template_name = "girvi/loan/print_labels.html#content" if request.htmx else "girvi/loan/print_labels.html"
        return render(request, template_name, {"form": form})

    return HttpResponse(status=200, content="No unreleased loans selected.")


def print_label(request):
    if request.method == "POST":
        form = LoanSelectionForm(request.POST)
        if form.is_valid():
            loans = form.cleaned_data["loans"]
            return print_labels_pdf(loans)

        template_name = "girvi/loan/print_labels.html#content" if request.htmx else "girvi/loan/print_labels.html"
        return render(request, template_name, {"form": form})

    else:
        form = LoanSelectionForm()
        template_name = "girvi/loan/print_labels.html#content" if request.htmx else "girvi/loan/print_labels.html"
        return render(request, template_name, {"form": form})


@login_required
def notify_print(request):
    loan_kind = request.POST.get("loan_kind", "given")
    if loan_kind != "given":
        return HttpResponse(status=400, content="Notifications can be created only for Given loans.")

    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        filter = LoanFilter(
            request.GET,
            queryset=GivenLoan.objects.filter(release__isnull=True)
            .select_related("borrower")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("borrower")
    else:
        selection, invalid_count = _parse_selected_ids(request.POST.getlist("selection"))
        if invalid_count:
            logger.warning("notify_print rejected invalid IDs: %s", request.POST.getlist("selection"))
            return HttpResponse(status=400, content="Invalid loan selection.")
        if not selection:
            return HttpResponse(status=400, content="Please select at least one unreleased given loan.")

        selected_loans = (
            GivenLoan.objects.filter(release__isnull=True)
            .filter(id__in=selection)
            .order_by("borrower")
        )

        if selected_loans.count() != len(selection):
            return HttpResponse(status=400, content="Some selected loans are not eligible for notifications.")

    if selected_loans:
        notice_code = request.POST.get("notice_code", DEFAULT_LOAN_REMINDER_CODE)
        medium_type = request.POST.get(
            "medium_type",
            Notification.MediumType.Letter,
        )

        try:
            ng = create_bulk_loan_reminder_group(
                selected_loans,
                notice_code=notice_code,
                medium_type=medium_type,
            )
        except ValueError as exc:
            return HttpResponse(status=400, content=str(exc))
        except Exception:
            logger.exception("Error creating reminder notifications.")
            return HttpResponse(status=500, content="Error creating notifications.")

        return redirect(ng.get_absolute_url())

    return HttpResponse(status=200, content="No unreleased loans selected.")


@login_required
def notify_print_v2(request):
    loan_kind = request.POST.get("loan_kind", "given")
    if loan_kind != "given":
        return HttpResponse(status=400, content="Notify V2 batches can be created only for Given loans.")

    select_all = request.POST.get("selectall")
    selected_loans = None

    if select_all == "selected":
        filterset = LoanFilter(
            request.GET,
            queryset=GivenLoan.objects.filter(release__isnull=True)
            .select_related("borrower")
            .prefetch_related("notifications", "loanitems"),
        )
        selected_loans = list(filterset.qs.order_by("borrower"))
    else:
        selection, invalid_count = _parse_selected_ids(request.POST.getlist("selection"))
        if invalid_count:
            logger.warning("notify_print_v2 rejected invalid IDs: %s", request.POST.getlist("selection"))
            return HttpResponse(status=400, content="Invalid loan selection.")
        if not selection:
            return HttpResponse(status=400, content="Please select at least one unreleased given loan.")

        selected_queryset = (
            GivenLoan.objects.filter(release__isnull=True)
            .filter(id__in=selection)
        )

        if selected_queryset.count() != len(selection):
            return HttpResponse(status=400, content="Some selected loans are not eligible for notifications.")

        selected_loans = list(selected_queryset.order_by("borrower"))

    if not selected_loans:
        return HttpResponse(status=200, content="No unreleased loans selected.")

    notice_code = request.POST.get("notice_code", DEFAULT_LOAN_REMINDER_CODE)
    medium_type = request.POST.get("medium_type", Notification.MediumType.Letter)
    event_key = _NOTIFY_V2_EVENT_MAP.get(notice_code, "loan.first_reminder_due")
    channel = _NOTIFY_V2_CHANNEL_MAP.get(medium_type, NotificationJob.Channel.LETTER)

    try:
        batch_result = create_girvi_reminder_batch(
            loans=selected_loans,
            created_by=request.user,
            event_key=event_key,
            channel=channel,
        )
    except ValueError as exc:
        return HttpResponse(status=400, content=str(exc))
    except Exception:
        logger.exception("Error creating notify_v2 reminder batch.")
        return HttpResponse(status=500, content="Error creating notify_v2 batch.")

    try:
        messages.success(
            request,
            f"Created notify_v2 batch with {batch_result.preview.borrower_count} recipient(s).",
        )
    except Exception:
        pass
    return redirect(batch_result.batch.get_absolute_url())


import base64


@login_required
def print_loan(request, pk=None):
    loan = get_object_or_404(
        GivenLoan.objects.select_related(
            "borrower", "series", "series__license"
        ).prefetch_related(
            "loanitems", "borrower__address", "borrower__contactno"
        ),
        pk=pk,
    )
    result = LoanPrintService.build_print_result(
        loan,
        template_resolver=LoanTemplate.objects.get_default,
        renderer=get_custom_jcl,
    )
    if not result.template:
        messages.warning(request, result.error_message)
        return redirect("girvi:girvi_loan_detail", pk=loan.pk)

    if not result.ok:
        readiness = result.readiness or {}
        logger.error(
            "Loan PDF generation failed for loan=%s template_id=%s print_option=%s readiness=%s",
            getattr(loan, "loan_id", None),
            getattr(result.template, "pk", None),
            getattr(result.template, "print_option", None),
            readiness.get("summary"),
        )
        messages.error(request, result.error_message)
        return redirect("girvi:girvi_loan_detail", pk=loan.pk)

    response = HttpResponse(result.pdf, content_type="application/pdf")
    response["Content-Disposition"] = f"inline; filename='{loan.loan_id}.pdf'"
    response["Content-Transfer-Encoding"] = "binary"
    return response
    # Encode the PDF in base64
    # pdf_base64 = base64.b64encode(pdf).decode("utf-8")

    # # Render the object HTML
    # object_html = f"""
    # <object data="data:application/pdf;base64,{pdf_base64}" type="application/pdf" width="100%" height="600px">
    #     <p>Your browser does not support PDFs. <a href="data:application/pdf;base64,{pdf_base64}">Download the PDF</a>.</p>
    # </object>
    # """
    # return HttpResponse(object_html)


@login_required
def print_grid_template(request):
    pdf = grid_template()

    # Encode the PDF in base64
    pdf_base64 = base64.b64encode(pdf).decode("utf-8")

    # Render the object HTML
    object_html = f"""
    <object data="data:application/pdf;base64,{pdf_base64}" type="application/pdf" width="100%" height="600px">
        <p>Your browser does not support PDFs. <a href="data:application/pdf;base64,{pdf_base64}">Download the PDF</a>.</p>
    </object>
    """
    return HttpResponse(object_html)


class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_header_footer(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.setFont("Helvetica", 10)
        self.drawRightString(
            200 * mm, 20 * mm, "Page %d of %d" % (self._pageNumber, page_count)
        )

        # Draw header
        self.saveState()
        styles = getSampleStyleSheet()
        header = Paragraph("Loan Report", styles["Heading1"])
        w, h = header.wrap(self._pagesize[0] - 1 * inch, self._pagesize[1])
        header.drawOn(self, inch, self._pagesize[1] - inch - h + 20)
        self.restoreState()


# @login_required
# def generate_loans_ledger_pdf(response):
#     # add annotation,bookmarks,table of contents,pagination,header and footer
#     response = HttpResponse(content_type="application/pdf")
#     response["Content-Disposition"] = 'attachment; filename="loan_report.pdf"'

#     doc = SimpleDocTemplate(response, pagesize=landscape(A4))
#     elements = []

#     styles = getSampleStyleSheet()
#     cover_title = Paragraph("Loan Report", styles["Title"])
#     cover_subtitle = Paragraph("Generated on: [Date]", styles["Heading2"])
#     elements.append(Spacer(1, 2 * inch))
#     elements.append(cover_title)
#     elements.append(Spacer(1, 0.5 * inch))
#     elements.append(cover_subtitle)
#     elements.append(PageBreak())

#     # Add Table of Contents
#     toc = TableOfContents()
#     toc.levelStyles = [
#         ParagraphStyle(fontSize=14, name="Heading1", leading=16),
#         ParagraphStyle(fontSize=12, name="Heading2", leading=14),
#         ParagraphStyle(fontSize=10, name="Heading3", leading=12),
#     ]
#     elements.append(Paragraph("Table of Contents", getSampleStyleSheet()["Heading1"]))
#     elements.append(toc)
#     elements.append(PageBreak())

#     # Add Table
#     data = [
#         [
#             "Loan ID",
#             "Loan Date",
#             "Customer",
#             "Loan Amount",
#             "Weight",
#             "Present Value",
#             "Item Description",
#             "Release Date",
#             "Released By",
#         ]
#     ]
#     loans = Loan.objects.filter(series__is_active = True).select_related("customer", "release")[:500]
#     for loan in loans.iterator(chunk_size=100):
#         data.append(
#             [
#                 loan.loan_id,
#                 loan.loan_date.date(),
#                 loan.customer,
#                 loan.loan_amount,
#                 loan.weight,
#                 loan.value,
#                 loan.item_desc,
#                 loan.release.release_date.date() if loan.is_released else "",
#                 loan.release.released_by if loan.is_released else "",
#             ]
#         )
#     # Define column widths
#     col_widths = [
#         0.5 * inch,
#         1 * inch,
#         1 * inch,
#         1 * inch,
#         1 * inch,
#         1 * inch,
#         2.5 * inch,
#         1 * inch,
#         1 * inch,
#     ]
#     table = Table(data, colWidths=col_widths,repeatRows=1, splitByRow=1)
#     table.setStyle(
#         TableStyle(
#             [
#                 ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
#                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
#                 ("ALIGN", (0, 0), (-1, -1), "CENTER"),
#                 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
#                 ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
#                 ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
#                 ("GRID", (0, 0), (-1, -1), 1, colors.black),
#             ]
#         )
#     )

#     elements.append(table)

#     # Define a frame for the content
#     frame = Frame(
#         inch,
#         inch,
#         landscape(A4)[0] - 2 * inch,
#         landscape(A4)[1] - 2 * inch,
#         id="normal",
#     )

#     # Create a PageTemplate with the frame
#     template = PageTemplate(id="test", frames=frame, onPage=PageNumCanvas)

#     # Build PDF with the template
#     doc.addPageTemplates([template])
#     # Build PDF
#     doc.multiBuild(elements, canvasmaker=PageNumCanvas)

#     return response


# @login_required
# def generate_loans_ledger_pdf(request):
#     # Create the HttpResponse object with the appropriate PDF headers.
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="loans_ledger.pdf"'

#     # Create the PDF object, using the response object as its "file."
#     doc = SimpleDocTemplate(response, pagesize=letter)
#     styles = getSampleStyleSheet()

#     # Create a list to hold the elements for the PDF.
#     elements = []

#     # Add the header
#     header = Paragraph("Loan Report", styles["Heading1"])
#     elements.append(header)

#     # Query the Series model to get all active series
#     series_list = Series.objects.filter(is_active=True)

#     for series in series_list:
#         # Add series title
#         series_title = Paragraph(f"Series: {series.name}", styles["Heading2"])
#         elements.append(series_title)

#         # Add Table
#         data = [
#             [
#                 "Loan ID",
#                 "Loan Date",
#                 "Customer",
#                 "Loan Amount",
#                 "Weight",
#                 "Present Value",
#                 "Item Description",
#                 "Release Date",
#                 "Released By",
#             ]
#         ]
#         loans = Loan.objects.filter(series=series).select_related("customer", "release")[:50]
#         for loan in loans.iterator(chunk_size=100):
#             data.append(
#                 [
#                     loan.loan_id,
#                     loan.loan_date.date(),
#                     loan.customer,
#                     loan.loan_amount,
#                     loan.weight,
#                     loan.value,
#                     loan.item_desc,
#                     loan.release.release_date.date() if loan.is_released else "",
#                     loan.release.released_by if loan.is_released else "",
#                 ]
#             )
#         # Define column widths
#         col_widths = [
#             0.5 * inch,
#             1 * inch,
#             1 * inch,
#             1 * inch,
#             1 * inch,
#             1 * inch,
#             2.5 * inch,
#             1 * inch,
#             1 * inch,
#         ]
#         table = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
#         table.setStyle(
#             TableStyle(
#                 [
#                     ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
#                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
#                     ("ALIGN", (0, 0), (-1, -1), "CENTER"),
#                     ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
#                     ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
#                     ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
#                     ("GRID", (0, 0), (-1, -1), 1, colors.black),
#                 ]
#             )
#         )
#         elements.append(table)

#     # Build the PDF
#     doc.build(elements)

#     return response


@login_required
def generate_unreleased_pdf(request):
    numbers = GivenLoan.objects.unreleased().values_list("loan_id", flat=True)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="numbers_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []

    list_style = getSampleStyleSheet()["OrderedList"]
    list_style.bulletFontName = "Courier"
    list_style.bulletFontSize = 10
    list_style.leftIndent = 24
    list_items_builtins = [
        ListItem(Paragraph(b, getSampleStyleSheet()["Normal"])) for b in numbers
    ]
    elements.append(
        BalancedColumns(
            F=[ListFlowable(list_items_builtins, style=list_style)], nCols=3
        )
    )
    elements.append(PageBreak())

    doc.build(elements)
    return response


from openpyxl import Workbook

from ..models import GivenLoan, Series
from ..resources import LedgerResource


@login_required
def export_loans_to_excel(request):
    # Create a workbook
    wb = Workbook()
    wb.remove(wb.active)  # Remove the default sheet

    # Fetch all series
    series_list = Series.objects.filter(is_active=True)

    for series in series_list:
        # Create a new worksheet for each series
        ws = wb.create_sheet(title=series.name)

        # Get loans for the current series
        loans = GivenLoan.objects.filter(series=series).for_table_display()

        # Use LoanResource to export data
        loan_resource = LedgerResource()
        dataset = loan_resource.export(loans)

        # Add headers to the worksheet
        headers = dataset.headers
        ws.append(headers)

        # Add loan data to the worksheet
        for row in dataset:
            ws.append(row)

    # Save the workbook to a response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{request.user.profile.workspace.name}_ledger.xlsx"'
    wb.save(response)

    return response
