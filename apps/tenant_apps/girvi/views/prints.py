from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (BalancedColumns, Frame, ListFlowable, ListItem,
                                LongTable, PageBreak, PageTemplate, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from apps.tenant_apps.utils.htmx_utils import for_htmx
from apps.tenant_apps.utils.loan_pdf import (get_custom_jcl, get_custom_jsk,
                                             get_loan_template, get_notice_pdf,
                                             print_labels_pdf)

from ..forms import LoanSelectionForm
from ..models import Loan


def print_labels(request):
    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        print("all selected")
        # get query parameters if all row selected and retrive queryset
        print(request.GET)
        filter = LoanFilter(
            request.GET,
            queryset=Loan.objects.unreleased()
            .select_related("customer", "release")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("customer")
        print(f"selected loans: {selected_loans.count()}")
    else:
        print("partially selected")
        # get the selected loan ids from the request
        selection = request.POST.getlist("selection")

        selected_loans = (
            Loan.objects.unreleased().filter(id__in=selection).order_by("customer")
        )

    if selected_loans:
        form = LoanSelectionForm(initial={"loans": selected_loans})
        from render_block import render_block_to_string

        response = render_block_to_string(
            "girvi/loan/print_labels.html", "content", {"form": form}, request
        )
        return HttpResponse(content=response)
        # return render(request, 'girvi/loan/print_labels.html', {'form': form})

    return HttpResponse(status=200, content="No unreleased loans selected.")


@for_htmx(use_block="content")
def print_label(request):
    if request.method == "POST":
        form = LoanSelectionForm(request.POST)
        if form.is_valid():
            loans = form.cleaned_data["loans"]
            return print_labels_pdf(loans)

        return render(request, "girvi/loan/print_labels.html", {"form": form})

    else:
        form = LoanSelectionForm()
        return render(request, "girvi/loan/print_labels.html", {"form": form})


@login_required
def notify_print(request):
    # check if user wanted all rows to be selected
    all = request.POST.get("selectall")
    selected_loans = None

    if all == "selected":
        print("all selected")
        # get query parameters if all row selected and retrive queryset
        print(request.GET)
        filter = LoanFilter(
            request.GET,
            queryset=Loan.objects.unreleased()
            .select_related("customer", "release")
            .prefetch_related("notifications", "loanitems"),
        )

        selected_loans = filter.qs.order_by("customer")
        print(f"selected loans: {selected_loans.count()}")
    else:
        print("partially selected")
        # get the selected loan ids from the request
        selection = request.POST.getlist("selection")

        selected_loans = (
            Loan.objects.unreleased().filter(id__in=selection).order_by("customer")
        )

    if selected_loans:
        # Create a new NoticeGroup
        ng = NoticeGroup.objects.create(name=datetime.now())

        # Get a queryset of customers with selected loans
        customers = Customer.objects.filter(loan__in=selected_loans).distinct()

        # Create a list of Notification objects to create
        notifications_to_create = []
        for customer in customers:
            notifications_to_create.append(
                Notification(
                    group=ng,
                    customer=customer,
                )
            )
        # Use bulk_create to create the notifications
        try:
            notifications = Notification.objects.bulk_create(notifications_to_create)
        except IntegrityError:
            print("Error adding notifications.")

        # Add loans to the notifications
        for notification in notifications:
            loans = selected_loans.filter(customer=notification.customer)
            notification.loans.set(loans)
            notification.save()
        return redirect(ng.get_absolute_url())

    return HttpResponse(status=200, content="No unreleased loans selected.")


@login_required
def print_loan(request, pk=None):
    loan = get_object_or_404(Loan, pk=pk)
    template = request.user.workspace.preferences["Loan__LoanPDFTemplate"]
    if template == "c":
        pdf = get_custom_jsk(loan=loan)
    elif template == "j":
        pdf = get_custom_jcl(loan=loan)
    else:
        pdf = get_loan_template(loan=loan)
    # Create a response object
    response = HttpResponse(pdf, content_type="application/pdf")
    # response["Content-Disposition"] = 'attachment; filename="pledge.pdf"'
    response["Content-Disposition"] = f"inline; filename='{loan.loan_id}.pdf'"
    response["Content-Transfer-Encoding"] = "binary"
    return response


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
    numbers = Loan.objects.unreleased().values_list("loan_id", flat=True)

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

from ..models import Loan, Series
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
        loans = Loan.objects.filter(series=series).with_details()

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
    ] = f'attachment; filename="{request.user.workspace.name}_ledger.xlsx"'
    wb.save(response)

    return response
