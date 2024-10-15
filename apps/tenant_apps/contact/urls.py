from django.urls import include, path

from . import views

urlpatterns = (
    # urls for Customer
    path("export/", views.export_form, name="export_form"),
    path(
        "export/<str:model_name>/<str:export_format>/",
        views.export_data,
        name="export_data",
    ),
    path("import/", views.import_data, name="import_data"),
    path("get_model_fields/", views.get_model_fields, name="get_model_fields"),
    path("customer/", views.customer_list, name="contact_customer_list"),
    path("customer/create/", views.customer_save, name="contact_customer_create"),
    path(
        "customer/detail/<int:pk>/",
        views.customer_detail,
        name="contact_customer_detail",
    ),
    path("report/", views.CustomerReport.as_view(), name="customer_report"),
    path(
        "customer/update/<int:pk>/", views.customer_save, name="contact_customer_update"
    ),
    path(
        "customer/<int:pk>/delete/",
        views.customer_delete,
        name="contact_customer_delete",
    ),
    path(
        "customer/<int:pk>/reallot_receipts/",
        views.reallot_receipts,
        name="contact_reallot_receipts",
    ),
    path(
        "customer/<int:pk>/reallot_payments/",
        views.reallot_payments,
        name="contact_reallot_payments",
    ),
    path(
        "customer/contactno/<int:pk>/detail/",
        views.contact_detail,
        name="customer_contact_detail",
    ),
    path("customer/contactno/<int:pk>/set_default/", views.contact_set_default, name="customer_contact_set_default"),
    path(
        "customer/<int:customer_pk>/contactno/add/",
        views.contact_save,
        name="contact_create",
    ),
    path(
        "customer/<int:customer_pk>/contactno/<int:contact_pk>/update/",
        views.contact_save,
        name="contact_update",
    ),
    path(
        "customer/contactno/<int:pk>/delete/",
        views.contact_delete,
        name="customer_contact_delete",
    ),
    path(
        "customer/<int:pk>/contactno/",
        views.contact_list,
        name="customer_contactno_list",
    ),
    path(
        "customer/<int:pk>/address/",
        views.address_list,
        name="customer_address_list",
    ),
    path(
        "customer/<int:customer_pk>/address/add/",
        views.address_create_or_update,
        name="customer_address_create",
    ),
    path(
        "customer/<int:customer_pk>/address/<int:address_pk>/edit/",
        views.address_create_or_update,
        name="customer_address_update",
    ),
    path("customer/address/<int:pk>/set_default/", views.address_set_default, name="customer_address_set_default"),
    path(
        "customer/address/<int:pk>/detail/",
        views.address_detail,
        name="customer_address_detail",
    ),
    path(
        "customer/address/<int:pk>/delete/",
        views.address_delete,
        name="customer_address_delete",
    ),
    path("customer/merge/", views.customer_merge, name="contact_customer_merge"),
    # path to create_relationship view
    path(
        "customer/<int:customer_id>/relationship/add/",
        views.relationship_save,
        name="create_relationship",
    ),
    path(
        "customer/<int:customer_id>/relationship/<int:relationship_id>/edit",
        views.relationship_save,
        name="update_relationship",
    ),
    path(
        "customer/relationship/<int:relationship_id>/delete/",
        views.relationship_delete,
        name="delete_relationship",
    ),
    path(
        "customer/relationship/<int:relationship_id>/detail/",
        views.relationship_detail,
        name="relationship_detail",
    ),
    path(
        "customer/<int:from_customer_id>/relationship/",
        views.relationship_list,
        name="relationship_list",
    ),
    path(
        "customer/<int:customer_id>/pics/",
        views.customer_pics,
        name="contact_customer_pics",
    ),
    path(
        "customer/<int:customer_id>/add_pic/",
        views.add_customer_pic,
        name="contact_customer_pic_add",
    ),
    path(
        "customer/pic/<int:pk>/delete/",
        views.customer_pic_delete,
        name="contact_pic_delete",
    ),
    path(
        "customer/pic/<int:pk>/set_default/",
        views.customer_pic_set_default,
        name="contact_pic_set_default",
    ),
)
