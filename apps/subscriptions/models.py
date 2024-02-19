from django.db import models
from django.contrib.auth.models import User

class Plan(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField()

    class BillingCycleChoices(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    billing_cycle = models.CharField(max_length=10, choices=BillingCycleChoices.choices,default=BillingCycleChoices.MONTHLY)
    # Add other fields as needed, such as the features that the plan includes'

    def __str__(self):
        return self.name

class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.customer}'s {self.plan} Subscription"

    def save(self, *args, **kwargs):
        if not self.id:
            # Calculate end date based on start date and plan's billing cycle
            if self.plan.billing_cycle == SubscriptionPlan.MONTHLY:
                self.end_date = self.start_date + relativedelta(months=1)
            elif self.plan.billing_cycle == SubscriptionPlan.ANNUAL:
                self.end_date = self.start_date + relativedelta(years=1)
        super().save(*args, **kwargs)

    # Add other fields as needed, such as the status of the subscriptionfrom django.db import models

# Create your models here.
class Invoice(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Add other fields as needed, such as the status of the invoice

    def __str__(self):
        return f"Invoice for {self.subscription.user.username}: {self.amount}"

class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    # Add other fields as needed, such as the payment method used

    def __str__(self):
        return f"Payment of {self.amount} for {self.invoice.subscription.user.username}"

