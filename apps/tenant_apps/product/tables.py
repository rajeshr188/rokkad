import django_tables2 as tables
from django.utils.html import format_html

from .models import Stock


class StockTable(tables.Table):
    id = tables.Column(linkify=True)
    created = tables.Column()
    variant = tables.Column(linkify=True)
    actions = tables.Column(orderable=False, empty_values=())
    weight = tables.Column(
        accessor="get_weight",
        verbose_name="Weight",
    )
    quantity = tables.Column(
        accessor="get_quantity",
        verbose_name="Qty",
    )
    purchase_touch = tables.Column(
        verbose_name="Touch",
    )
    purchase_rate = tables.Column(
        verbose_name="Rate",
    )
    lot_no = tables.Column(
        verbose_name="Lot#",
    )
    serial_no = tables.Column(
        verbose_name="Serial#",
    )

    def render_actions(self, record):
        return format_html(
            """
            <div class="btn-group responsive">
                <button type="button" class="btn btn-sm btn-secondary dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-three-dots-vertical" viewBox="0 0 16 16">
  <path d="M9.5 13a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0"/>
</svg>
                </button>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item text-info" hx-target="#content" hx-get="/product/stock/transaction/{}"
    #                 hx-push-url="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-square" viewBox="0 0 16 16">
    #                 <path d="M14 1a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h12zM2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H2z"/>
    #                 <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
    #                 </svg> Transaction</a></li>
                    <li><a class="dropdown-item text-primary" hx-target="#content" hx-get="/product/stock/{}/split/"
                    hx-push-url="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-signpost-split" viewBox="0 0 16 16">
                    <path d="M7 7V1.414a1 1 0 0 1 2 0V2h5a1 1 0 0 1 .8.4l.975 1.3a.5.5 0 0 1 0 .6L14.8 5.6a1 1 0 0 1-.8.4H9v10H7v-5H2a1 1 0 0 1-.8-.4L.225 9.3a.5.5 0 0 1 0-.6L1.2 7.4A1 1 0 0 1 2 7zm1 3V8H2l-.75 1L2 10zm0-5h6l.75-1L14 3H8z"/>
                </svg> Split</a></li>
<li><a class="dropdown-item text-warning" hx-get="/product/stock/{}/merge/"
    #                     hx-push-url="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-sign-merge-right-fill" viewBox="0 0 16 16">
  <path d="M9.05.435c-.58-.58-1.52-.58-2.1 0L.436 6.95c-.58.58-.58 1.519 0 2.098l6.516 6.516c.58.58 1.519.58 2.098 0l6.516-6.516c.58-.58.58-1.519 0-2.098zM8.75 6v1q.211.451.588.95c.537.716 1.259 1.44 2.016 2.196l-.708.708-.015-.016c-.652-.652-1.33-1.33-1.881-2.015V12h-1.5V6H6.034a.25.25 0 0 1-.192-.41l1.966-2.36a.25.25 0 0 1 .384 0l1.966 2.36a.25.25 0 0 1-.192.41z"/>
</svg> Merge</a></li>
                    <li><a class="dropdown-item text-danger" hx-delete="/product/stock/{}/delete/" hx-confirm="Are you sure?" hx-target="closest tr" hx-swap="outerHTML swap:0.5s"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash" viewBox="0 0 16 16">
    #                 <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5Zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5Zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6Z"/>
    #                 <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1ZM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118ZM2.5 3h11V2h-11v1Z"/>
    #                 </svg> Stock</a></li>
                </ul>
            </div>
            """,
            record.pk,
            record.pk,
            record.pk,
            record.pk,
        )

    class Meta:
        model = Stock
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No Stock Found matching your search..."
        template_name = "table_htmx.html"  # Use a Bootstrap 4 template (optional)
        fields = (
            "id",
            "created",
            "variant",
            "huid",
            "lot_no",
            "serial_no",
            "quantity",
            "weight",
            "purchase_touch",
            "purchase_rate",
            "status",
        )  # Specify the fields to display in the table
