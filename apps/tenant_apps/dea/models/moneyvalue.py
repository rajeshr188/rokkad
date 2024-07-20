from django.db import connection, models
from moneyed import Money


class MoneyValueField(models.Field):
    description = "wrapper for money_value composite type in postgres"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return Money(value.amount, value.currency)

    def to_python(self, value):
        if isinstance(value, Money):
            return value
        if value is None:
            return value
        return Money(value.amount, value.currency.code)

    def get_prep_value(self, value):
        # in admin input box we enter 10 USD,20 INR,30 AUD

        if isinstance(value, Money):
            return value
        else:
            amount, currency = value.split()
            return Money(amount, currency)

    def db_type(self, connection):
        return "money_value"


# class MoneyValueField(models.Field):
#     description = "A custom field for PostgreSQL money_value type"

#     def db_type(self, connection):
#         return 'money_value'

#     def from_db_value(self, value, expression, connection):
#         if value is None:
#             return value
#         amount, currency = value[1:-1].split(',')
#         return Money(amount=Decimal(amount), currency=currency)

#     def get_prep_value(self, value):
#         if value is None:
#             return None
#         if isinstance(value, Money):
#             return f'({value.amount},{value.currency.code})'
#         return value

#     def to_python(self, value):
#         if isinstance(value, Money):
#             return value
#         if value is None:
#             return value
#         amount, currency = value[1:-1].split(',')
#         return Money(amount=Decimal(amount), currency=currency)

#     def get_internal_type(self):
#         return 'MoneyValueField'
