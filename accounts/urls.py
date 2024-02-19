from django.urls import path
from . import views

urlpatterns = [
    # other url patterns
    path('profile/', views.profile, name='profile'),
    path('membership/list/', views.membership_list, name='orgs_membership_list'),
]