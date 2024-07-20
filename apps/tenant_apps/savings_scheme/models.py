from django.db import models


# Create your models here.
class Scheme(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    max_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2)
    max_withdrawal = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}".format(self.name)


class Subscription(models.Model):
    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE)
    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE)
    deposit = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}".format(self.account)


class Payment(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}".format(self.subscription)


class Withdrawal(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{}".format(self.subscription)
