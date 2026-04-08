import django_tables2 as tables
from django_tables2.utils import A

from .models import Payment, Purchase


class PurchaseTable(tables.Table):
    id = tables.Column(linkify=True)
    supplier = tables.Column(linkify=True)
    # paid = tables.Column(
    #     accessor="get_total_payments", verbose_name="Paid", orderable=False
    # )
    net_wt = tables.Column(
        accessor="get_net_wt", verbose_name="Net Wt", orderable=False, empty_values=[]
    )
    balance = tables.Column(
        accessor="get_balance", verbose_name="Balance", orderable=False, empty_values=[]
    )
    edit = tables.Column(
        linkify=("purchase:purchase_invoice_update", [tables.A("pk")]),
        empty_values=(),
        attrs={"a": {"class": "btn btn-outline-info", "role": "button"}},
    )
    remove = tables.Column(
        linkify=("purchase:purchase_invoice_delete", [tables.A("pk")]),
        empty_values=(),
        attrs={"a": {"class": "btn btn-outline-danger", "role": "button"}},
    )

    def render_supplier(self, value):
        return value.name

    def render_voucher_date(self, value):
        return value.strftime("%d/%m/%y")

    def render_edit(self):
        return "Edit"

    def render_remove(self):
        return "Delete"

    class Meta:
        model = Purchase
        fields = (
            "id",
            "voucher_date",
            "supplier",
            "net_wt",
            "balance",
            "status",
            "is_gst",
            "term",
            "due_date",
        )

        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No Invoices Found matching your search..."
        template_name = "table_htmx.html"


class PaymentTable(tables.Table):
    id = tables.Column(linkify=True)
    supplier = tables.Column(linkify=True)
    # edit = tables.LinkColumn('purchase_payment_update',
    #                     args=[A('pk')],attrs={'a':{"class":"btn btn-outline-info","role":"button"}},
    #                     orderable=False, empty_values=())
    remove = tables.LinkColumn(
        "purchase:purchase_payment_delete",
        args=[A("pk")],
        attrs={"a": {"class": "btn btn-outline-danger", "role": "button"}},
        orderable=False,
        empty_values=(),
    )

    def render_supplier(self, value):
        return value.name

    def render_voucher_date(self, value):
        return value.strftime("%d/%m/%y")

    # def render_edit(self):
    #     return 'Edit'
    def render_remove(self):
        return "Delete"

    class Meta:
        model = Payment
        fields = (
            "id",
            "voucher_date",
            "supplier",
            "total",
            "status",
            "description",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No Receipts Found matching your search..."
