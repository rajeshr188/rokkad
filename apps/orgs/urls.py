from django.urls import path
from . import views

urlpatterns = [
    # other urls...
    path('invite/', views.create_invite, name='invite_to_company'),
    path('invite/success/', views.invite_success, name='invite-success-url'),
    path('invitations/accept-invite/<str:key>/', views.CustomAcceptInvite.as_view(), name='accept-invite'),
]