from django.urls import path

from . import views

app_name = "party"

urlpatterns = [
    path("<int:pk>/photo/view/", views.party_profile_photo, name="party_photo"),
    path("<int:pk>/documents/<int:document_pk>/download/", views.party_document_download, name="party_document_download"),
    path("autocomplete/", views.party_autocomplete, name="party_autocomplete"),
    path("", views.party_list, name="party_list"),
    path("create/", views.party_create, name="party_create"),
    path("<int:pk>/", views.party_detail, name="party_detail"),
    path("<int:pk>/edit/", views.party_update, name="party_update"),
    path("<int:pk>/merge/", views.party_merge, name="party_merge"),
    path("<int:pk>/photo/", views.party_profile_photo_update, name="party_photo_update"),
    path(
        "<int:pk>/photo/remove/",
        views.party_profile_photo_remove,
        name="party_photo_remove",
    ),
    path("<int:pk>/roles/add/", views.party_role_add, name="party_role_add"),
    path(
        "<int:pk>/roles/<int:role_pk>/end/",
        views.party_role_end,
        name="party_role_end",
    ),
    path("<int:pk>/contacts/save/", views.party_contact_save, name="party_contact_add"),
    path(
        "<int:pk>/contacts/<int:contact_pk>/save/",
        views.party_contact_save,
        name="party_contact_update",
    ),
    path(
        "<int:pk>/contacts/<int:contact_pk>/delete/",
        views.party_contact_delete,
        name="party_contact_delete",
    ),
    path("<int:pk>/addresses/save/", views.party_address_save, name="party_address_add"),
    path(
        "<int:pk>/addresses/<int:address_pk>/save/",
        views.party_address_save,
        name="party_address_update",
    ),
    path(
        "<int:pk>/addresses/<int:address_pk>/delete/",
        views.party_address_delete,
        name="party_address_delete",
    ),
    path(
        "<int:pk>/identifiers/save/",
        views.party_identifier_save,
        name="party_identifier_add",
    ),
    path(
        "<int:pk>/identifiers/<int:identifier_pk>/save/",
        views.party_identifier_save,
        name="party_identifier_update",
    ),
    path(
        "<int:pk>/identifiers/<int:identifier_pk>/delete/",
        views.party_identifier_delete,
        name="party_identifier_delete",
    ),
    path(
        "<int:pk>/documents/save/",
        views.party_document_save,
        name="party_document_add",
    ),
    path(
        "<int:pk>/documents/<int:document_pk>/save/",
        views.party_document_save,
        name="party_document_update",
    ),
    path(
        "<int:pk>/documents/<int:document_pk>/delete/",
        views.party_document_delete,
        name="party_document_delete",
    ),
    path(
        "<int:pk>/relationships/save/",
        views.party_relationship_save,
        name="party_relationship_add",
    ),
    path(
        "<int:pk>/relationships/<int:relationship_pk>/save/",
        views.party_relationship_save,
        name="party_relationship_update",
    ),
    path(
        "<int:pk>/relationships/<int:relationship_pk>/delete/",
        views.party_relationship_delete,
        name="party_relationship_delete",
    ),
]
