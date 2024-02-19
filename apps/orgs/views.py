from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from invitations.views import AcceptInvite
from .models import Membership
from .forms import CompanyInvitationForm

# Create your views here.

User = get_user_model()

@login_required
def create_invite(request):
    if request.method == 'POST':
        form = CompanyInvitationForm(request.POST, inviter=request.user,request=request)
        if form.is_valid():
            form.save()
            return redirect('invite-success-url')
    else:
        form = CompanyInvitationForm(inviter=request.user)
    return render(request, 'company/invitation_form.html', {'form': form})

@login_required
def invite_success(request):
    return render(request, 'company/invite_success.html')

class CustomAcceptInvite(AcceptInvite):
    def get(self, *args, **kwargs):
        invite = self.get_object()
        email = invite.email
        user = User.objects.filter(email=email).first()

        if user:
            # If the user is already registered, create a Membership instance
            Membership.objects.create(user=user, company=invite.company)

        return super().get(*args, **kwargs)
