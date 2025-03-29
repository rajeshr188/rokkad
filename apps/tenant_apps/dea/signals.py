from django.db.backends.signals import connection_created
from django.dispatch import receiver
from moneyed import Money

# old way of registering adapter
from psycopg2.extensions import AsIs, adapt, register_adapter
from psycopg2.extras import register_composite


def moneyvalue_adapter(value):
    return AsIs(
        "(%s,%s)::money_value" % (adapt(value.amount), adapt(value.currency.code))
    )


@receiver(connection_created)
def register_composites(sender, connection, **kwargs):
    print("registering composites")
    MoneyValue = register_composite(
        "money_value", connection.cursor().cursor, globally=True
    ).type
    register_adapter(Money, moneyvalue_adapter)
    print("composites registered")


# registering composite types using psycopg
# from psycopg.types.composite import CompositeInfo, register_composite
# @receiver(connection_created)
# def register_composites(sender, connection, **kwargs):
#     info = CompositeInfo.fetch(connection.connection, "money_value")
#     composite = register_composite(
#         info=info,
#         context=None,
#         factory=lambda amount, currency: Money(amount, currency),
#     )

# from django.db import connection
# from django.db.backends.signals import connection_created
# from psycopg import connect
# from psycopg.types.composite import CompositeInfo, register_composite

# from .models.moneyvalue import MoneyValue

# def register_money_value_composite(sender, connection, **kwargs):
#     with connection.cursor() as cursor:
#         # Ensure the composite type exists in the database
#         # cursor.execute("""
#         #     CREATE TYPE IF NOT EXISTS money_value AS (
#         #         amount numeric,
#         #         currency varchar(3)
#         #     );
#         # """)
#         # Register the composite type with Psycopg
#         conn = connection.connection
#         info = CompositeInfo.fetch(conn, 'money_value')
#         register_composite(info, conn, factory=MoneyValue)

# # Connect the signal
# connection_created.connect(register_money_value_composite)
