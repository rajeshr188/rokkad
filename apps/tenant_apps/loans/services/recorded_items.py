"""Actual paper item agreements and exact item-rounded monetary totals."""
from decimal import Decimal, ROUND_HALF_UP

ITEM_PROFILE = "recorded-anniversary/2"
MONEY = Decimal("0.01")


def monthly_interest(items, quantum=MONEY):
    return sum(((Decimal(row["principal"]) * Decimal(row["rate"]) / 100).quantize(
        Decimal(quantum).normalize(), rounding=ROUND_HALF_UP) for row in items), Decimal("0"))


def effective_rate(items):
    principal = sum((Decimal(row["principal"]) for row in items), Decimal("0"))
    return (sum((Decimal(row["principal"]) * Decimal(row["rate"]) for row in items),
                Decimal("0")) / principal).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def contract_items(data):
    return data.get("collateral") or [{name: data[name] for name in (
        "description", "metal", "quantity", "gross_weight", "net_weight", "purity", "principal", "rate")}]


def validate_items(rows, amount, text):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("Enter between one and 100 actual collateral rows.")
    fields = {"description", "metal", "quantity", "gross_weight", "net_weight", "purity", "principal", "rate"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Each collateral row needs its actual item details, principal and rate.")
        row["description"] = text(row["description"], "item description", 255)
        if row["metal"] not in ("GOLD", "SILVER") or type(row["quantity"]) is not int or not 1 <= row["quantity"] <= 10000:
            raise ValueError("Select a supported item metal and quantity.")
        for name in ("gross_weight", "net_weight", "purity"):
            row[name] = amount(row[name], name, places=4, positive=True)
        row["principal"] = amount(row["principal"], "item principal", positive=True)
        row["rate"] = amount(row["rate"], "item monthly rate", places=6)
        if Decimal(row["rate"]) > 100 or Decimal(row["purity"]) > 100 or Decimal(row["net_weight"]) > Decimal(row["gross_weight"]):
            raise ValueError("Check the item's rate, purity and net weight.")
    return rows
