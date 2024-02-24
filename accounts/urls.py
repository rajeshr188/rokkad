from django.urls import path
from . import views

urlpatterns = [
    # other url patterns
    path('profile/', views.profile, name='profile'),
    path('membership/list/', views.membership_list, name='orgs_membership_list'),
    path('switch/workspace/<int:workspace_id>/', views.switch_workspace, name='switch_workspace'),
    path('clear/workspace/', views.clear_workspace, name='clear_workspace'),
]