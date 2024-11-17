# # models/period.py
# from django.db import models
# from django.core.exceptions import ValidationError
# from django.utils import timezone
# import calendar

# class AccountingPeriod(models.Model):
#     class PeriodStatus(models.TextChoices):
#         OPEN = 'OPEN', 'Open'
#         CLOSED = 'CLOSED', 'Closed'
#         LOCKED = 'LOCKED', 'Locked'
    
#     start_date = models.DateField()
#     end_date = models.DateField()
#     status = models.CharField(
#         max_length=10,
#         choices=PeriodStatus.choices,
#         default=PeriodStatus.OPEN
#     )
#     closed_date = models.DateTimeField(null=True, blank=True)
#     closed_by = models.ForeignKey(
#         'users.CustomUser', 
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True
#     )
#     closing_journal_entry = models.OneToOneField(
#         'JournalEntry',
#         on_delete=models.PROTECT, 
#         null=True,
#         blank=True,
#         related_name='closing_period'
#     )

#     class Meta:
#         ordering = ['-end_date']
#         constraints = [
#             models.CheckConstraint(
#                 check=models.Q(end_date__gt=models.F('start_date')),
#                 name='end_date_after_start_date'
#             )
#         ]

#     def clean(self):
#         if self.start_date and self.end_date:
#             if self.end_date <= self.start_date:
#                 raise ValidationError('End date must be after start date')
            
#             # Check for overlapping periods
#             overlapping = AccountingPeriod.objects.filter(
#                 start_date__lte=self.end_date,
#                 end_date__gte=self.start_date
#             )
#             if self.pk:
#                 overlapping = overlapping.exclude(pk=self.pk)
#             if overlapping.exists():
#                 raise ValidationError('Periods cannot overlap')

#     @transaction.atomic
#     def close_period(self, user):
#         """Close accounting period and generate closing entries"""
#         if self.status != self.PeriodStatus.OPEN:
#             raise ValidationError('Can only close open periods')

#         # Calculate closing balances
#         income_accounts = Ledger.objects.filter(
#             AccountType__AccountType__in=['Revenue', 'Expense']
#         )
        
#         closing_entries = []
#         retained_earnings = Ledger.objects.get(name='Retained Earnings')
        
#         # Close income/expense accounts to retained earnings
#         for account in income_accounts:
#             balance = account.get_balance()
#             if balance != 0:
#                 closing_entries.append({
#                     'ledgerno': account.id,
#                     'ledgerno_dr': retained_earnings.id,
#                     'amount': abs(balance)
#                 })

#         # Create closing journal entry
#         je = JournalEntry.objects.create(
#             desc=f'Period Closing Entry - {self.end_date}',
#         )
#         je.transact(closing_entries, [])
        
#         self.status = self.PeriodStatus.CLOSED
#         self.closed_date = timezone.now()
#         self.closed_by = user
#         self.closing_journal_entry = je
#         self.save()

#     def lock_period(self):
#         """Lock period to prevent any changes"""
#         if self.status != self.PeriodStatus.CLOSED:
#             raise ValidationError('Can only lock closed periods')
#         self.status = self.PeriodStatus.LOCKED
#         self.save()
