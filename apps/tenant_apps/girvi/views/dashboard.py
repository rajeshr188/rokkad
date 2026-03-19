"""Girvi Dashboard and Navigation Views"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import (
    GivenLoan, Release, License, Series, LoanItemStorageBox,
    LoanPayment, StatementItem
)
from apps.tenant_apps.notify.models import Notification


@login_required
def girvi_dashboard(request):
    """
    Girvi Dashboard: Central hub showing all available operations,
    organized by workflow/entity with counts and quick access links.
    """
    
    # Loan counts and status via refactored manager/queryset API
    given_loans = GivenLoan.objects
    total_loans = given_loans.count()
    unreleased_loans = given_loans.unreleased().count()
    released_loans = given_loans.released().count()
    overdue_loans = given_loans.non_performing_loans_stats().count()
    total_loan_amount = given_loans.get_queryset().total_loan_amount() or 0
    
    # Release counts
    total_releases = Release.objects.count()
    recent_releases = Release.objects.order_by('-release_date')[:5]
    
    # License counts
    total_licenses = License.objects.count()
    active_licenses = License.objects.filter(is_active=True).count()
    
    # Series counts
    total_series = Series.objects.count()
    active_series = Series.objects.filter(is_active=True).count()
    
    # Storage box counts
    total_boxes = LoanItemStorageBox.objects.count()
    
    # Payment counts
    total_payments = LoanPayment.objects.count()
    pending_payments = LoanPayment.objects.filter(with_release=False).count()
    
    # Statement counts
    total_statements = StatementItem.objects.count()
    
    # Notification/Notice counts
    total_notifications = Notification.objects.count()
    pending_notifications = Notification.objects.filter(
        status=Notification.StatusType.Draft
    ).count()
    
    context = {
        # Loan section
        'total_loans': total_loans,
        'unreleased_loans': unreleased_loans,
        'released_loans': released_loans,
        'overdue_loans': overdue_loans,
        'total_loan_amount': total_loan_amount,
        
        # Release section
        'total_releases': total_releases,
        'recent_releases': recent_releases,
        
        # License section
        'total_licenses': total_licenses,
        'active_licenses': active_licenses,
        
        # Series section
        'total_series': total_series,
        'active_series': active_series,
        
        # Storage section
        'total_boxes': total_boxes,
        
        # Payment section
        'total_payments': total_payments,
        'pending_payments': pending_payments,
        
        # Statement section
        'total_statements': total_statements,
        
        # Notification section
        'total_notifications': total_notifications,
        'pending_notifications': pending_notifications,
    }
    
    return render(request, 'girvi/dashboard.html', context)
