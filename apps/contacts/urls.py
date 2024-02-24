from django.urls import path
from . import views

urlpatterns = [
    path('contact/', views.contact_list, name='contact_list'),
    path('contact/create/', views.contact_create, name='contact_create'),
    path('contact/<int:pk>/', views.contact_detail, name='contact_detail'),
    path('contact/<int:pk>/delete/', views.contact_delete, name='contact_delete'),
]
