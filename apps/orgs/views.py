from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from invitations.views import AcceptInvite
from .models import Membership,Role,Company,CompanyInvitation,Domain
from .forms import CompanyInvitationForm,CompanyForm
from .decorators import role_required,company_member_required
from django.db.models import Count
from django_tenants.utils import remove_www
#
# Create your views here.

User = get_user_model()

def has_permission(user, tenant, permission_codename):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.permissions.filter(codename=permission_codename).exists()

def has_role(user, tenant, role_name):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.name == role_name

# def my_view(request, tenant_id):
#     tenant = get_object_or_404(Tenant, id=tenant_id)

#     if not has_permission(request.user, tenant, 'my_permission'):
#         return HttpResponseForbidden()

    # Existing code...



@login_required
def company_create(request):
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.schema_name = company.name.lower().replace(' ', '_')
            company.creator = request.user
            company.owner = request.user
            company.save()
            domain = remove_www(request.get_host().split(":")[0]).lower()
            company_domain = f"{company.schema_name}.{domain}"
            Domain.objects.create(tenant=company, domain=company_domain, is_primary=True)
            Membership.objects.create(user=request.user, company=company, role=Role.objects.get(name='Owner'))
            return redirect('orgs_company_list')
    else:
        form = CompanyForm()
    return render(request, 'company/company_form.html', {'form': form})

@login_required
def company_list(request):
    companies = request.user.owned_companies.annotate(num_members=Count('membership'))
    
    form = CompanyForm()
    return render(request, 'company/company_list.html', {'companies': companies,'form': form})

@login_required
@company_member_required
def company_detail(request, company_id):
    company = Company.objects.get(id=company_id)
    return render(request, 'company/company_detail.html', {'company': company})


@role_required('Owner')
def company_update(request, company_id):
    company = Company.objects.get(id=company_id)
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            return redirect('orgs_company_list')
    else:
        form = CompanyForm(instance=company)
    return render(request, 'company/company_form.html', {'form': form})


@role_required('Owner')
def company_delete(request, company_id):
    company = get_object_or_404(Company, id=company_id)

    # Check if the user has the permission to delete the company
    if request.user != company.owner:
        return redirect('error_page')  # Redirect to an error page

    company.delete()
    return redirect('orgs_company_list')  # Redirect to the list of companies

@login_required
def companyinvitations_list(request):
    invitations = CompanyInvitation.objects.filter(inviter=request.user.id)
    return render(request, 'company/company_invitations_list.html', {'invitations': invitations})
    

# @role_required('Owner')
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
