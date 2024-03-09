from django.db import connection, models
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from moneyed import Money
from psycopg.types.composite import CompositeInfo, register_composite

# old way of registering adapter
# from psycopg2.extensions import AsIs, adapt, register_adapter
# from psycopg2.extras import register_composite


# def moneyvalue_adapter(value):
#     return AsIs(
#         "(%s,%s)::money_value" % (adapt(value.amount), adapt(value.currency.code))
#     )


# registering composite types using psycopg


@receiver(connection_created)
def register_composites(sender, connection, **kwargs):
    #     MoneyValue = register_composite(
    #     "money_value", connection.cursor().cursor, globally=True
    # ).type
    info = CompositeInfo.fetch(connection.connection, "money_value")
    composite = register_composite(
        info=info,
        context=None,
        factory=lambda amount, currency: Money(amount, currency),
    )
