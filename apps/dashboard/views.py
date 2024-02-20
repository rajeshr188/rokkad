from django.shortcuts import render
from apps.orgs.models import Membership
from django.shortcuts import redirect
from django.http import HttpResponseForbidden as HTTP403Forbidden
from django.contrib.auth.decorators import login_required
@login_required
def index(request):
    # if request.user.is_authenticated and request.user.is_superuser:
    #     return redirect('orgs_member_dashboard')
    # else:
    #     print(request.user.id)
    #     print(request.user)
    #     print(request.user.is_superuser)
    # try:
    #     membership = Membership.objects.get(user=request.user.id)
    #     if membership.role == 'Customer':
    #         return redirect('orgs_customer_dashboard')
    #     else:
    #         return redirect('orgs_member_dashboard')
    # except Membership.DoesNotExist:
    #     return HTTP403Forbidden()
    return render(request, 'dashboard/index.html')
    # return render(request, 'orgs/orgs_dashboard.html')
    # return render(request, 'orgs/customer_dashboard.html')

    

