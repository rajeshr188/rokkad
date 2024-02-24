from django.shortcuts import render
from .models import Customer
from .forms import ContactForm
from apps.orgs.decorators import company_member_required
# Create your views here.
@company_member_required
def contact_list(request):
    contacts = Customer.objects.all()
    return render(request, 'contacts/contact_list.html',{ 'contacts': contacts})

@company_member_required
def contact_detail(request, pk):
    contact = Customer.objects.get(id=pk)
    return render(request, 'contacts/contact_detail.html',{ 'contact': contact})

@company_member_required
def contact_create(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
    form = ContactForm()
    return render(request, 'contacts/contact_form.html',{"form": form})

@company_member_required
def contact_delete(request, pk):
    contact = Customer.objects.get(id=pk)
    if request.method == 'POST':
        contact.delete()
        return redirect('contact_list')
    return render(request, 'contacts/contact_delete.html', {'contact': contact})
