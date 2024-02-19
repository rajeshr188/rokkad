from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def profile(request):
    return render(request, 'account/profile.html')

def membership_list(request):
    memberships = request.user.memberships.all()
    return render(request, 'account/membership_list.html', {'memberships': memberships})    